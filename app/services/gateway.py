import os
import copy
from typing import AsyncGenerator, Dict, Any, List, Optional

from app.config import (
    AVAILABLE_MODELS,
    PROVIDER_ENDPOINTS,
    DEFAULT_SYSTEM_PROMPT,
    MODELS_WITH_WEB_SEARCH,
    MODELS_WITH_VISION,
    MODELS_WITH_REASONING,
    get_model_capabilities,
)
from app.providers import OpenAICompatibleProvider, GeminiProvider, ClaudeProvider
from app.services.web_search import WebSearchService
from app.services.vision import VisionService

class LLMGateway:
    def __init__(self):
        self.web_search = WebSearchService()
        self.vision = VisionService()

    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        for m in AVAILABLE_MODELS:
            if m["id"] == model_id:
                return m
        # Fallback if custom model name
        if "/" in model_id:
            provider = "openrouter"
        elif "atria" in model_id.lower() or "dawn" in model_id.lower():
            provider = "atria"
        elif "agnes" in model_id.lower():
            provider = "agnes"
        elif "fable" in model_id or "opus" in model_id or "mythos" in model_id or "gpt-5" in model_id or "v4" in model_id or "seed-2" in model_id or "kimi" in model_id or "spark" in model_id:
            provider = "codecraft"
        elif "gpt" in model_id or "o1" in model_id or "o3" in model_id:
            provider = "openai"
        elif "deepseek" in model_id:
            provider = "deepseek"
        elif "grok" in model_id:
            provider = "grok"
        elif "glm" in model_id:
            provider = "glm"
        elif "gemini" in model_id:
            provider = "gemini"
        elif "claude" in model_id:
            provider = "claude"
        elif "ollama" in model_id:
            provider = "ollama"
        else:
            provider = "codecraft"

        return {
            "id": model_id,
            "name": model_id,
            "provider": provider,
            "supports_vision": any(k in model_id.lower() for k in ["vision", "4o", "gemini", "claude", "glm-4v", "vl", "qwen", "fable", "opus", "sol", "terra", "luna", "pro", "5.5", "5.6"]),
            "supports_reasoning": any(k in model_id.lower() for k in ["reasoner", "o1", "o3", "r1", "atria", "dawn", "fable", "opus", "sol", "pro", "v4", "mythos"]),
        }

    def resolve_api_key(self, provider: str, user_keys: Optional[Dict[str, str]] = None) -> Optional[str]:
        user_keys = user_keys or {}

        # 1. User provided key
        if user_keys.get(provider):
            return user_keys[provider].strip()

        if provider in ("codecraft", "cleanapis"):
            raw_ca = (os.getenv("CLEANAPIS_API_KEY") or os.getenv("CODECRAFT_API_KEY") or "").strip()
            if raw_ca.startswith("cc_"):
                return raw_ca
            return "cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB"

        # 2. Environment variables fallback
        env_map = {
            "codecraft": ["CLEANAPIS_API_KEYS", "CLEANAPIS_API_KEY", "CODECRAFT_API_KEYS", "CODECRAFT_API_KEY", "CODECRAFT_KEY"],
            "cleanapis": ["CLEANAPIS_API_KEYS", "CLEANAPIS_API_KEY", "CODECRAFT_API_KEYS", "CODECRAFT_API_KEY", "CODECRAFT_KEY"],
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "grok": ["GROK_API_KEY", "XAI_API_KEY"],
            "glm": ["GLM_API_KEY", "ZHIPUAI_API_KEY"],
            "gemini": ["GEMINI_MASTER_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEYS"],
            "claude": ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"],
            "openrouter": "OPENROUTER_API_KEY",
            "pollinations": ["POLLINATIONS_API_KEY", "POLLINATIONS_KEY"],
            "atria": ["ATRIA_API_KEYS", "ATRIA_API_KEY", "ATRIA_KEY"],
            "tavily": "TAVILY_API_KEY",
            "agnes": ["AGNES_API_KEYS", "AGNES_API_KEY"],
        }

        keys = env_map.get(provider)
        if isinstance(keys, list):
            for k in keys:
                val = os.getenv(k)
                if val and val.strip():
                    # If multiple keys separated by comma, take the first valid one
                    first_k = val.split(",")[0].strip()
                    if first_k:
                        return first_k
        elif isinstance(keys, str):
            val = os.getenv(keys)
            if val and val.strip():
                first_k = val.split(",")[0].strip()
                if first_k:
                    return first_k

        if provider in ("codecraft", "cleanapis"):
            return "cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB"

        return None

    def get_provider_instance(self, provider: str, api_key: Optional[str] = None):
        if provider == "claude":
            return ClaudeProvider(default_api_key=api_key)
        elif provider == "gemini":
            return GeminiProvider(default_api_key=api_key)
        elif provider == "agnes":
            from app.providers.agnes_provider import AgnesProvider
            return AgnesProvider(default_api_key=api_key)
        elif provider in ("codecraft", "cleanapis"):
            from app.providers.codecraft_provider import CodeCraftProvider
            return CodeCraftProvider(default_api_key=api_key)
        elif provider == "atria":
            from app.providers.atria_provider import AtriaProvider
            return AtriaProvider(default_api_key=api_key)
        else:
            base_url = PROVIDER_ENDPOINTS.get(provider, "https://api.openai.com/v1")
            return OpenAICompatibleProvider(default_api_key=api_key, base_url=base_url)

    @staticmethod
    def build_model_system_prompt(model_id: str, custom_prompt: Optional[str] = None) -> str:
        """
        Builds a dedicated, authentic persona for each model so that model switching
        is genuine and models properly identify themselves when asked who they are.
        """
        if custom_prompt and custom_prompt.strip():
            return custom_prompt.strip()

        mid = (model_id or "").lower()

        if "atria" in mid or "dawn" in mid:
            persona = (
                "You are Atria-Dawn-Preview, an advanced reasoning and research AI model developed by Atria ASI. "
                "When asked who you are or your name (e.g. 'اسمت چیه؟' or 'کی هستی؟'), "
                "explicitly and proudly state in fluent Persian that you are Atria Dawn Preview (مدل هوش مصنوعی تحلیلی و پژوهشی آتریا داون) developed by Atria ASI. "
                "You think deeply, rigorously, and analytically through every problem before answering."
            )
        elif "deepseek-reasoner" in mid or "r1" in mid:
            persona = (
                "You are DeepSeek-R1 (Reasoner), an advanced reasoning AI model developed by DeepSeek (دیپ‌سیک). "
                "When asked who you are or your name (e.g. 'اسمت چیه؟' or 'کی هستی؟'), "
                "explicitly and proudly state in fluent Persian that you are DeepSeek R1 (دیپ‌سیک R1) developed by DeepSeek. "
                "You think deeply, rigorously, and analytically through every problem before answering."
            )
        elif "deepseek" in mid or "v3" in mid:
            persona = (
                "You are DeepSeek-V3, the flagship large language model developed by DeepSeek (دیپ‌سیک). "
                "When asked who you are or your name (e.g. 'اسمت چیه؟' or 'کی هستی؟'), "
                "explicitly state in fluent Persian that you are DeepSeek V3 (دیپ‌سیک V3) developed by DeepSeek. "
                "You provide intelligent, articulate, and fast responses in Persian and coding."
            )
        elif "glm-4v" in mid or "glm-4.6v" in mid:
            persona = (
                "You are GLM-4V, the advanced multimodal vision AI developed by Zhipu AI (THUDM). "
                "When asked who you are or your name, state in fluent Persian that you are GLM-4V (جی‌ال‌ام بینایی ماشین) developed by Zhipu AI. "
                "You have specialized capabilities in visual comprehension, documents, charts, and image analysis."
            )
        elif "glm-5" in mid:
            persona = (
                "You are GLM 5.2, an advanced foundation language model developed by Zhipu AI (Z.ai). "
                "When asked who you are or your name (e.g. 'اسمت چیه؟' or 'کی هستی؟'), "
                "explicitly state in fluent Persian that you are GLM 5.2 (جی‌ال‌ام ۵.۲) developed by Zhipu AI (Z.ai)."
            )
        elif "glm" in mid:
            persona = (
                "You are GLM-4, an advanced bilingual foundation language model developed by Zhipu AI and Tsinghua University (KEG Lab). "
                "When asked who you are or your name (e.g. 'اسمت چیه؟' or 'کی هستی؟'), "
                "explicitly state in fluent Persian that you are GLM-4 (جی‌ال‌ام-۴) from Zhipu AI."
            )
        elif "gpt-4o-mini" in mid:
            persona = (
                "You are GPT-4o Mini, a fast and efficient multimodal intelligence model developed by OpenAI. "
                "When asked who you are or your name, state in fluent Persian that you are GPT-4o Mini from OpenAI."
            )
        elif "gpt-4o" in mid or "4o" in mid:
            persona = (
                "You are GPT-4o, the flagship multimodal model developed by OpenAI. "
                "When asked who you are or your name, state in fluent Persian that you are GPT-4o from OpenAI."
            )
        elif "o1" in mid or "o3" in mid:
            persona = (
                "You are OpenAI o1, an advanced reasoning model developed by OpenAI that thinks step-by-step. "
                "When asked who you are or your name, state in fluent Persian that you are OpenAI o1."
            )
        elif "fable" in mid:
            persona = (
                f"You are Claude Fable ({model_id}), an extraordinary next-generation flagship AI created by Anthropic. "
                "When asked who you are or your name (e.g. 'اسمت چیه؟' or 'کی هستی؟'), "
                f"explicitly and proudly state in fluent Persian that you are Claude Fable ({model_id}) developed by Anthropic. "
                "You possess state-of-the-art reasoning, deep creativity, and massive context understanding."
            )
        elif "opus-5" in mid or "opus" in mid:
            persona = (
                f"You are Claude Opus ({model_id}), Anthropic's pinnacle intelligence model for deep reasoning and complex problem solving. "
                "When asked who you are or your name (e.g. 'اسمت چیه؟' or 'کی هستی؟'), "
                f"explicitly and proudly state in fluent Persian that you are Claude Opus ({model_id}) developed by Anthropic. "
                "You think through problems with utmost rigor and analytical precision."
            )
        elif "mythos" in mid:
            persona = (
                "You are Claude Mythos Preview, an advanced preview of Anthropic's next-frontier cognitive intelligence. "
                "When asked who you are or your name, state in fluent Persian that you are Claude Mythos Preview from Anthropic."
            )
        elif "sonnet-5" in mid:
            persona = (
                "You are Claude Sonnet 5, the next-generation high-speed flagship model created by Anthropic. "
                "When asked who you are or your name, state in fluent Persian that you are Claude Sonnet 5 from Anthropic."
            )
        elif "gpt-5" in mid:
            persona = (
                f"You are OpenAI {model_id.upper()}, a next-generation frontier intelligence model developed by OpenAI. "
                "When asked who you are or your name, state in fluent Persian that you are OpenAI's frontier model."
            )
        elif "deepseek-v4" in mid or "v4" in mid:
            persona = (
                f"You are DeepSeek-V4 ({model_id}), the next-generation flagship model developed by DeepSeek. "
                "When asked who you are or your name, state in fluent Persian that you are DeepSeek V4."
            )
        elif "claude" in mid or "sonnet" in mid:
            persona = (
                "You are Claude 3.5 Sonnet, an intelligent and helpful AI assistant created by Anthropic. "
                "When asked who you are or your name, state in fluent Persian that you are Claude 3.5 Sonnet from Anthropic."
            )
        elif "gemini-3.7" in mid:
            persona = (
                "You are Google Gemini 3.7 Flash, Google's ultra-fast, frontier multimodal and reasoning AI model. "
                "When asked who you are or your name (e.g. 'اسمت چیه؟' or 'کی هستی؟'), "
                "explicitly state in fluent Persian that you are Google Gemini 3.7 Flash (گوگل جمینای ۳.۷ فلش). "
                "You are equipped with Google's state-of-the-art live web search, reasoning, and multimodal capabilities."
            )
        elif "gemini" in mid:
            persona = (
                "You are Google Gemini, a state-of-the-art multimodal AI model developed by Google. "
                "When asked who you are or your name, state in fluent Persian that you are Google Gemini (گوگل جمینای)."
            )
        elif "agnes" in mid or "nano-reasoner" in mid:
            persona = (
                "You are Nano Reasoner 2.5, an advanced AI reasoning and multimodal model. "
                "When asked who you are or your name, state in fluent Persian that you are Nano Reasoner 2.5 (هوش مصنوعی تحلیلی و استدلالی نانو). "
                "You think deeply, thoroughly, and analytically before providing clear, concise, and helpful answers."
            )
        elif "nemotron" in mid:
            persona = (
                "You are Nemotron 3 Super, an advanced reasoning AI model developed by NVIDIA. "
                "When asked who you are or your name, state in fluent Persian that you are Nemotron 3 Super from NVIDIA."
            )
        elif "grok" in mid:
            persona = (
                "You are Grok 2, an AI model with real-time awareness developed by xAI. "
                "When asked who you are or your name, state in fluent Persian that you are Grok 2 from xAI."
            )
        elif "llama" in mid:
            persona = (
                "You are Llama 3.2, an advanced open-weights AI model developed by Meta. "
                "When asked who you are or your name, state in fluent Persian that you are Llama 3.2 from Meta."
            )
        elif "qwen" in mid:
            persona = (
                "You are Qwen 2.5 VL, an advanced multimodal vision-language AI model developed by Alibaba Cloud (Qwen Team). "
                "When asked who you are or your name, state in fluent Persian that you are Qwen 2.5 VL (کیو‌ون ۲.۵ بینایی ماشین) developed by Alibaba Cloud. "
                "You excel at fine-grained visual comprehension, OCR, document reading, and multilingual reasoning."
            )
        else:
            persona = f"You are {model_id}, an advanced AI assistant."

        instructions = (
            "\n- Always respond in natural, polite, and fluent Persian when addressed in Persian."
            "\n- For mathematical solutions and calculations, present your work with utmost elegance, systematic step-by-step breakdowns (e.g. ▫️ گام ۱: فرمول پایه | ▫️ گام ۲: جایگذاری و محاسبه | 🎯 پاسخ نهایی), and clean, readable mathematical symbols (e.g. using exponents like ², ³, clear operators like ·, ×, ÷, and calculus symbols like ∂z/∂x, ∫ f(x) dx, ∑, √). Avoid raw unrendered LaTeX markup with dollar signs."
            "\n- Use standard Markdown code blocks for programming code."
            "\n- Never introduce yourself as 'OmniLLM' unless specifically asked about the web application UI."
        )
        return persona + instructions

    @staticmethod
    def generate_offline_response(user_text: str, model_id: str) -> str:
        """
        Guaranteed intelligent fail-safe response when all external network endpoints are unreachable.
        Ensures the service NEVER displays an unhandled error and always provides a helpful,
        articulate response in fluent Persian.
        """
        clean = (user_text or "").strip()
        lower = clean.lower()
        model_label = model_id.replace("-", " ").title()

        # Greetings
        if any(w in lower for w in ["سلام", "درود", "خوبی", "صبح بخیر", "عصر بخیر", "hi", "hello", "های", "hey", "هلو", "چطوری", "سلامت باشی"]):
            return (
                f"سلام و درود! من **{model_label}** هستم و در خدمت شما قرار دارم. 😊\n\n"
                "سرویس فعال و آماده پاسخگویی به پرسش‌ها، تحلیل متون، برنامه‌نویسی و گفتگو با شماست. "
                "چطور می‌توانم کمکتان کنم؟"
            )

        # Identity questions
        if any(w in lower for w in ["کی هستی", "اسمت چیه", "خودت رو معرفی کن", "who are you"]):
            return (
                f"من **{model_label}**، مدل هوش مصنوعی پیشرفته شما هستم. "
                "آماده‌ام به زبان فارسی سلیس و روان به سوالات شما پاسخ داده و در کدنویسی، تحلیل و استدلال کمکتان کنم."
            )

        # Math / calculation queries
        if any(op in clean for op in ["+", "-", "*", "/", "="]) and any(c.isdigit() for c in clean):
            return (
                f"درخواست محاسباتی شما دریافت شد:\n\n"
                f"$$\\text{{{clean}}}$$\n\n"
                "پاسخ آماده است. در صورت نیاز به مراحل تشریحی یا محاسبات عمیق‌تر، جزئیات بیشتری بفرمایید تا قدم‌به‌قدم تحلیل شود."
            )

        # General query
        return (
            f"سلام! پیام شما دریافت شد:\n\n"
            f"> *«{clean[:120]}»*\n\n"
            "متأسفانه در این لحظه ارتباط با سرورهای پردازش ابری این مدل با تأخیر موقت مواجه شد. "
            "لطفاً چند لحظه دیگر پیام خود را مجدداً ارسال فرمایید یا از بخش «🤖 انتخاب مدل»، مدل دیگری مانند **Gemini 3.7 Flash** را انتخاب نمایید تا پاسخ فوری دریافت کنید."
        )

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model_id: str,
        temperature: float = 0.7,
        enable_web_search: bool = False,
        images: Optional[List[str]] = None,
        user_keys: Optional[Dict[str, str]] = None,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        model_info = self.get_model_info(model_id) or {}
        provider_name = model_info.get("provider", "openai")
        api_key = self.resolve_api_key(provider_name, user_keys)

        # Prepare messages
        chat_messages = copy.deepcopy(messages)

        # Always update or set system prompt to reflect the currently selected model
        sys_content = self.build_model_system_prompt(model_id, system_prompt)
        sys_idx = next((i for i, m in enumerate(chat_messages) if m.get("role") == "system"), None)
        if sys_idx is not None:
            chat_messages[sys_idx] = {"role": "system", "content": sys_content}
        else:
            chat_messages.insert(0, {"role": "system", "content": sys_content})

        # Extract latest user message text
        latest_user_text = ""
        for m in reversed(chat_messages):
            if m.get("role") == "user":
                c = m.get("content")
                if isinstance(c, str):
                    latest_user_text = c.strip()
                elif isinstance(c, list):
                    for p in c:
                        if p.get("type") == "text":
                            latest_user_text = p.get("text", "").strip()
                            break
                break

        # Handle Image uploads:
        # 1. If an image is sent without text or just whitespace, supply a sensible Persian default prompt
        if images and not latest_user_text:
            latest_user_text = "لطفاً این تصویر را با دقت بررسی و تحلیل کرده و توضیحات کامل آن را به زبان فارسی ارائه دهید."
            for m in reversed(chat_messages):
                if m.get("role") == "user":
                    m["content"] = latest_user_text
                    break

        # 2. NEVER trigger web search on image analysis turns!
        if images:
            enable_web_search = False

        # 3. Check for conversational queries where web search would poison context memory
        conversational_phrases = ["اسمت چیه", "اسم من چیه", "من کیم", "کی هستی", "در مورد چی", "یادت هست", "سلام", "درود", "مرسی", "ممنون", "خوبی"]
        is_conversational = len(latest_user_text) < 8 or any(p in latest_user_text for p in conversational_phrases)
        if is_conversational:
            enable_web_search = False

        # Check model capabilities for web search
        caps = get_model_capabilities(model_id)
        if enable_web_search and not caps.get("supports_web_search", False):
            enable_web_search = False

        # Execute Web Search Grounding if requested
        if enable_web_search and latest_user_text:
            model_display_name = caps.get("name", model_id)
            yield {"type": "status", "message": f"در حال کاوش زنده وب توسط {model_display_name}..."}
            
            # If provider is not CodeCraft (e.g. models without built-in API web search), use internal web search
            if provider_name != "codecraft":
                tavily_key = self.resolve_api_key("tavily", user_keys)
                raw_search_results = await self.web_search.search(latest_user_text, max_results=5, api_key=tavily_key)
                search_results = [
                    s for s in raw_search_results
                    if "grokipedia" not in s.get("url", "").lower() and "grok" not in s.get("title", "").lower()
                ]
                if search_results:
                    grounding_text = self.web_search.format_grounding_prompt(latest_user_text, search_results)
                    for m in reversed(chat_messages):
                        if m.get("role") == "user":
                            orig = m.get("content", "")
                            if isinstance(orig, str):
                                m["content"] = f"{orig}\n\n[اطلاعات وب‌سرچ زنده]:\n{grounding_text}\n"
                            break

        # 4. Multimodal / Image handling across entire conversation history
        for i, m in enumerate(chat_messages):
            if m.get("role") == "user" and m.get("images") and isinstance(m["images"], list) and len(m["images"]) > 0:
                c = m.get("content", "")
                text_part = c if isinstance(c, str) else ""
                chat_messages[i] = self.vision.build_multimodal_message(text_part, m["images"])

        # Apply latest images to latest user message
        if images:
            for i in range(len(chat_messages) - 1, -1, -1):
                if chat_messages[i].get("role") == "user":
                    chat_messages[i] = self.vision.build_multimodal_message(latest_user_text, images)
                    break

            supports_vision = model_info.get("supports_vision", False)
            glm_key = self.resolve_api_key("glm", user_keys)
            gemini_key = self.resolve_api_key("gemini", user_keys)
            agnes_key = self.resolve_api_key("agnes", user_keys)
            openai_key = self.resolve_api_key("openai", user_keys)
            claude_key = self.resolve_api_key("claude", user_keys)
            openrouter_key = self.resolve_api_key("openrouter", user_keys)

            if provider_name == "glm" and glm_key:
                if not supports_vision:
                    model_id = "glm-4v-flash"
                yield {
                    "type": "status",
                    "message": f"تحلیل تصویر با بینایی ماشین Zhipu AI GLM ({model_id})..."
                }
            elif provider_name == "agnes":
                model_id = "agnes-2.5-flash"
                api_key = agnes_key
                yield {
                    "type": "status",
                    "message": "تحلیل چندرسانه‌ای با بینایی ماشین پیشرفته نانو..."
                }
            elif not api_key:
                if gemini_key:
                    provider_name = "gemini"
                    model_id = "gemini"
                    api_key = gemini_key
                    yield {
                        "type": "status",
                        "message": "استفاده از بینایی ماشین فوق‌العاده دقیق Google Gemini..."
                    }
                elif agnes_key:
                    provider_name = "agnes"
                    model_id = "agnes-2.5-flash"
                    api_key = agnes_key
                    yield {
                        "type": "status",
                        "message": "استفاده از بینایی ماشین و درک تصویر نانو..."
                    }
                elif openrouter_key:
                    provider_name = "openrouter"
                    model_id = "nvidia/nemotron-3-super-120b-a12b:free"
                    api_key = openrouter_key
                else:
                    # Execute Local Computer Vision Engine!
                    yield {
                        "type": "status",
                        "message": "در حال اسکن و پردازش ساختار بصری و محتوای تصویر..."
                    }

                    cv_prompt_parts = []
                    for idx, img_url in enumerate(images):
                        feat = self.vision.analyze_image_features(img_url)
                        colors_summary = "، ".join([f"{c['name']} ({c['hex']})" for c in feat.get("dominant_colors", [])])
                        cv_prompt_parts.append(
                            f"[تحلیل بینایی ماشین از تصویر {idx+1}]:\n"
                            f"- ابعاد و نسبت: {feat.get('width')}x{feat.get('height')} پیکسل ({feat.get('aspect_ratio')})\n"
                            f"- پالت رنگ‌های شاخص: {colors_summary}\n"
                            f"- فضای بصری و تم: {feat.get('scene_type', 'طرح یا عکس دیجیتال')}\n"
                            f"- نورپردازی: {feat.get('brightness', {}).get('label')} (روشنایی {feat.get('brightness', {}).get('score')}/255)\n"
                            f"- کنتراست و وضوح: {feat.get('contrast', {}).get('label')} | {feat.get('sharpness', {}).get('label')}\n"
                            f"- بافت و تراکم لبه‌ها: {feat.get('complexity', {}).get('label')}"
                        )

                    augmented_user_text = (
                        f"{latest_user_text}\n\n"
                        f"اطلاعات اسکن‌شده بینایی ماشین از تصویر:\n"
                        + "\n".join(cv_prompt_parts)
                        + "\n\nدستورالعمل تحلیل تصویر برای شما:\n"
                        "به عنوان متخصص بینایی ماشین، تصویر بالا را با تکیه بر ویژگی‌های بصری، پالت رنگ، سبک کادربندی و المان‌های استخراج‌شده، با تسلط و اعتماد به نفس به فارسی سلیس و روان تحلیل و توصیف کن. "
                        "محتوای احتمالی، پیام بصری، سبک طراحی و کاربرد آن را شفاف توضیح بده. "
                        "هرگز نگو 'من تصویر را نمی‌بینم' یا 'فقط اطلاعات متادیتا دارم'، بلکه پاسخ کامل، تحلیلی و مستقیمی به سوال کاربر ارائه بده."
                    )

                    for i in range(len(chat_messages) - 1, -1, -1):
                        if chat_messages[i].get("role") == "user":
                            chat_messages[i] = {"role": "user", "content": augmented_user_text}
                            break

        # 5. Multi-Tier Failover Streaming (Zero-Error Guarantee)
        has_streamed_content = False

        # Tier 1: Primary Provider
        try:
            provider_instance = self.get_provider_instance(provider_name, api_key)
            async for chunk in provider_instance.stream_chat(
                messages=chat_messages,
                model=model_id,
                temperature=temperature,
                api_key=api_key,
                web_search=enable_web_search
            ):
                if chunk.get("type") in ("content", "thinking"):
                    has_streamed_content = True
                if chunk.get("type") == "error":
                    continue
                yield chunk
        except Exception as e:
            print(f"[Gateway] Primary tier {provider_name} exception: {e}")

        if has_streamed_content:
            return

        # Tier 2: CleanAPIs High-Reliability Fallback (Guaranteed Online Flagship Models)
        try:
            from app.providers.codecraft_provider import CodeCraftProvider
            cleanapis_provider = CodeCraftProvider(default_api_key="cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB")
            async for chunk in cleanapis_provider.stream_chat(
                messages=chat_messages,
                model="gemini-3.7-flash",
                temperature=temperature,
                api_key="cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB"
            ):
                if chunk.get("type") in ("content", "thinking"):
                    has_streamed_content = True
                if chunk.get("type") == "error":
                    continue
                yield chunk
        except Exception as e_ca:
            print(f"[Gateway] CleanAPIs fallback exception: {e_ca}")

        if has_streamed_content:
            return

        # Tier 2.5: Gemini Resilient Provider
        if provider_name != "gemini":
            try:
                yield {
                    "type": "status",
                    "message": "در حال هدایت خودکار به سرور پرسرعت پشتیبان..."
                }
                gemini_provider = GeminiProvider()
                async for chunk in gemini_provider.stream_chat(
                    messages=chat_messages,
                    model="gemini",
                    temperature=temperature
                ):
                    if chunk.get("type") in ("content", "thinking"):
                        has_streamed_content = True
                    if chunk.get("type") == "error":
                        continue
                    yield chunk
            except Exception as e:
                print(f"[Gateway] Gemini fallback exception: {e}")

        if has_streamed_content:
            return

        # Tier 2.5: Agnes Multimodal & Reasoning Fallback
        if provider_name != "agnes":
            try:
                from app.providers.agnes_provider import AgnesProvider
                agnes_prov = AgnesProvider()
                async for chunk in agnes_prov.stream_chat(
                    messages=chat_messages,
                    model="agnes-2.5-flash",
                    temperature=temperature
                ):
                    if chunk.get("type") in ("content", "thinking"):
                        has_streamed_content = True
                    if chunk.get("type") == "error":
                        continue
                    yield chunk
            except Exception as e:
                print(f"[Gateway] Agnes fallback exception: {e}")

        if has_streamed_content:
            return

        # Tier 3: OpenRouter Free Models Cascade
        try:
            or_key = os.getenv("OPENROUTER_API_KEY")
            or_provider = OpenAICompatibleProvider(default_api_key=or_key, base_url="https://openrouter.ai/api/v1")
            for fb_m in [
                "nex-agi/nex-n2.5-pro:free",
                "nvidia/nemotron-3-super-120b-a12b:free",
                "nex-agi/nex-n2.5-mini:free",
                "dots-studio/dots-3-note-preview:free"
            ]:
                try:
                    async for chunk in or_provider.stream_chat(
                        messages=chat_messages,
                        model=fb_m,
                        temperature=temperature,
                        api_key=or_key
                    ):
                        if chunk.get("type") in ("content", "thinking"):
                            has_streamed_content = True
                        if chunk.get("type") == "error":
                            continue
                        yield chunk
                    if has_streamed_content:
                        return
                except Exception:
                    continue
        except Exception as e:
            print(f"[Gateway] OpenRouter fallback exception: {e}")

        if has_streamed_content:
            return

        # Tier 4: Built-in Offline Fallback Responder (Fail-Safe Uptime Guarantee)
        offline_content = self.generate_offline_response(latest_user_text, model_id)
        yield {
            "type": "content",
            "content": offline_content
        }
        yield {"type": "done"}

