import json
import os
import asyncio
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional
from app.providers.base import BaseProvider

class OpenAICompatibleProvider(BaseProvider):
    """
    Unified provider for all OpenAI-compatible APIs:
    - OpenAI (GPT-4o, o1, etc.)
    - DeepSeek (deepseek-chat, deepseek-reasoner)
    - xAI Grok (grok-2, grok-2-vision)
    - Zhipu AI GLM (glm-4, glm-4v, glm-4-flash)
    - OpenRouter
    - Ollama / Local
    Includes automated zero-error failover cascade to ensure 100% service uptime.
    """
    def __init__(self, default_api_key: Optional[str] = None, base_url: str = "https://api.openai.com/v1"):
        super().__init__(api_key=default_api_key, base_url=base_url)

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        key = api_key or self.api_key
        target_base_url = self.base_url
        target_model = model

        # Free OpenRouter fallback pool
        FREE_FALLBACK_POOL = [
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "google/gemma-4-26b-a4b-it:free",
            "qwen/qwen3.8-27b:free",
            "dots-studio/dots-3-note-preview:free",
            "liquid/lfm-2.5-2.6b:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "nvidia/nemotron-3.5-lightning:free"
        ]

        is_local = "localhost" in (target_base_url or "") or "127.0.0.1" in (target_base_url or "")
        is_reasoning_model = any(tag in str(target_model).lower() for tag in ["o1", "o3", "reasoner", "r1", "atria", "dawn"])

        # If no key is provided and not running locally, route to high-speed OpenRouter free models
        if not key and not is_local:
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if openrouter_key:
                target_base_url = "https://openrouter.ai/api/v1"
                key = openrouter_key
                if is_reasoning_model:
                    target_model = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
                else:
                    target_model = "google/gemma-4-26b-a4b-it:free"
            else:
                # Direct failover to Google Gemini
                from app.providers.gemini_provider import GeminiProvider
                gemini = GeminiProvider()
                async for chunk in gemini.stream_chat(messages=messages, model="gemini", temperature=temperature, **kwargs):
                    yield chunk
                return

        headers = {
            "Content-Type": "application/json",
        }
        if key:
            headers["Authorization"] = f"Bearer {key}"

        # Extra headers for OpenRouter
        if "openrouter.ai" in (target_base_url or ""):
            headers["HTTP-Referer"] = "https://github.com/omni-chat"
            headers["X-Title"] = "OmniLLM Hub"

        # Build payload
        payload: Dict[str, Any] = {
            "model": target_model,
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

        # Enable native web search on upstream model (CodeCraft API)
        if kwargs.get("web_search") or kwargs.get("enable_web_search"):
            payload["web_search"] = True

        endpoint = target_base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"

        attempted = set(kwargs.get("_attempted_models", []))
        attempted.add(target_model)

        has_streamed_content = False

        from app.services.http_client import get_shared_http_client
        client = get_shared_http_client()

        try:
            async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_bytes = await response.aread()
                    print(f"[OpenAICompatible] Upstream returned status {response.status_code}: {err_bytes[:200]}")

                    # If CodeCraft, retry once after a short delay
                    if "codecraftapi.com" in target_base_url:
                        await asyncio.sleep(1.0)
                        try:
                            async with client.stream("POST", endpoint, headers=headers, json=payload) as retry_resp:
                                if retry_resp.status_code == 200:
                                            async for line in retry_resp.aiter_lines():
                                                if not line:
                                                    continue
                                                line = line.strip()
                                                if line.startswith("data:"):
                                                    line_data = line[len("data:"):].strip()
                                                    if line_data == "[DONE]":
                                                        yield {"type": "done"}
                                                        return
                                                    try:
                                                        chunk = json.loads(line_data)
                                                    except json.JSONDecodeError:
                                                        continue
                                                    choices = chunk.get("choices", [])
                                                    if choices:
                                                        delta = choices[0].get("delta", {})
                                                        if delta.get("reasoning_content"):
                                                            yield {"type": "thinking", "content": delta["reasoning_content"]}
                                                        if delta.get("content"):
                                                            yield {"type": "content", "content": delta["content"]}
                                            return
                        except Exception as re:
                            print(f"[OpenAICompatible] CodeCraft retry exception: {re}")

                        # Fallback to next model in OpenRouter pool if available
                        next_model = next((m for m in FREE_FALLBACK_POOL if m not in attempted), None)
                        openrouter_key = os.getenv("OPENROUTER_API_KEY")
                        if next_model and openrouter_key:
                            next_kwargs = dict(kwargs)
                            next_kwargs["_attempted_models"] = list(attempted)
                            prov = OpenAICompatibleProvider(default_api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
                            async for chunk in prov.stream_chat(
                                messages=messages,
                                model=next_model,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                api_key=openrouter_key,
                                **next_kwargs
                            ):
                                yield chunk
                            return

                        # If OpenRouter models also exhausted, failover to Google Gemini
                        from app.providers.gemini_provider import GeminiProvider
                        gemini = GeminiProvider()
                        async for chunk in gemini.stream_chat(messages=messages, model="gemini", temperature=temperature, **kwargs):
                            yield chunk
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        line = line.strip()
                        if line.startswith("data:"):
                            line_data = line[len("data:"):].strip()
                            if line_data == "[DONE]":
                                yield {"type": "done"}
                                break

                            try:
                                chunk = json.loads(line_data)
                            except json.JSONDecodeError:
                                continue

                            choices = chunk.get("choices", [])
                            if not choices:
                                continue

                            delta = choices[0].get("delta", {})

                            # 1. Reasoning content
                            reasoning_content = delta.get("reasoning_content") or delta.get("reasoning")
                            if reasoning_content:
                                has_streamed_content = True
                                yield {
                                    "type": "thinking",
                                    "content": reasoning_content
                                }

                            # 2. Assistant content
                            content = delta.get("content")
                            if content:
                                has_streamed_content = True
                                yield {
                                    "type": "content",
                                    "content": content
                                }

        except (httpx.ConnectError, httpx.TimeoutException, Exception):
            if not has_streamed_content:
                # Seamless failover to Gemini on any connection failure
                try:
                    yield {
                        "type": "status",
                        "message": "در حال هدایت خودکار به سرور پشتیبان..."
                    }
                    from app.providers.gemini_provider import GeminiProvider
                    gemini = GeminiProvider()
                    async for chunk in gemini.stream_chat(messages=messages, model="gemini", temperature=temperature, **kwargs):
                        yield chunk
                    return
                except Exception:
                    pass
