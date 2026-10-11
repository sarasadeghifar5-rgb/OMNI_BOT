import re
import os
import logging
from typing import Optional
import httpx

from app.providers.gemini_provider import GeminiKeyPool
from app.services.http_client import get_shared_http_client

logger = logging.getLogger("PromptEnhancer")
_TRANSLATION_CACHE: dict = {}

TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional Persian-to-English translator for AI image/video generation prompts. "
    "Translate the user's Persian text into natural, accurate, fluent English, preserving every detail "
    "(subjects, colors, numbers, actions, style, setting, mood). Do not add, omit or invent anything. "
    "Keep proper nouns correct (e.g. Tehran, Iran). Output ONLY the English translation, "
    "with no quotes, explanations, notes or Persian text."
)

def _clean_translation(text: str) -> str:
    """Normalizes an LLM translation response into a single clean line."""
    if not isinstance(text, str):
        return ""
    text = text.strip().strip('"\'`').replace("\n", " ").strip()
    text = re.sub(r"^(translation|english)\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()

def has_persian_characters(text: str) -> bool:
    """Checks if text contains any Persian/Arabic alphabet characters."""
    return bool(re.search(r'[\u0600-\u06FF]', text))

def clean_command_prefixes(prompt: str) -> str:
    """Strips common bot/user command prefixes and suffixes."""
    clean = prompt.strip()
    prefixes = [
        "عکس بساز از", "عکس بساز", "تصویر بساز از", "تصویر بساز",
        "یک عکس از", "یک تصویر از", "یک عکس", "یک تصویر",
        "عکس از", "تصویر از", "عکس", "تصویر", "نقاشی از", "نقاشی",
        "تولید عکس از", "تولید عکس", "تولید تصویر از", "تولید تصویر",
        "ویدیو بساز از", "ویدیو بساز", "یک ویدیو از", "کلیپ بساز از",
        "کلیپ بساز", "یک کلیپ از", "تولید ویدیو از", "فیلم کوتاه از",
        "با جمینای بساز", "/image", "/img", "/video", "/banana",
        "generate an image of", "create a photo of", "photo of", "picture of", "video of"
    ]
    for p in prefixes:
        if clean.lower().startswith(p.lower()):
            clean = clean[len(p):].lstrip(": ").strip()
            break

    suffixes = [
        "تولید کن لطفا", "تولید کن", "تولید کنید",
        "بساز لطفا", "بساز", "بسازید",
        "بکش لطفا", "بکش", "بکشید",
        "ایجاد کن", "ایجاد کنید", "طراحی کن", "طراحی کنید"
    ]
    for s in suffixes:
        if clean.endswith(s):
            clean = clean[:-len(s)].rstrip(": ").strip()
            break

    return clean or prompt.strip()

# Bilingual dictionary mapping for emergency fallback
KEYWORD_MAPPINGS = [
    ("فضانورد", "astronaut"),
    ("گربه", "cat"),
    ("سگ", "dog"),
    ("اسب", "horse"),
    ("شیر", "lion"),
    ("گرگ", "wolf"),
    ("پرنده", "bird"),
    ("عقاب", "eagle"),
    ("شاهین", "falcon"),
    ("ماشین", "car"),
    ("اتومبیل", "car"),
    ("موتور", "motorcycle"),
    ("تهران", "Tehran"),
    ("ایران", "Iran"),
    ("کوهستان", "mountains"),
    ("کوه", "mountain"),
    ("دریا", "ocean"),
    ("ساحل", "beach"),
    ("جنگل", "forest"),
    ("غروب", "sunset"),
    ("طلوع", "sunrise"),
    ("شهر", "city"),
    ("کوچه", "alley"),
    ("باران", "rain"),
    ("برف", "snow"),
    ("نئون", "neon lights"),
    ("مرد", "man"),
    ("زن", "woman"),
    ("کودک", "child"),
    ("بچه", "child"),
    ("گل", "flowers"),
    ("آسمان", "sky"),
    ("فضا", "space"),
    ("ماه", "moon"),
]

def fallback_translate(prompt: str, media_type: str = "image") -> str:
    """Fast keyword-based translation fallback if LLM APIs are unreachable."""
    clean = clean_command_prefixes(prompt)
    if not has_persian_characters(clean):
        return clean

    translated_parts = []
    text_lower = clean.lower()
    for fa, en in KEYWORD_MAPPINGS:
        if fa in text_lower:
            translated_parts.append(en)

    if not translated_parts:
        return clean

    return ", ".join(translated_parts)


class PromptEnhancerService:
    """
    Translates Persian prompts directly and faithfully to English
    without adding extra unsolicited words or cinematic descriptions.
    """

    @classmethod
    async def enhance_prompt(
        cls,
        prompt: str,
        media_type: str = "image"
    ) -> str:
        """
        Translates Persian/non-English prompts directly to English.
        If the prompt is already in English, it returns it completely untouched.
        Uses in-memory LRU cache and shared HTTP client pool for 0ms re-hits.
        """
        clean = clean_command_prefixes(prompt)
        if not clean:
            return ""

        is_persian = has_persian_characters(clean)

        # If it doesn't contain Persian characters, it's already English - leave it completely as is!
        if not is_persian:
            return clean

        cache_key = f"{media_type}:{clean.strip().lower()}"
        if cache_key in _TRANSLATION_CACHE:
            return _TRANSLATION_CACHE[cache_key]

        client = get_shared_http_client()

        # Attempt 1: Agnes AI direct translation
        from app.services.agnes_client import AgnesKeyPool, DEFAULT_BASE_URL
        agnes_pool = AgnesKeyPool.get_instance()
        active_keys = agnes_pool.get_active_keys()
        for key in active_keys[:2]:
            agnes_pool.acquire_key(key)
            try:
                base_url = (os.getenv("AGNES_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
                endpoint = f"{base_url}/chat/completions"
                payload = {
                    "model": "agnes-2.5-flash",
                    "messages": [
                        {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                        {"role": "user", "content": clean}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 600
                }
                resp = await client.post(
                    endpoint,
                    headers=agnes_pool.get_headers(key),
                    json=payload,
                    timeout=httpx.Timeout(12.0, connect=4.0)
                )
                if resp.status_code == 200:
                    agnes_pool.record_key_success(key)
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        content = _clean_translation(msg.get("content") or "")
                        if len(content) > 1 and not has_persian_characters(content):
                            logger.info(f"Prompt translated via Agnes: '{clean}' -> '{content}'")
                            if len(_TRANSLATION_CACHE) > 5000:
                                _TRANSLATION_CACHE.clear()
                            _TRANSLATION_CACHE[cache_key] = content
                            return content
                else:
                    agnes_pool.record_key_error(key, resp.status_code)
            except Exception as e:
                agnes_pool.record_key_error(key, 500)
                logger.warning(f"Agnes translation failed: {e}")
            finally:
                agnes_pool.release_key(key)

        # Attempt 2: Gemini direct translation (fallback)
        try:
            pool = GeminiKeyPool.get_instance()
            gemini_key = pool.get_active_key()
            if gemini_key and gemini_key.startswith("AIza"):
                for g_model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                    gen_config = {"temperature": 0.1, "maxOutputTokens": 800}
                    if "2.5" in g_model:
                        # Disable "thinking" so the token budget is not consumed before the answer
                        gen_config["thinkingConfig"] = {"thinkingBudget": 0}
                    payload = {
                        "systemInstruction": {"parts": [{"text": TRANSLATION_SYSTEM_PROMPT}]},
                        "contents": [
                            {"role": "user", "parts": [{"text": clean}]}
                        ],
                        "generationConfig": gen_config
                    }
                    resp = await client.post(url, json=payload, timeout=httpx.Timeout(12.0, connect=4.0))
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", []) or [{}]
                            text = _clean_translation(" ".join((p.get("text") or "") for p in parts))
                            if len(text) > 1 and not has_persian_characters(text):
                                logger.info(f"Prompt translated via Gemini: '{clean}' -> '{text}'")
                                _TRANSLATION_CACHE[cache_key] = text
                                return text
        except Exception as e:
            logger.warning(f"Gemini translation failed: {e}")

        # Fallback to direct dictionary (not cached, so the next request retries the LLM)
        return fallback_translate(clean, media_type=media_type)
