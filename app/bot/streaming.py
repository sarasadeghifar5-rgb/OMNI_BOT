"""
===========================================================
⚡ Enterprise Real-Time Telegram Streaming Engine
===========================================================
Provides silky-smooth, real-time token streaming to Telegram
chats with sub-second perceived latency (TTFT < 1.5s).

Key Features:
- Adaptive cadence throttling (~0.85s - 1.0s) respecting Telegram API limits
- Live animated typing cursor (' ▍')
- Real-time reasoning/thinking block visualization
- Zero-drop token buffering
- Dynamic Retry-After rate-limit handling
- Seamless finalization with Markdown-to-HTML & overflow chunking
"""

import time
import asyncio
import html
import logging
from typing import List, Dict, Any, Optional

from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from app.bot.utils import (
    markdown_to_telegram_html,
    format_thinking_block,
    safe_edit_or_reply,
    deduplicate_text,
    strip_html_tags,
)

logger = logging.getLogger("TelegramStream")


class TelegramStreamEngine:
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        placeholder_msg: Message,
        model_name: str,
        thinking_tag: str = "🫥",
        min_edit_interval: float = 0.85,
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.msg = placeholder_msg
        self.model_name = model_name
        self.thinking_tag = thinking_tag
        self.min_edit_interval = min_edit_interval

        self.content_chunks: List[str] = []
        self.thinking_chunks: List[str] = []
        self.sources: List[Dict[str, Any]] = []
        self.current_status: str = ""

        self.last_edit_time: float = 0.0
        self.throttle_until: float = 0.0
        self.last_rendered_text: str = ""
        self._is_finalized: bool = False
        self._edit_lock = asyncio.Lock()

        # Model title for thinking block
        mid = (model_name or "").lower()
        if "atria" in mid or "dawn" in mid:
            self.think_title = "فرآیند استدلال عمیق (Atria Dawn)"
        elif "deepseek" in mid or "r1" in mid:
            self.think_title = "فرآیند تحلیل و تفکر عمیق (DeepSeek R1)"
        elif "agnes" in mid or "nano" in mid:
            self.think_title = "فرآیند استدلال تحلیلی (Nano Reasoner)"
        else:
            self.think_title = "فرآیند تحلیل و تفکر عمیق"

    async def process_event(self, event: Dict[str, Any]):
        """Processes an incoming streaming chunk from LLMGateway."""
        if self._is_finalized:
            return

        etype = event.get("type")

        if etype == "content":
            chunk = event.get("content", "")
            if chunk:
                self.content_chunks.append(chunk)
                await self._maybe_update_telegram()

        elif etype == "thinking":
            th_chunk = event.get("content", "")
            if th_chunk:
                self.thinking_chunks.append(th_chunk)
                await self._maybe_update_telegram()

        elif etype == "status":
            self.current_status = event.get("message", "")
            await self._maybe_update_telegram(force=True)

        elif etype == "sources":
            self.sources = event.get("sources", [])

        elif etype == "error":
            err = event.get("error", "Unknown error")
            raise RuntimeError(err)

    async def _maybe_update_telegram(self, force: bool = False):
        """Dispatches an edit update if the minimum cadence interval has elapsed."""
        now = time.time()
        if now < self.throttle_until:
            return

        if not force and (now - self.last_edit_time) < self.min_edit_interval:
            return

        text_to_render, parse_mode = self._build_streaming_preview()
        if not text_to_render or text_to_render == self.last_rendered_text:
            return

        if self._edit_lock.locked():
            return

        async with self._edit_lock:
            try:
                await self.msg.edit_text(text_to_render, parse_mode=parse_mode)
                self.last_edit_time = time.time()
                self.last_rendered_text = text_to_render
            except TelegramRetryAfter as e:
                self.throttle_until = time.time() + e.retry_after + 0.2
            except TelegramBadRequest as e:
                err_msg = str(e).lower()
                if "message is not modified" in err_msg:
                    self.last_edit_time = time.time()
                elif "can't parse entities" in err_msg or "unclosed" in err_msg:
                    # Incomplete HTML tag in mid-stream, fallback safely to plain text
                    plain = strip_html_tags(text_to_render)
                    try:
                        await self.msg.edit_text(plain, parse_mode=None)
                        self.last_edit_time = time.time()
                        self.last_rendered_text = plain
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"[StreamEngine] Silent edit exception: {e}")

    def _build_streaming_preview(self) -> tuple[str, Optional[str]]:
        """Constructs an aesthetic, safe in-flight preview for the user."""
        raw_content = "".join(self.content_chunks)
        raw_thinking = "".join(self.thinking_chunks)

        cursor = " ▍"

        # 1. If only thinking so far (Reasoning models)
        if raw_thinking and not raw_content:
            clean_th = raw_thinking.strip()
            if len(clean_th) > 1400:
                clean_th = clean_th[-1400:]
            escaped_th = html.escape(clean_th)
            text = (
                f"<blockquote expandable><b>💭 {html.escape(self.think_title)}:</b>\n"
                f"{escaped_th}{cursor}</blockquote>\n\n"
                f"{self.thinking_tag} <i>در حال پردازش پاسخ نهایی...</i>"
            )
            return text, "HTML"

        # 2. If both thinking and content are present
        if raw_thinking and raw_content:
            clean_th = raw_thinking.strip()
            if len(clean_th) > 1000:
                clean_th = clean_th[:1000].rsplit(" ", 1)[0] + "..."
            escaped_th = html.escape(clean_th)
            clean_content = raw_content[-2200:] if len(raw_content) > 2200 else raw_content
            formatted_content = markdown_to_telegram_html(clean_content)

            text = (
                f"<blockquote expandable><b>💭 {html.escape(self.think_title)}:</b>\n"
                f"{escaped_th}</blockquote>\n\n"
                f"{formatted_content}{cursor}"
            )
            return text, "HTML"

        # 3. If standard content only
        if raw_content:
            clean_content = raw_content[-3500:] if len(raw_content) > 3500 else raw_content
            formatted_content = markdown_to_telegram_html(clean_content)
            return f"{formatted_content}{cursor}", "HTML"

        # 4. Status update
        if self.current_status:
            escaped_st = html.escape(self.current_status)
            return f"{self.thinking_tag} <b>{escaped_st}</b>", "HTML"

        return "", None

    async def finalize(self) -> tuple[str, str]:
        """
        Finalizes the stream:
        - Removes stream cursor
        - Produces clean, final Markdown-to-HTML rendering
        - Attaches web search sources
        - Handles messages exceeding Telegram's 4096 character limit
        - Returns (full_content, full_thinking)
        """
        self._is_finalized = True

        full_content = deduplicate_text("".join(self.content_chunks).strip())
        full_thinking = deduplicate_text("".join(self.thinking_chunks).strip())

        # Extract <think> tags if model streamed them inside content
        if "<think>" in full_content and "</think>" in full_content:
            try:
                t_parts = full_content.split("</think>")
                extracted_think = t_parts[0].replace("<think>", "").strip()
                full_content = deduplicate_text(t_parts[1].strip())
                if extracted_think:
                    full_thinking = deduplicate_text(f"{full_thinking}\n{extracted_think}".strip())
            except Exception:
                pass

        # If thinking repeats final answer, suppress thinking
        if full_thinking:
            clean_th = full_thinking.strip()
            clean_co = full_content.strip()
            if clean_th == clean_co or (len(clean_co) > 20 and clean_co in clean_th):
                full_thinking = ""

        if not full_content:
            full_content = "⚠️ پاسخی از هوش مصنوعی دریافت نشد. لطفاً دوباره تلاش فرمایید."

        final_parts = []

        # 1. Reasoning Thinking Block
        if full_thinking:
            final_parts.append(format_thinking_block(full_thinking, title=self.think_title))

        # 2. Main Response Body
        final_parts.append(markdown_to_telegram_html(full_content))

        # 3. Web Search Grounding Sources
        if self.sources:
            clean_sources = [
                s for s in self.sources
                if "grokipedia" not in s.get("url", "").lower()
                and "grok" not in s.get("title", "").lower()
                and s.get("url")
            ]
            if clean_sources:
                sources_text = "\n\n📚 <b>منابع و پیوندهای وب:</b>\n"
                for idx, s in enumerate(clean_sources[:4], 1):
                    title = html.escape(s.get("title", f"منبع {idx}"))
                    url = html.escape(s.get("url", ""))
                    sources_text += f'{idx}. <a href="{url}">{title}</a>\n'
                final_parts.append(sources_text)

        complete_response = "".join(final_parts)

        # Seamlessly edit the message to the final version, with overflow chunking
        await safe_edit_or_reply(self.msg, complete_response, parse_mode="HTML")

        return full_content, full_thinking
