import os
import asyncio
import time
import html
import logging
from typing import List, Dict, Any, Optional

from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext

from app.services.gateway import LLMGateway
from app.bot.database import BotDatabase
from app.bot.config import ADMIN_IDS, CUSTOM_EMOJI_THINKING
from app.config import get_model_capabilities, MODEL_NAMES
from app.bot.middlewares import ConcurrencyManager
from app.bot.streaming import TelegramStreamEngine

logger = logging.getLogger("ChatHandler")

router = Router(name="chat_router")
gateway = LLMGateway()
db = BotDatabase.get_instance()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_chat(message: Message, state: FSMContext):
    """
    هندلر اصلی و اختصاصی چت متنی کاربران با مدل‌های هوش مصنوعی (OmniLLM Unified Chat):
    - اجرای مستقیم مدل انتخاب‌شده بدون هیچ‌گونه سرویس پشتیبان / فال‌بک
    - استریم زنده پاسخ و فرآیند تفکر عمیق (Thinking)
    - سوییچ خودکار به استودیو عکس و ویدیو در صورت درخواست کاربر
    """
    user_text = message.text.strip()
    user_id = message.from_user.id

    # ۰. بررسی مسدود بودن کاربر
    if await db.is_user_banned(user_id):
        return

    # ۱. دریافت اطلاعات کاربر و مدل انتخابی از دیتابیس
    user = await db.get_or_create_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    selected_model = user.get("selected_model") or "gemini-3.7-flash"
    if selected_model == "gemini":
        selected_model = "gemini-3.7-flash"

    model_caps = get_model_capabilities(selected_model)
    model_display_name = MODEL_NAMES.get(selected_model, selected_model)

    # ۲. مسیریابی هوشمند به استودیو تصویر در صورت درخواست ساخت عکس
    image_prefixes = [
        "عکس بساز از", "عکس بساز", "تصویر بساز از", "تصویر بساز",
        "یک عکس از", "یک تصویر از", "نقاشی از", "تولید عکس از", "تولید تصویر از"
    ]
    matched_image_prefix = next((p for p in image_prefixes if user_text.startswith(p)), None)
    if model_caps.get("is_image_studio", False) or matched_image_prefix:
        from app.bot.handlers.image import execute_text_generation, get_user_settings
        clean_prompt = user_text
        if matched_image_prefix:
            clean_prompt = user_text[len(matched_image_prefix):].lstrip(": ").strip()
        if not clean_prompt:
            clean_prompt = user_text
        ratio, size = await get_user_settings(state, user_id)
        await execute_text_generation(message, clean_prompt, ratio, size, state)
        return

    # ۳. مسیریابی هوشمند به استودیو ویدیو در صورت درخواست ساخت ویدیو
    video_prefixes = [
        "ویدیو بساز از", "ویدیو بساز", "کلیپ بساز از", "کلیپ بساز",
        "یک ویدیو از", "یک کلیپ از", "تولید ویدیو از", "فیلم کوتاه از"
    ]
    matched_video_prefix = next((p for p in video_prefixes if user_text.startswith(p)), None)
    if model_caps.get("is_video_studio", False) or matched_video_prefix:
        from app.bot.handlers.video import execute_video_generation, get_user_video_settings
        clean_prompt = user_text
        if matched_video_prefix:
            clean_prompt = user_text[len(matched_video_prefix):].lstrip(": ").strip()
        if not clean_prompt:
            clean_prompt = user_text
        ratio, seconds, size = await get_user_video_settings(state, user_id)
        await execute_video_generation(message, prompt=clean_prompt, mode="text", ratio=ratio, seconds=seconds, size=size)
        return

    # ۴. تعیین وضعیت سرچ وب
    web_search_enabled = bool(user.get("web_search_enabled", 0))

    # ۵. دریافت تاریخچه گفتگوهای قبلی (Sliding Window Context)
    history = await db.get_chat_history(user_id)
    chat_messages = list(history)
    chat_messages.append({"role": "user", "content": user_text})

    # ۶. کنترل همزمانی درخواست‌ها
    user_lock = await ConcurrencyManager.get_user_lock(user_id)
    async with user_lock:
        async with ConcurrencyManager.acquire_slot():
            # ارسال سیگنال در حال تایپ
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

            # ساخت پیام وضعیت اولیه با ایموجی متحرک
            thinking_eid = CUSTOM_EMOJI_THINKING or "5334904192622403796"
            thinking_tag = f'<tg-emoji emoji-id="{thinking_eid}">🫥</tg-emoji>'

            if any(k in selected_model.lower() for k in ["reasoner", "r1", "atria", "dawn", "agnes", "opus", "sol"]):
                wait_text = f"{thinking_tag} <b>در حال تفکر عمیق و استدلال با {model_display_name}...</b>"
            elif web_search_enabled:
                wait_text = f"{thinking_tag} <b>در حال تحلیل و جستجوی زنده با {model_display_name}...</b>"
            else:
                wait_text = f"{thinking_tag} <b>در حال دریافت پاسخ از {model_display_name}...</b>"

            waiting_msg = await message.answer(wait_text, parse_mode="HTML")

            # ارسال مداوم سیگنال تایپ در پس‌زمینه
            typing_task = asyncio.create_task(keep_typing(message))

            # موتور استریم زنده پاسخ در تلگرام
            stream_engine = TelegramStreamEngine(
                bot=message.bot,
                chat_id=message.chat.id,
                placeholder_msg=waiting_msg,
                model_name=selected_model,
                thinking_tag=thinking_tag,
            )

            try:
                # 🚀 اجرای مستقیم مدل هوش مصنوعی انتخاب‌شده بدون هیچ سرویس پشتیبان
                async for event in gateway.stream_chat(
                    messages=chat_messages,
                    model_id=selected_model,
                    enable_web_search=web_search_enabled
                ):
                    await stream_engine.process_event(event)

                # لغو تسک وضعیت تایپ
                typing_task.cancel()

                # نهایی‌سازی پیام در تلگرام
                full_content, full_thinking = await stream_engine.finalize()

                # ذخیره پیام‌ها در دیتابیس در پس‌زمینه
                if full_content:
                    asyncio.create_task(db.add_message(user_id, "user", user_text, model=selected_model))
                    asyncio.create_task(db.add_message(user_id, "assistant", full_content, model=selected_model))

            except Exception as e:
                typing_task.cancel()
                logger.error(f"[ChatHandler] Error processing message for user {user_id} on model {selected_model}: {e}")
                err_text = f"⚠️ <b>خطا در دریافت پاسخ از {model_display_name}:</b>\n<code>{html.escape(str(e)[:250])}</code>"
                try:
                    await waiting_msg.edit_text(err_text, parse_mode="HTML")
                except Exception:
                    await message.answer(err_text, parse_mode="HTML")


async def keep_typing(message: Message):
    """ارسال دوره‌ای اکشن تایپ به تلگرام در حین پردازش و استریم."""
    try:
        while True:
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
            await asyncio.sleep(4.0)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
