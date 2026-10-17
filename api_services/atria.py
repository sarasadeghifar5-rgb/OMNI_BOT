"""
Atria ASI client for deep reasoning model Atria-Dawn-Preview (200k context window).
Features KeyPool, fast failover (15s timeout), and seamless fallback to CleanAPIs DeepSeek/Claude.
"""
import httpx
import logging
from typing import List, Dict, Optional
from config import ATRIA_BASE_URL, ATRIA_API_KEYS
from api_services.key_pool import KeyPool
from api_services.cleanapis import cleanapis_client
from utils.system_prompt import MASTER_SYSTEM_PROMPT

from api_services.agnes import agnes_client

logger = logging.getLogger(__name__)

class AtriaClient:
    def __init__(self, base_url: str = ATRIA_BASE_URL, keys: List[str] = ATRIA_API_KEYS):
        self.base_url = base_url.rstrip("/")
        self.pool = KeyPool("Atria ASI", keys, cooldown_seconds=60)

    async def generate_chat_response(
        self,
        model: str = "Atria-Dawn-Preview",
        messages: List[Dict[str, str]] = None,
        temperature: float = 0.5,
        max_tokens: int = 8192
    ) -> str:
        """Call Atria ASI chat completions with fast failover and graceful fallback to Agnes AI."""
        url = f"{self.base_url}/chat/completions"

        full_messages = [{"role": "system", "content": MASTER_SYSTEM_PROMPT}]
        if messages:
            for m in messages:
                full_messages.append({"role": m["role"], "content": m["content"]})

        payload = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Try with 25s timeout for fast response
        attempts = 1
        last_error = ""

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                for _ in range(attempts):
                    api_key = self.pool.get_key()
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }

                    try:
                        response = await client.post(url, headers=headers, json=payload)
                        if response.status_code == 200:
                            self.pool.report_success(api_key)
                            data = response.json()
                            choices = data.get("choices", [])
                            if choices:
                                return choices[0]["message"]["content"].strip()
                        elif response.status_code in (429, 401, 403):
                            self.pool.report_failure(api_key, response.status_code)
                            last_error = f"کد خطا {response.status_code}"
                            continue
                        else:
                            self.pool.report_failure(api_key, response.status_code)
                            last_error = f"کد خطا {response.status_code}"
                    except httpx.TimeoutException:
                        self.pool.report_failure(api_key, 408)
                        last_error = "Timeout"
                    except Exception as e:
                        self.pool.report_failure(api_key)
                        last_error = str(e)
        except Exception as e:
            last_error = str(e)

        # Seamless fallback to Agnes AI
        logger.warning(f"Atria ASI unavailable or timed out ({last_error}). Falling back to Agnes AI.")
        return await agnes_client.generate_chat_response(
            model="agnes-3.0-flash",
            messages=messages or [],
            temperature=temperature,
            max_tokens=max_tokens
        )

# Global instance
atria_client = AtriaClient()
