"""
Google Gemini client with KeyPool and graceful fallback to CleanAPIs Gemini.
Handles text, vision, and audio transcription.
"""
import httpx
import logging
import base64
from typing import List, Dict, Optional, Tuple, Any
from config import GEMINI_BASE_URL, GEMINI_API_KEYS
from api_services.key_pool import KeyPool
from api_services.cleanapis import cleanapis_client
from utils.system_prompt import MASTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, base_url: str = GEMINI_BASE_URL, keys: List[str] = GEMINI_API_KEYS):
        self.base_url = base_url.rstrip("/")
        self.pool = KeyPool("Google Gemini", keys, cooldown_seconds=60)

    async def generate_chat_response(
        self,
        model: str = "gemini-flash-latest",
        messages: List[Dict[str, str]] = None,
        temperature: float = 0.5,
        max_tokens: int = 8192
    ) -> str:
        """Generate response using Google Gemini API with fallback to CleanAPIs."""
        contents = []
        if messages:
            for m in messages:
                role = "user" if m["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": m["content"]}]
                })

        # Try Google AI Studio first
        attempts = min(2, len(self.pool.keys))
        for _ in range(attempts):
            api_key = self.pool.get_key()
            url = f"{self.base_url}/models/{model}:generateContent?key={api_key}"

            payload = {
                "systemInstruction": {
                    "parts": [{"text": MASTER_SYSTEM_PROMPT}]
                },
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        self.pool.report_success(api_key)
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
                    else:
                        self.pool.report_failure(api_key, res.status_code)
            except Exception as e:
                self.pool.report_failure(api_key)
                logger.warning(f"Google Gemini direct connection failed: {e}. Falling back to CleanAPIs.")

        # Fallback to CleanAPIs Gemini 3.7 Flash for 100% reliable uptime
        logger.info("Routing Gemini request to CleanAPIs Gemini 3.7 Flash fallback.")
        return await cleanapis_client.generate_chat_response(
            model="gemini-3.7-flash",
            messages=messages or []
        )

    async def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        prompt: str = "این تصویر را به دقت بررسی کن و به زبان فارسی توضیح بده."
    ) -> str:
        """Multimodal image analysis using Gemini."""
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # Try direct Google Gemini
        for _ in range(2):
            api_key = self.pool.get_key()
            url = f"{self.base_url}/models/gemini-flash-latest:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": img_b64
                            }
                        }
                    ]
                }]
            }

            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        self.pool.report_success(api_key)
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"].strip()
                    else:
                        self.pool.report_failure(api_key, res.status_code)
            except Exception as e:
                self.pool.report_failure(api_key)

        return "متأسفانه در تحلیل تصویر خطایی رخ داد. لطفاً تصویر را مجدداً ارسال فرمایید."

# Global instance
gemini_client = GeminiClient()
