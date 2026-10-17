"""
CleanAPIs client for flagship AI models (Claude 5, GPT-5.6, DeepSeek, Gemini 3.7, Qwen, Kimi).
"""
import httpx
import logging
import base64
from typing import List, Dict, Optional
from config import CLEANAPIS_BASE_URL, CLEANAPIS_API_KEY
from utils.system_prompt import MASTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class CleanAPIsClient:
    def __init__(self, base_url: str = CLEANAPIS_BASE_URL, api_key: str = CLEANAPIS_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def generate_chat_response(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 8192
    ) -> str:
        """Call CleanAPIs chat completion endpoint."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Prepend system prompt if not present
        full_messages = [{"role": "system", "content": MASTER_SYSTEM_PROMPT}]
        for m in messages:
            full_messages.append({"role": m["role"], "content": m["content"]})

        payload = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0]["message"]["content"].strip()
                else:
                    logger.warning(f"CleanAPIs error {response.status_code}: {response.text[:120]}. Falling back to Agnes AI.")
            except Exception as e:
                logger.warning(f"CleanAPIs request failed ({e}). Falling back to Agnes AI.")

        # Seamless fast failover to Agnes AI
        from api_services.agnes import agnes_client
        return await agnes_client.generate_chat_response(
            model="agnes-3.0-flash",
            messages=messages or [],
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def generate_vision_response(
        self,
        model: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        prompt: str = "این تصویر را به دقت بررسی و تحلیل کن و به زبان فارسی توضیح بده.",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Optional[str]:
        """Call CleanAPIs vision completion with base64 image."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            "temperature": temperature,
            "max_tokens": 8192
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0]["message"]["content"].strip()
                else:
                    logger.warning(f"CleanAPIs vision error {response.status_code}. Falling back to Agnes vision.")
            except Exception as e:
                logger.warning(f"CleanAPIs vision exception: {e}. Falling back to Agnes vision.")

        from api_services.agnes import agnes_client
        return await agnes_client.generate_vision_response(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt
        )

# Global instance
cleanapis_client = CleanAPIsClient()
