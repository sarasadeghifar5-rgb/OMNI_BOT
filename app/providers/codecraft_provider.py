import os
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

from app.providers.base import BaseProvider
from app.services.codecraft_client import CodeCraftKeyPool, DEFAULT_BASE_URL

logger = logging.getLogger("CodeCraftProvider")


class CodeCraftProvider(BaseProvider):
    """
    Dedicated Provider for CodeCraft API:
    - 33 Next-Gen flagship models (Claude Opus 5.5, Fable 5.1, GPT-5.6 Sol/Luna/Terra, DeepSeek V4)
    - Deep reasoning extraction (reasoning_content & thinking blocks)
    - Native server-side web search integration
    - Highly resilient Multi-Key Failover & Load-Balancing Pool
    """

    def __init__(self, default_api_key: Optional[str] = None):
        raw_ca_url = (os.getenv("CLEANAPIS_BASE_URL") or os.getenv("CODECRAFT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        if "codecraftapi.com" in raw_ca_url or not raw_ca_url:
            raw_ca_url = DEFAULT_BASE_URL
        super().__init__(
            api_key=default_api_key,
            base_url=raw_ca_url
        )
        self.pool = CodeCraftKeyPool.get_instance()

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

        # Determine if model natively does reasoning
        is_reasoning_model = any(
            tag in str(model).lower()
            for tag in ["reasoner", "r1", "opus", "fable", "sol", "terra", "luna", "pro", "v4", "mythos", "k3", "k2.6"]
        )

        # Build payload
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        if not is_reasoning_model:
            payload["temperature"] = temperature
        else:
            if max_tokens:
                payload["max_completion_tokens"] = max_tokens

        if max_tokens and not is_reasoning_model:
            payload["max_tokens"] = max_tokens

        # Enable native web search on upstream CodeCraft model
        if kwargs.get("web_search") or kwargs.get("enable_web_search"):
            payload["web_search"] = True

        from app.services.http_client import get_shared_http_client
        client = get_shared_http_client()

        active_keys = self.pool.get_active_keys()
        if api_key and api_key.startswith("cc_"):
            keys = [api_key] + [k for k in active_keys if k != api_key]
        else:
            keys = active_keys
        if not keys:
            from app.services.codecraft_client import FALLBACK_CODECRAFT_KEYS
            keys = list(FALLBACK_CODECRAFT_KEYS)

        for key in keys:
            headers = self.pool.get_headers(key)
            has_streamed = False
            self.pool.acquire_key(key)

            try:
                async with client.stream("POST", endpoint, headers=headers, json=payload, timeout=httpx.Timeout(40.0, connect=6.0)) as response:
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
                            f"CodeCraft upstream returned {response.status_code} for key [...{key[-6:]}]: {err_preview}. Rotating key..."
                        )
                        self.pool.record_key_error(key, response.status_code)
                        continue

            except (httpx.TimeoutException, httpx.RequestError) as ex:
                logger.warning(f"CodeCraft connection error for key [...{key[-6:]}]: {ex}. Rotating key...")
                self.pool.record_key_error(key, 504)
                continue
            except Exception as e:
                logger.warning(f"CodeCraft unexpected error for key [...{key[-6:]}]: {e}. Rotating key...")
                self.pool.record_key_error(key, 500)
                continue
            finally:
                self.pool.release_key(key)

        # If all keys failed for this model, retry with CleanAPIs' guaranteed model (gemini-3.7-flash)
        if model != "gemini-3.7-flash":
            logger.info("Retrying with CleanAPIs flagship model gemini-3.7-flash...")
            try:
                master_key = "cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB"
                headers = {"Authorization": f"Bearer {master_key}", "Content-Type": "application/json"}
                fallback_payload = {"model": "gemini-3.7-flash", "messages": messages, "stream": True}
                async with client.stream("POST", endpoint, headers=headers, json=fallback_payload, timeout=httpx.Timeout(30.0, connect=6.0)) as response:
                    if response.status_code == 200:
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
                                    if choices:
                                        content = choices[0].get("delta", {}).get("content")
                                        if content:
                                            yield {"type": "content", "content": content}
                                except json.JSONDecodeError:
                                    continue
                        yield {"type": "done"}
                        return
            except Exception as e_fb:
                logger.warning(f"CleanAPIs gemini-3.7-flash fallback exception: {e_fb}")

        # If still failed, fallback to Gemini provider
        logger.error("All CodeCraft keys in pool exhausted. Failing over to backup provider...")
        try:
            from app.providers.gemini_provider import GeminiProvider
            gemini = GeminiProvider()
            async for chunk in gemini.stream_chat(messages=messages, model="gemini", temperature=temperature, **kwargs):
                yield chunk
        except Exception as e:
            logger.error(f"Fallback after CodeCraft failure also errored: {e}")
            yield {"type": "error", "message": "ارتباط با سرورهای هوش مصنوعی برقرار نشد."}
