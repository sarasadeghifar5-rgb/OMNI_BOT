import os
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

from app.providers.base import BaseProvider
from app.services.atria_client import AtriaKeyPool, DEFAULT_BASE_URL

logger = logging.getLogger("AtriaProvider")


class AtriaProvider(BaseProvider):
    """
    Dedicated Provider for Atria ASI:
    - Atria Dawn Preview reasoning model with 256K context window
    - Deep reasoning extraction (reasoning_content & thinking blocks)
    - Multi-Key Failover & Load-Balancing Pool
    """

    def __init__(self, default_api_key: Optional[str] = None):
        super().__init__(
            api_key=default_api_key,
            base_url=os.getenv("ATRIA_BASE_URL") or DEFAULT_BASE_URL
        )
        self.pool = AtriaKeyPool.get_instance()

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        target_model = model or "Atria-Dawn-Preview"
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

        # Build payload
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": True,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        from app.services.http_client import get_shared_http_client
        client = get_shared_http_client()

        active_keys = self.pool.get_active_keys()
        if api_key:
            keys = [api_key] + [k for k in active_keys if k != api_key]
        else:
            keys = active_keys
        if not keys:
            from app.services.atria_client import FALLBACK_ATRIA_KEYS
            keys = list(FALLBACK_ATRIA_KEYS)

        for key in keys:
            headers = self.pool.get_headers(key)
            has_streamed = False
            self.pool.acquire_key(key)

            try:
                async with client.stream("POST", endpoint, headers=headers, json=payload, timeout=httpx.Timeout(30.0, connect=6.0)) as response:
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

                    else:
                        # 429, 401, 500, etc.
                        err_preview = (await response.aread())[:120].decode("utf-8", errors="ignore")
                        logger.warning(
                            f"Atria upstream returned {response.status_code} for key [...{key[-6:]}]: {err_preview}. Rotating key..."
                        )
                        self.pool.record_key_error(key, response.status_code)
                        continue

            except (httpx.TimeoutException, httpx.RequestError) as ex:
                logger.warning(f"Atria connection error for key [...{key[-6:]}]: {ex}. Rotating key...")
                self.pool.record_key_error(key, 504)
                continue
            except Exception as e:
                logger.warning(f"Atria unexpected error for key [...{key[-6:]}]: {e}. Rotating key...")
                self.pool.record_key_error(key, 500)
                continue
            finally:
                self.pool.release_key(key)

        # If all Atria keys in pool failed, fallback seamlessly to CleanAPIs (gemini-3.7-flash)
        logger.error("All Atria keys in pool exhausted. Failing over to CleanAPIs backup provider...")
        try:
            from app.providers.codecraft_provider import CodeCraftProvider
            cleanapis = CodeCraftProvider(default_api_key="cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB")
            async for chunk in cleanapis.stream_chat(
                messages=messages,
                model="gemini-3.7-flash",
                temperature=temperature,
                api_key="cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB",
                **kwargs
            ):
                yield chunk
        except Exception as e:
            logger.error(f"Fallback after Atria failure also errored: {e}")
            yield {"type": "error", "message": "ارتباط با سرورهای هوش مصنوعی برقرار نشد."}
