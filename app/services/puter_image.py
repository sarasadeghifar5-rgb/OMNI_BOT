import os
import time
import uuid
import base64
import random
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx
from app.config import BASE_DIR

GENERATED_DIR = BASE_DIR / "app" / "static" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


class PuterImageService:
    """
    Service for generating photorealistic and artistic images using Puter.com API.
    Provides direct access to Google Nano Banana models:
      - google/nano-banana (Nano Banana - Fast, highly detailed)
      - google/nano-banana-2 (Nano Banana 2 - Powered by Gemini 3.1 Flash Image)
      - google/nano-banana-pro (Nano Banana Pro - Powered by Gemini 3 Pro Image, up to 4K)
      - workers-ai:bytedance/stable-diffusion-xl-lightning (Cost 0 - 100% Free)
    """

    PUTER_API_URL = "https://api.puter.com/drivers/call"

    MODEL_MAPPINGS = {
        "nano-banana": "google/nano-banana",
        "nano-banana-1": "google/nano-banana",
        "nano-banana-2": "google/nano-banana-2",
        "nano-banana-pro": "google/nano-banana-pro",
        "google/nano-banana": "google/nano-banana",
        "google/nano-banana-2": "google/nano-banana-2",
        "google/nano-banana-pro": "google/nano-banana-pro",
        "sdxl": "workers-ai:bytedance/stable-diffusion-xl-lightning",
        "sdxl-lightning": "workers-ai:bytedance/stable-diffusion-xl-lightning",
        "free-sdxl": "workers-ai:bytedance/stable-diffusion-xl-lightning",
    }

    MODEL_LABELS = {
        "google/nano-banana": "Google Nano Banana (سریع و خلاقانه)",
        "google/nano-banana-2": "Google Nano Banana 2 (Gemini 3.1 Flash Image)",
        "google/nano-banana-pro": "Google Nano Banana Pro (Gemini 3 Pro Image)",
        "workers-ai:bytedance/stable-diffusion-xl-lightning": "SDXL Lightning (رایگان Puter)",
    }

    @classmethod
    def get_token(cls, user_token: Optional[str] = None) -> str:
        """Resolve Puter token from user parameter or environment"""
        if user_token and user_token.strip():
            return user_token.strip()
        env_token = os.getenv("PUTER_AUTH_TOKEN") or os.getenv("PUTER_API_KEY")
        if env_token and env_token.strip():
            return env_token.strip()
        # Default fallback token provided by user
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InYyIn0.eyJ0IjoidCIsInYiOiIyIiwidG9rZW5fdWlkIjoiMDI3OGMyNDItN2VhMi00NjQ1LTg3MGQtZjIwNmM4OTZiMDA3IiwidXUiOiJObHlHejV3eVNvcXl2eGZIajJaSElBPT0iLCJzdSI6IncrV2pTQ1c5UXMyMUZabktKS3FYZkE9PSIsImFpIjoiTmx5R3o1d3lTb3F5dnhmSGoyWkhJQT09IiwiZnVsbF9hY2Nlc3MiOnRydWUsImlhdCI6MTc5MDA5NzEwNn0.N_ne3_qUVEm1-XGUxjGFAUtTJhY_yrVjVr7ShvU3X4I"

    @staticmethod
    def _save_image_bytes(raw_bytes: bytes, prefix: str = "banana", ext: str = "jpg") -> str:
        """Save raw bytes to disk and return relative web path"""
        try:
            filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
            filepath = GENERATED_DIR / filename
            filepath.write_bytes(raw_bytes)
            return f"/static/generated/{filename}"
        except Exception as e:
            print(f"[PuterImageService] Error saving image: {e}")
            return ""

    @staticmethod
    def _save_base64_image(base64_data: str, prefix: str = "banana") -> str:
        """Decode base64 string and save to disk"""
        try:
            ext = "png"
            if "data:image/jpeg" in base64_data or "data:image/jpg" in base64_data:
                ext = "jpg"
            elif "data:image/webp" in base64_data:
                ext = "webp"

            if "base64," in base64_data:
                base64_data = base64_data.split("base64,")[1]
            raw_bytes = base64.b64decode(base64_data.strip())
            return PuterImageService._save_image_bytes(raw_bytes, prefix=prefix, ext=ext)
        except Exception as e:
            print(f"[PuterImageService] Error decoding base64: {e}")
            return base64_data

    @classmethod
    async def translate_and_enhance_prompt(cls, prompt: str) -> str:
        """
        Translates Persian prompts and enriches brief queries into rich English visual prompts.
        """
        clean = prompt.strip()
        for p in [
            "/banana", "/nano_banana", "/nano", "/gemini_image", "/image", "/img",
            "عکس بساز از", "عکس بساز", "تصویر بساز از", "تصویر بساز",
            "یک عکس از", "یک تصویر از", "یک عکس", "یک تصویر",
            "عکس از", "تصویر از", "عکس", "تصویر", "نقاشی از", "نقاشی",
            "تولید عکس از", "تولید عکس", "تولید تصویر از", "تولید تصویر",
            "با نانو بنانا بساز", "با نانو موز بساز", "با جمینای بساز"
        ]:
            if clean.lower().startswith(p.lower()):
                clean = clean[len(p):].lstrip(": ").strip()
                break

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
            clean = "A breathtaking cinematic vista with soft morning golden hour light"

        # Check if already detailed English
        is_ascii = all(ord(c) < 128 for c in clean)
        if is_ascii and len(clean.split()) >= 6:
            return clean

        # Fast bilingual dictionary for Persian terms
        fa_en_dict = [
            ("تهران", "Tehran"), ("ایران", "Iran"), ("موز", "banana"),
            ("فضانورد", "astronaut"), ("فضا", "outer space"), ("سیاره", "planet"),
            ("مریخ", "Mars"), ("ماه", "Moon"), ("زمین", "Earth"),
            ("گربه", "cat"), ("سگ", "dog"), ("شیر", "lion"), ("ببر", "tiger"),
            ("پرنده", "bird"), ("اسب", "horse"), ("ماشین", "futuristic sports car"),
            ("موتور", "motorcycle"), ("هواپیما", "airplane"), ("شهر", "cityscape"),
            ("آینده‌نگرانه", "futuristic cyberpunk"), ("سایبرپانک", "cyberpunk"),
            ("خیابان", "street"), ("دریا", "ocean"), ("ساحل", "beach"),
            ("کوه", "majestic mountains"), ("جنگل", "lush forest"), ("درخت", "tree"),
            ("گل", "flowers"), ("غروب", "dramatic sunset"), ("طلوع", "sunrise"),
            ("زن", "beautiful woman"), ("مرد", "handsome man"), ("کودک", "child"),
            ("پسر", "boy"), ("دختر", "girl"), ("لبخند", "smiling"),
            ("روشنایی نئونی", "neon glowing lights"), ("واقع‌گرایانه", "hyperrealistic"),
            ("سینمایی", "cinematic lighting, 8k resolution"), ("کارتونی", "pixar 3d animation style"),
            ("انیمه", "anime aesthetic studio ghibli"), ("نقاشی رنگ روغن", "oil painting masterpiece")
        ]

        mapped = []
        temp = clean
        for fa, en in fa_en_dict:
            if fa in temp:
                mapped.append(en)
                temp = temp.replace(fa, " ")

        subject = ", ".join(mapped) if mapped else clean
        return f"A highly detailed, photorealistic, professional masterpiece of {subject}, 8k resolution, cinematic lighting, dramatic atmosphere, octane render, sharp focus"

    @classmethod
    async def generate_image(
        cls,
        prompt: str,
        model: str = "nano-banana",
        aspect_ratio: str = "1:1",
        resolution: str = "1K",
        output_format: str = "jpg",
        user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for generating image with Google Nano Banana via Puter.
        """
        token = cls.get_token(user_token)
        target_model = cls.MODEL_MAPPINGS.get(model.lower(), "google/nano-banana")
        english_prompt = await cls.translate_and_enhance_prompt(prompt)

        # Allowed aspect ratios
        valid_ratios = ["1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2", "21:9"]
        selected_ratio = aspect_ratio if aspect_ratio in valid_ratios else "1:1"

        # Build args based on model type
        args: Dict[str, Any] = {
            "prompt": english_prompt,
            "model": target_model,
        }

        # Model specific options
        if "nano-banana" in target_model:
            args["aspect_ratio"] = selected_ratio
            args["output_format"] = output_format
            if "nano-banana-2" in target_model or "nano-banana-pro" in target_model:
                args["resolution"] = resolution if resolution in ["1K", "2K", "4K"] else "1K"

        payload = {
            "interface": "puter-image-generation",
            "driver": "ai-image",
            "test_mode": False,
            "method": "generate",
            "args": args,
            "auth_token": token
        }

        headers = {
            "Content-Type": "application/json;actually=json",
            "Authorization": f"Bearer {token}"
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
                resp = await client.post(cls.PUTER_API_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") and data.get("result"):
                        result_val = data["result"]
                        image_url = ""
                        # If result is URL
                        if isinstance(result_val, str) and (result_val.startswith("http://") or result_val.startswith("https://")):
                            try:
                                img_resp = await client.get(result_val, timeout=30.0)
                                if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                                    ext = "png" if "png" in result_val else "jpg"
                                    image_url = cls._save_image_bytes(img_resp.content, prefix="banana", ext=ext)
                            except Exception as dl_err:
                                print(f"[PuterImageService] Direct download failed, using remote URL: {dl_err}")
                            if not image_url:
                                image_url = result_val

                        # If result is base64 Data URL
                        elif isinstance(result_val, str) and (result_val.startswith("data:image/") or len(result_val) > 200):
                            image_url = cls._save_base64_image(result_val, prefix="banana")

                        if image_url:
                            model_label = cls.MODEL_LABELS.get(target_model, target_model)
                            return {
                                "status": "success",
                                "engine": "puter_nano_banana",
                                "model_id": target_model,
                                "model_name": model_label,
                                "image_url": image_url,
                                "prompt": prompt,
                                "english_prompt": english_prompt,
                                "aspect_ratio": selected_ratio,
                                "resolution": resolution,
                                "is_fallback": False
                            }
        except Exception as e:
            print(f"[PuterImageService] Primary Nano Banana generation error: {e}")

        # Fallback 1: Try 100% free Puter SDXL Lightning
        if target_model != "workers-ai:bytedance/stable-diffusion-xl-lightning":
            try:
                fallback_payload = {
                    "interface": "puter-image-generation",
                    "driver": "ai-image",
                    "test_mode": False,
                    "method": "generate",
                    "args": {
                        "prompt": english_prompt,
                        "model": "workers-ai:bytedance/stable-diffusion-xl-lightning"
                    },
                    "auth_token": token
                }
                async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
                    resp = await client.post(cls.PUTER_API_URL, json=fallback_payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("success") and data.get("result"):
                            local_url = cls._save_base64_image(data["result"], prefix="banana_sdxl")
                            if local_url:
                                return {
                                    "status": "success",
                                    "engine": "puter_sdxl",
                                    "model_id": "sdxl-lightning",
                                    "model_name": "SDXL Lightning (رایگان Puter)",
                                    "image_url": local_url,
                                    "prompt": prompt,
                                    "english_prompt": english_prompt,
                                    "aspect_ratio": selected_ratio,
                                    "is_fallback": True
                                }
            except Exception as e2:
                print(f"[PuterImageService] SDXL fallback error: {e2}")

        # Fallback 1.5: Try Puter Stable Diffusion XL Base (Free)
        try:
            fb_payload2 = {
                "interface": "puter-image-generation",
                "driver": "ai-image",
                "test_mode": False,
                "method": "generate",
                "args": {
                    "prompt": english_prompt,
                    "model": "@cf/stabilityai/stable-diffusion-xl-base-1.0"
                },
                "auth_token": token
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
                resp = await client.post(cls.PUTER_API_URL, json=fb_payload2, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") and data.get("result"):
                        local_url = cls._save_base64_image(data["result"], prefix="banana_sdxl_base")
                        if local_url:
                            return {
                                "status": "success",
                                "engine": "puter_sdxl_base",
                                "model_id": "sdxl-base",
                                "model_name": "SDXL Base (رایگان Puter)",
                                "image_url": local_url,
                                "prompt": prompt,
                                "english_prompt": english_prompt,
                                "aspect_ratio": selected_ratio,
                                "is_fallback": True
                            }
        except Exception as e2_base:
            print(f"[PuterImageService] SDXL Base fallback error: {e2_base}")

        # Fallback 2: Free Pollinations FLUX engine
        try:
            encoded = urllib.parse.quote(english_prompt)
            seed = random.randint(1000, 999999)
            pollinations_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=flux&nologo=true&seed={seed}"
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=5.0), follow_redirects=True) as client:
                p_resp = await client.get(pollinations_url)
                if p_resp.status_code == 200 and len(p_resp.content) > 2000:
                    local_url = cls._save_image_bytes(p_resp.content, prefix="banana_flux", ext="jpg")
                    if local_url:
                        return {
                            "status": "success",
                            "engine": "flux",
                            "model_id": "flux-free",
                            "model_name": "FLUX.1 Studio (پشتیبان رایگان)",
                            "image_url": local_url,
                            "prompt": prompt,
                            "english_prompt": english_prompt,
                            "aspect_ratio": selected_ratio,
                            "is_fallback": True
                        }
        except Exception as e3:
            print(f"[PuterImageService] Pollinations fallback error: {e3}")

        return {
            "status": "error",
            "engine": "puter",
            "model_name": "Nano Banana",
            "image_url": "",
            "prompt": prompt,
            "error_message": "خطا در برقراری ارتباط با درگاه تولید تصویر Puter. لطفاً دوباره تلاش نمایید."
        }
