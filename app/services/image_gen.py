import os
import time
import uuid
import base64
import random
import urllib.parse
import httpx
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.config import BASE_DIR
from app.providers.gemini_provider import GeminiKeyPool
from app.services.puter_image import PuterImageService

GENERATED_DIR = BASE_DIR / "app" / "static" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


class ImageGenService:
    """
    Dedicated AI Image Generation Service.
    Generates genuine, high-quality, photorealistic images via:
    1. Google Nano Banana 1, 2, Pro via Puter.com API
    2. FLUX.1 / SDXL Diffusion Engine (free, reliable, instant)
    3. Prompt translation & enhancement to English visual descriptions
    4. Direct Google Imagen / OpenRouter Imagen (when paid keys are provided)
    """

    SUPPORTED_MODELS = {
        "agnes-image-2.5-flash": "ادیت عکس نانو بنانا 🍌",
        "nano-banana": "Google Nano Banana (سریع و باکیفیت)",
        "nano-banana-2": "Google Nano Banana 2 (Gemini 3.1 Flash Image)",
        "nano-banana-pro": "Google Nano Banana Pro (Gemini 3 Pro Image)",
        "sdxl-lightning": "SDXL Lightning (رایگان Puter)",
        "gemini": "Google Gemini / Nano Banana Studio",
        "flux": "FLUX.1 Ultra (تصویرسازی پیشرفته)",
        "gemini-2.5-flash-image": "Google Gemini 2.5 Flash Image",
        "gemini-3.1-flash-image": "Google Gemini 3.1 Flash Image",
    }

    @staticmethod
    def _save_image_bytes(raw_bytes: bytes, prefix: str = "ai_image", ext: str = "jpg") -> str:
        """
        Saves binary image data to static/generated/ on local disk.
        Returns the web-accessible relative URL.
        """
        try:
            filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
            filepath = GENERATED_DIR / filename
            filepath.write_bytes(raw_bytes)
            return f"/static/generated/{filename}"
        except Exception as e:
            print(f"[ImageGenService] Error saving image file: {e}")
            return ""

    @staticmethod
    def _save_base64_image(base64_data: str, prefix: str = "ai_image") -> str:
        """
        Decodes base64 image data and saves it to static/generated/ on local disk.
        """
        try:
            ext = "png"
            if "data:image/jpeg" in base64_data:
                ext = "jpg"
            elif "data:image/webp" in base64_data:
                ext = "webp"

            if "base64," in base64_data:
                base64_data = base64_data.split("base64,")[1]
            raw_bytes = base64.b64decode(base64_data.strip())
            return ImageGenService._save_image_bytes(raw_bytes, prefix=prefix, ext=ext)
        except Exception as e:
            print(f"[ImageGenService] Error saving base64 image: {e}")
            return f"data:image/png;base64,{base64_data}"

    @classmethod
    async def _enhance_and_translate_prompt(
        cls,
        prompt: str,
        openrouter_key: Optional[str] = None
    ) -> str:
        """
        Translates Persian prompts and enriches brief queries into rich,
        highly detailed English visual descriptions suited for diffusion models.
        """
        clean = prompt.strip()
        # Strip common command prefixes
        for p in [
            "عکس بساز از", "عکس بساز", "تصویر بساز از", "تصویر بساز",
            "یک عکس از", "یک تصویر از", "یک عکس", "یک تصویر",
            "عکس از", "تصویر از", "عکس", "تصویر", "نقاشی از", "نقاشی",
            "تولید عکس از", "تولید عکس", "تولید تصویر از", "تولید تصویر",
            "با جمینای بساز", "/gemini_image", "/gemini_img", "/image", "/img",
            "generate an image of", "create a photo of", "photo of", "picture of", "draw"
        ]:
            if clean.lower().startswith(p.lower()):
                clean = clean[len(p):].lstrip(": ").strip()
                break

        # Strip common Persian command suffixes
        for s in [
            "تولید کن لطفا", "تولید کن", "تولید کنید",
            "بساز لطفا", "بساز", "بسازید",
            "بکش لطفا", "بکش", "بکشید",
            "ایجاد کن", "ایجاد کنید", "طراحی کن", "طراحی کنید"
        ]:
            if clean.endswith(s):
                clean = clean[:-len(s)].rstrip(": ").strip()
                break

        if not clean:
            clean = "A stunning cinematic landscape with beautiful lighting"

        # Check if the prompt already looks like detailed English
        is_ascii = all(ord(c) < 128 for c in clean)
        if is_ascii and len(clean.split()) >= 6:
            return clean

        # Use fast, free LLM (OpenRouter Nex N2.5 Pro) to translate and enrich prompt
        or_key = openrouter_key or os.getenv("OPENROUTER_API_KEY")
        if or_key:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
                    payload = {
                        "model": "nex-agi/nex-n2.5-pro:free",
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are an expert AI prompt engineer for photorealistic diffusion models (FLUX/SDXL). "
                                    "Translate any non-English prompt to English and optimize it with visual details, "
                                    "lighting, atmosphere, and authentic textures. "
                                    "Keep it under 35 words. "
                                    "Output ONLY the English prompt. Do not include quotes, explanations, or prefixes."
                                )
                            },
                            {
                                "role": "user",
                                "content": clean
                            }
                        ],
                        "max_tokens": 100,
                        "temperature": 0.5
                    }
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {or_key}"},
                        json=payload
                    )
                    if resp.status_code == 200:
                        msg = resp.json().get("choices", [{}])[0].get("message", {})
                        content_raw = msg.get("content") or msg.get("reasoning_content") or ""
                        if isinstance(content_raw, str) and content_raw.strip():
                            enhanced = content_raw.strip().strip('"\'`')
                            if len(enhanced) > 5 and all(ord(c) < 128 for c in enhanced):
                                return enhanced
            except Exception as e:
                print(f"[ImageGenService] Prompt translation error: {e}")

        # Smart bilingual keyword mapping fallback
        keyword_map = [
            ("تهران", "Tehran"),
            ("ایران", "Iran"),
            ("مردم", "people"),
            ("خیابان", "street"),
            ("ماشین", "car"),
            ("طبیعت", "nature"),
            ("کوه", "mountains"),
            ("دریا", "sea"),
            ("غروب", "sunset"),
            ("شهر", "city"),
            ("زن", "woman"),
            ("مرد", "man"),
            ("دختر", "girl"),
            ("پسر", "boy"),
            ("کودک", "child"),
            ("گربه", "cat"),
            ("سگ", "dog"),
            ("جنگل", "forest"),
        ]
        mapped_words = []
        temp_clean = clean
        for fa_w, en_w in keyword_map:
            if fa_w in temp_clean:
                mapped_words.append(en_w)
                temp_clean = temp_clean.replace(fa_w, " ")
        subject_str = " ".join(mapped_words) if mapped_words else clean

        enhanced_fallback = f"A high quality, authentic, detailed realistic photograph of {subject_str}, professional photography, 35mm lens, natural lighting, sharp focus, 4k"
        return enhanced_fallback

    @classmethod
    async def _generate_via_pollinations(
        cls,
        english_prompt: str,
        original_prompt: str,
        seed: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generates real, high-resolution raster images using Pollinations AI (FLUX / Turbo models).
        Free, reliable, and produces actual photorealistic JPEG images.
        """
        if seed is None:
            seed = random.randint(1000, 999999)

        encoded_prompt = urllib.parse.quote(english_prompt)

        # Try fast turbo first (4s latency), then flux, then default
        endpoints = [
            f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=turbo&nologo=true&seed={seed}",
            f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true&seed={seed}",
            f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={seed}",
        ]

        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0), follow_redirects=True) as client:
            for url in endpoints:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.content) > 2000:
                        content_type = resp.headers.get("content-type", "")
                        ext = "png" if "png" in content_type else "jpg"
                        local_url = cls._save_image_bytes(resp.content, prefix="flux_image", ext=ext)
                        if local_url:
                            model_label = "FLUX.1 Ultra (تصویرسازی واقعی)"
                            return {
                                "status": "success",
                                "engine": "flux",
                                "model_name": model_label,
                                "image_url": local_url,
                                "prompt": original_prompt,
                                "english_prompt": english_prompt,
                                "is_fallback": False,
                                "description": f"تصویر تولید شده با مدل هوش مصنوعی {model_label}"
                            }
                except Exception as e:
                    print(f"[ImageGenService] Pollinations attempt error: {e}")
                    continue

        return None

    @classmethod
    async def generate_image(
        cls,
        prompt: str,
        model: str = "gemini",
        width: int = 1024,
        height: int = 1024,
        enhance: bool = True,
        seed: Optional[int] = None,
        history_messages: Optional[List[Dict[str, Any]]] = None,
        api_key: Optional[str] = None,
        openrouter_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for generating authentic, photorealistic images.
        """
        clean_prompt = prompt.strip()
        if not clean_prompt:
            clean_prompt = "یک تصویر دیدنی و جذاب از طبیعت و نورپردازی زیبا"

        # 1. Translate & enhance user prompt into rich English visual prompt
        english_prompt = await cls._enhance_and_translate_prompt(
            prompt=clean_prompt,
            openrouter_key=openrouter_key
        )

        # 1.5 Check if Agnes / GPT image model is requested
        if any(k in model.lower() for k in ["agnes", "gpt-image", "gpt_image"]):
            from app.services.agnes_image import AgnesImageService
            agnes = AgnesImageService(api_key=api_key)
            ratio = "1:1"
            if width > height * 1.3:
                ratio = "16:9"
            elif height > width * 1.3:
                ratio = "9:16"
            res = await agnes.generate_image(prompt=clean_prompt, ratio=ratio, size="1K")
            if res.get("success"):
                return {
                    "status": "success",
                    "engine": "nano_banana",
                    "model_name": "ادیت عکس نانو بنانا 🍌",
                    "image_url": res["url"],
                    "prompt": clean_prompt,
                    "english_prompt": english_prompt,
                    "is_fallback": False,
                    "description": "تصویر تولید شده با مدل فوق‌حرفه‌ای نانو بنانا"
                }

        # 2. Check if Puter token is configured or if user specifically requested a Banana/Nano model
        is_banana_request = any(k in model.lower() for k in ["banana", "nano", "sdxl", "puter"])
        puter_token = PuterImageService.get_token()

        if is_banana_request or puter_token:
            banana_model = "nano-banana"
            if "nano-banana-pro" in model.lower() or "pro" in model.lower():
                banana_model = "nano-banana-pro"
            elif "nano-banana-2" in model.lower() or "2" in model.lower():
                banana_model = "nano-banana-2"
            elif "sdxl" in model.lower():
                banana_model = "sdxl-lightning"

            aspect_ratio = "1:1"
            if width > height * 1.3:
                aspect_ratio = "16:9"
            elif height > width * 1.3:
                aspect_ratio = "9:16"

            puter_res = await PuterImageService.generate_image(
                prompt=clean_prompt,
                model=banana_model,
                aspect_ratio=aspect_ratio,
                resolution="2K" if "pro" in banana_model else "1K"
            )
            if puter_res.get("status") == "success" and puter_res.get("image_url"):
                return puter_res

        # 3. Check if user provided their own paid OpenRouter or Google key for Imagen
        pool = GeminiKeyPool.get_instance()
        node = pool.select_best_node(user_override_key=api_key)

        # 4. Attempt direct Google Generative Language API if key provided
        if node and api_key:
            for d_model in ["gemini-2.5-flash-image", "gemini-3.1-flash-image"]:
                try:
                    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{d_model}:generateContent?key={node.key}"
                    payload = {
                        "contents": [{"parts": [{"text": english_prompt}]}],
                        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
                    }
                    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                        resp = await client.post(endpoint, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            for p in parts:
                                if "inlineData" in p and p["inlineData"].get("data"):
                                    b64 = p["inlineData"]["data"]
                                    local_url = cls._save_base64_image(b64, prefix="gemini")
                                    return {
                                        "status": "success",
                                        "engine": "gemini",
                                        "model_name": f"Google Gemini Imagen ({d_model})",
                                        "image_url": local_url,
                                        "prompt": clean_prompt,
                                        "english_prompt": english_prompt,
                                        "is_fallback": False,
                                        "description": ""
                                    }
                except Exception as e:
                    print(f"[ImageGenService] Direct Google Imagen attempt error: {e}")

        # 4.5 Fallback to Nano Banana (Agnes AI) Image Generation Engine
        try:
            from app.services.agnes_image import AgnesImageService
            agnes = AgnesImageService()
            agnes_res = await agnes.generate_image(prompt=clean_prompt, size="1K", ratio="1:1")
            if agnes_res.get("success") and agnes_res.get("url"):
                return {
                    "status": "success",
                    "engine": "agnes",
                    "model_name": "ادیت عکس نانو بنانا 🍌",
                    "image_url": agnes_res["url"],
                    "prompt": clean_prompt,
                    "english_prompt": english_prompt,
                    "is_fallback": True,
                    "description": ""
                }
        except Exception as e:
            print(f"[ImageGenService] Agnes Image fallback error: {e}")

        # 5. Generate via reliable, high-quality FLUX / Diffusion engine
        flux_result = await cls._generate_via_pollinations(
            english_prompt=english_prompt,
            original_prompt=clean_prompt,
            seed=seed
        )
        if flux_result:
            return flux_result

        # 5. If all attempts failed, return informative error message
        return {
            "status": "error",
            "engine": "image_gen",
            "model_name": "AI Image Generator",
            "image_url": "",
            "prompt": clean_prompt,
            "is_fallback": False,
            "error_message": "سرویس تولید تصویر در حال حاضر در دسترس نیست. لطفاً اتصال اینترنت را بررسی و مجدداً تلاش نمایید."
        }

