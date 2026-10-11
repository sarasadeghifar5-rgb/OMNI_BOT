import os
import json
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional
from app.providers.base import BaseProvider

class ClaudeProvider(BaseProvider):
    """
    Anthropic Claude Provider for Claude 3.5 Sonnet, Claude 3.7 Sonnet, etc.
    """
    def __init__(self, default_api_key: Optional[str] = None):
        super().__init__(api_key=default_api_key, base_url="https://api.anthropic.com/v1")

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
        if not key:
            from app.providers.openai_compatible import OpenAICompatibleProvider
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            free_prov = OpenAICompatibleProvider(default_api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
            async for chunk in free_prov.stream_chat(messages, model="nex-agi/nex-n2.5-pro:free", temperature=temperature, **kwargs):
                yield chunk
            return

        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Separate system message from conversation history
        system_prompt = None
        formatted_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                if isinstance(content, str):
                    system_prompt = content
                continue

            # Format image parts if any
            if isinstance(content, list):
                claude_content = []
                for part in content:
                    if part.get("type") == "text":
                        claude_content.append({"type": "text", "text": part.get("text", "")})
                    elif part.get("type") == "image_url":
                        url_data = part.get("image_url", {}).get("url", "")
                        if url_data.startswith("data:"):
                            # Parse data:image/png;base64,...
                            try:
                                header, base64_str = url_data.split(";base64,")
                                media_type = header.replace("data:", "")
                                claude_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": base64_str
                                    }
                                })
                            except Exception:
                                pass
                formatted_messages.append({"role": role, "content": claude_content})
            else:
                formatted_messages.append({"role": role, "content": content})

        payload = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        endpoint = f"{self.base_url}/messages"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
                async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        yield {
                            "type": "status",
                            "message": "در حال هدایت خودکار به سرور پشتیبان با کیفیت بالا..."
                        }
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
                            data_str = line[len("data:"):].strip()
                            try:
                                data = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            event_type = data.get("type")
                            if event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield {
                                        "type": "content",
                                        "content": delta.get("text", "")
                                    }
                                elif delta.get("type") == "thinking_delta":
                                    yield {
                                        "type": "thinking",
                                        "content": delta.get("thinking", "")
                                    }
                            elif event_type == "message_stop":
                                yield {"type": "done"}
                                break

        except (httpx.ConnectError, httpx.TimeoutException, Exception):
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
