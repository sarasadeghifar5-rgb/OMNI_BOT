import os
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

from app.providers.base import BaseProvider
from app.services.agnes_client import AgnesKeyPool, DEFAULT_BASE_URL

logger = logging.getLogger("AgnesProvider")


class AgnesProvider(BaseProvider):
    """
    Dedicated Provider for Agnes AI:
    - Text Generation & Reasoning (deep reasoning_content / thinking blocks)
    - Multimodal Understanding (visual analysis via image_url / base64 data URIs)
    - Resilient 5-Key Rotation Pool
    """

    MODEL_ALIASES = {
        "agnes": "agnes-2.5-flash",
        "agnes-2.5-flash": "agnes-2.5-flash",
        "agnes-reasoner": "agnes-2.5-flash",
        "agnes-2.5-pro": "agnes-2.5-pro",
        "agnes-3.0-flash": "agnes-3.0-flash",
        "nano-reasoner": "agnes-2.5-flash",
        "nano-reasoner-2.5": "agnes-2.5-flash",
    }

    FALLBACK_MODELS = [
        "agnes-2.5-flash",
        "agnes-2.5-pro",
        "agnes-3.0-flash",
    ]

    def __init__(self, default_api_key: Optional[str] = None):
        super().__init__(
            api_key=default_api_key,
            base_url=os.getenv("AGNES_BASE_URL") or DEFAULT_BASE_URL
        )
        self.pool = AgnesKeyPool.get_instance()

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        target_model = self.MODEL_ALIASES.get(model, model)
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

        # Build payload
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        from app.services.http_client import get_shared_http_client
        client = get_shared_http_client()

        keys = [api_key] if api_key else self.pool.get_active_keys()

        for key in keys:
            headers = self.pool.get_headers(key)
            has_streamed = False
            self.pool.acquire_key(key)

            try:
                async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                        if response.status_code == 200:
                            self.pool.record_key_success(key)
                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                line_str = line.strip()
                                if line_str.startswith("data:"):
                                    data_text = line_str[len("data:"):].strip()
                                    if data_text == "[DONE]":
                                        yield {"type": "done"}
                                        return
                                    try:
                                        chunk = json.loads(data_text)
                                        choices = chunk.get("choices", [])
                                        if not choices:
                                            continue
                                        delta = choices[0].get("delta", {})

                                        # 1. Reasoning / Thinking content
                                        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                                        if reasoning:
                                            has_streamed = True
                                            yield {
                                                "type": "thinking",
                                                "content": reasoning
                                            }

                                        # 2. Main response content
                                        content = delta.get("content")
                                        if content:
                                            has_streamed = True
                                            yield {
                                                "type": "content",
                                                "content": content
                                            }
                                    except json.JSONDecodeError:
                                        continue

                            if has_streamed:
                                yield {"type": "done"}
                                return

                        elif response.status_code in (429, 403):
                            self.pool.record_key_error(key, response.status_code)
                            # Key rate-limited, try next key
                            continue
                        else:
                            self.pool.record_key_error(key, response.status_code)
                            continue

            except (httpx.TimeoutException, httpx.RequestError):
                self.pool.record_key_error(key, 504)
                continue
            except Exception as e:
                self.pool.record_key_error(key, 500)
                continue
            finally:
                self.pool.release_key(key)

        # If all keys failed on Agnes, failover to Gemini
        try:
            from app.providers.gemini_provider import GeminiProvider
            gemini = GeminiProvider()
            async for chunk in gemini.stream_chat(messages=messages, model="gemini", temperature=temperature, **kwargs):
                yield chunk
        except Exception:
            yield {"type": "error", "message": "ارتباط با سرویس هوش مصنوعی برقرار نشد."}
