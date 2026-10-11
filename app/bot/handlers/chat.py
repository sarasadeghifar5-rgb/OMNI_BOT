import asyncio
import time
import html
from typing import List, Dict, Any
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction

from app.services.gateway import LLMGateway
from app.bot.database import BotDatabase
from app.bot.config import ADMIN_IDS, CUSTOM_EMOJI_THINKING
from app.config import STAR_LOCKED_MODELS, get_model_capabilities
from app.bot.keyboards import get_star_paywall_keyboard
from app.bot.middlewares import ConcurrencyManager
from app.bot.utils import (
    safe_reply,
    format_thinking_block,
    safe_edit_or_reply,
    deduplicate_text,
    markdown_to_telegram_html,
)

from aiogram.fsm.context import FSMContext

router = Router(name="chat_router")
gateway = LLMGateway()
db = BotDatabase.get_instance()

@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_chat(message: Message, state: FSMContext):
    """
    Main chat handler for text messages.
    Supports multi-model routing, Atria/DeepSeek thinking display,
    web search grounding, and smart image generation routing.
    """
    user_text = message.text.strip()
    user_id = message.from_user.id

    # 0. Check if user is banned
    if await db.is_user_banned(user_id):
        return

    # 1. Get user preferences from database
    user = await db.get_or_create_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    selected_model = user.get("selected_model") or "gemini-3.7-flash"
    if selected_model == "gemini":
        selected_model = "gemini-3.7-flash"
    model_caps = get_model_capabilities(selected_model)

    # If user is in image studio mode, route directly to image generation
    if model_caps.get("is_image_studio"):
        from app.bot.handlers.image import execute_text_generation, get_user_settings
        ratio, size = await get_user_settings(state, user_id)
        await execute_text_generation(message, user_text, ratio, size, state)
        return

    # If user is in video studio mode, route directly to video generation
    if model_caps.get("is_video_studio"):
        from app.bot.handlers.video import execute_video_generation, get_user_video_settings
        ratio, seconds, size = await get_user_video_settings(state, user_id)
        await execute_video_generation(message, prompt=user_text, mode="text", ratio=ratio, seconds=seconds, size=size)
        return

    # Strictly only enable web search if this specific model REALLY supports web search!
    if model_caps.get("supports_web_search", False):
        web_search_enabled = bool(user.get("web_search_enabled", 0))
    else:
        web_search_enabled = False

    # Check VIP / Star lock for premium models
    is_admin = (user_id in ADMIN_IDS)
    is_vip = await db.is_user_vip(user_id)
    if selected_model in STAR_LOCKED_MODELS and not (is_admin or is_vip):
        text = (
            f"🔒 **مدل فعال شما (`{selected_model}`) نیازمند اشتراک استار تلگرام است!**\n\n"
            "این مدل جزو پرچمداران پردازشی فوق‌پیشرفته نسل ۵ در CodeCraft API است.\n\n"
            "⭐ جهت فعال‌سازی آنی، یکی از پلن‌های استار زیر را انتخاب فرمایید:"
        )
        markup = get_star_paywall_keyboard(selected_model)
        await message.reply(text, reply_markup=markup, parse_mode="Markdown")
        return

    # Check if admin sent a custom animated emoji to set for web search
    if is_admin:
        custom_emoji_id = None
        for entity in (message.entities or []):
            if entity.type == "custom_emoji" and entity.custom_emoji_id:
                custom_emoji_id = str(entity.custom_emoji_id)
                break
        
        if custom_emoji_id:
            import os
            from app.bot import config as bot_config
            from app.bot import keyboards as bot_keyboards
            bot_config.CUSTOM_EMOJI_WEB_SEARCH = custom_emoji_id
            bot_keyboards.CUSTOM_EMOJI_WEB_SEARCH = custom_emoji_id
            os.environ["CUSTOM_EMOJI_WEB_SEARCH"] = custom_emoji_id
            await db.set_setting("custom_emoji_web_search", custom_emoji_id)
            
            try:
                env_path = bot_config.BASE_DIR / ".env"
                if env_path.exists():
                    txt = env_path.read_text(encoding="utf-8")
                    if "CUSTOM_EMOJI_WEB_SEARCH=" in txt:
                        lines = [f"CUSTOM_EMOJI_WEB_SEARCH={custom_emoji_id}" if l.startswith("CUSTOM_EMOJI_WEB_SEARCH=") else l for l in txt.splitlines()]
                        env_path.write_text("\n".join(lines), encoding="utf-8")
                    else:
                        env_path.write_text(txt + f"\nCUSTOM_EMOJI_WEB_SEARCH={custom_emoji_id}\n", encoding="utf-8")
            except Exception:
                pass

            await message.reply(
                f"🎉 **ایموجی متحرک با موفقیت شناسایی و اعمال شد!**\n\n"
                f"• شناسه ایموجی متحرک: `{custom_emoji_id}`\n"
                "• از این پس این ایموجی متحرک به عنوان آیکون اختصاصی وب‌سرچ در تمامی منوها و دکمه‌ها نمایش داده می‌شود.",
                parse_mode="Markdown"
            )
            return

        if user_text.startswith("/set_emoji"):
            parts = user_text.split()
            if len(parts) > 1 and parts[1].isdigit():
                eid = parts[1].strip()
                import os
                from app.bot import config as bot_config
                from app.bot import keyboards as bot_keyboards
                bot_config.CUSTOM_EMOJI_WEB_SEARCH = eid
                bot_keyboards.CUSTOM_EMOJI_WEB_SEARCH = eid
                os.environ["CUSTOM_EMOJI_WEB_SEARCH"] = eid
                await db.set_setting("custom_emoji_web_search", eid)
                await message.reply(f"✅ شناسه ایموجی متحرک سرچ وب به `{eid}` تنظیم شد.", parse_mode="Markdown")
                return

        if user_text.startswith("/set_thinking_emoji"):
            parts = user_text.split()
            if len(parts) > 1 and parts[1].isdigit():
                eid = parts[1].strip()
                import os
                from app.bot import config as bot_config
                bot_config.CUSTOM_EMOJI_THINKING = eid
                os.environ["CUSTOM_EMOJI_THINKING"] = eid
                await db.set_setting("custom_emoji_thinking", eid)
                try:
                    env_path = bot_config.BASE_DIR / ".env"
                    if env_path.exists():
                        txt = env_path.read_text(encoding="utf-8")
                        if "CUSTOM_EMOJI_THINKING=" in txt:
                            lines = [f"CUSTOM_EMOJI_THINKING={eid}" if l.startswith("CUSTOM_EMOJI_THINKING=") else l for l in txt.splitlines()]
                            env_path.write_text("\n".join(lines), encoding="utf-8")
                        else:
                            env_path.write_text(txt + f"\nCUSTOM_EMOJI_THINKING={eid}\n", encoding="utf-8")
                except Exception:
                    pass
                await message.reply(f"✅ شناسه ایموجی متحرک در حال فکر کردن به `{eid}` تنظیم شد.", parse_mode="Markdown")
                return

    # 1.5. If the active model is Image Studio or user explicitly asked for an image
    image_prefixes = [
        "عکس بساز از", "عکس بساز", "تصویر بساز از", "تصویر بساز",
        "یک عکس از", "یک تصویر از", "نقاشی از", "تولید عکس از", "تولید تصویر از"
    ]
    matched_prefix = next((p for p in image_prefixes if user_text.startswith(p)), None)

    if model_caps.get("is_image_studio", False) or matched_prefix:
        from app.bot.handlers.image import execute_text_generation, get_user_settings
        clean_prompt = user_text
        if matched_prefix:
            clean_prompt = user_text[len(matched_prefix):].lstrip(": ").strip()
        if not clean_prompt:
            clean_prompt = user_text
        ratio, size = await get_user_settings(state, message.from_user.id)
        await execute_text_generation(message, clean_prompt, ratio, size, state)
        return

    # 1.6. If user explicitly asked for a video or video model is active
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
        ratio, seconds, size = await get_user_video_settings(state, message.from_user.id)
        await execute_video_generation(message, prompt=clean_prompt, mode="text", ratio=ratio, seconds=seconds, size=size)
        return

    # 3. Fetch sliding-window chat history
    history = await db.get_chat_history(user_id)
    chat_messages = list(history)
    chat_messages.append({"role": "user", "content": user_text})

    # 4. Concurrency control per-user and globally
    user_lock = await ConcurrencyManager.get_user_lock(user_id)
    async with user_lock:
        async with ConcurrencyManager.acquire_slot():
            # Send initial typing action
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

            # Determine stylish waiting message with animated custom thinking emoji in FRONT of text (جلوی متن)
            from app.bot import config as bot_config
            thinking_eid = getattr(bot_config, "CUSTOM_EMOJI_THINKING", "") or "5334904192622403796"
            thinking_tag = f'<tg-emoji emoji-id="{thinking_eid}">🫥</tg-emoji>'

            if "reasoner" in selected_model.lower() or "r1" in selected_model.lower() or "atria" in selected_model.lower() or "dawn" in selected_model.lower() or "agnes" in selected_model.lower():
                wait_text = f"{thinking_tag} <b>در حال تفکر عمیق و تحلیل مسئله...</b>"
            elif web_search_enabled:
                wait_text = f"{thinking_tag} <b>در حال تفکر و جستجو در وب...</b>"
            else:
                wait_text = f"{thinking_tag} <b>در حال فکر کردن...</b>"

            waiting_msg = await message.answer(wait_text, parse_mode="HTML")

            # Keep sending typing action in background while streaming
            typing_task = asyncio.create_task(keep_typing(message))

            # Real-Time Streaming Engine for sub-second perceived response latency
            from app.bot.streaming import TelegramStreamEngine
            stream_engine = TelegramStreamEngine(
                bot=message.bot,
                chat_id=message.chat.id,
                placeholder_msg=waiting_msg,
                model_name=selected_model,
                thinking_tag=thinking_tag,
            )

            try:
                async for event in gateway.stream_chat(
                    messages=chat_messages,
                    model_id=selected_model,
                    enable_web_search=web_search_enabled
                ):
                    await stream_engine.process_event(event)

                # Cancel background typing indicator
                typing_task.cancel()

                # Finalize formatted message and send overflow chunks if needed
                full_content, full_thinking = await stream_engine.finalize()

                # Save user and assistant messages asynchronously in background (zero disk I/O wait)
                asyncio.create_task(db.add_message(user_id, "user", user_text, model=selected_model))
                asyncio.create_task(db.add_message(user_id, "assistant", full_content, model=selected_model))

            except Exception as e:
                typing_task.cancel()
                print(f"[ChatHandler] Exception for user {user_id}: {e}")
                try:
                    await waiting_msg.edit_text(f"⚠️ متاسفانه خطایی در پردازش رخ داد:\n{str(e)[:150]}")
                except Exception:
                    await message.answer(f"⚠️ متاسفانه خطایی در پردازش رخ داد:\n{str(e)[:150]}")


async def keep_typing(message: Message):
    """Periodically sends typing action to Telegram while generating."""
    try:
        while True:
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
            await asyncio.sleep(4.0)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
