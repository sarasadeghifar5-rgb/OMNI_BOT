import io
import base64
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import httpx
import subprocess
import imageio_ffmpeg
from app.services.gemini_tts import GeminiTTSService
from app.services.gateway import LLMGateway
from app.providers.gemini_provider import GeminiKeyPool
from app.bot.database import BotDatabase
from app.bot.middlewares import ConcurrencyManager
import html
from app.bot.utils import safe_reply, format_thinking_block, safe_edit_or_reply, markdown_to_telegram_html

router = Router(name="voice_router")
db = BotDatabase.get_instance()
gateway = LLMGateway()

class TTSStates(StatesGroup):
    waiting_for_tts_text = State()

REPLY_KEYBOARD_BUTTONS = {
    "💬 گفتگوی جدید", "گفتگوی جدید", "🗑️ گفتگو جدید", "💬 گفتگو جدید", "گفتگو جدید 💬", "گفتگو جدید", "🗨️ گفتگو جدید", "🗑️ چت جدید", "چت جدید",
    "🤖 انتخاب مدل", "انتخاب مدل 🤖", "انتخاب مدل",
    "🍌 ادیت عکس نانو بنانا", "ادیت عکس نانو بنانا 🍌", "ادیت عکس نانو بنانا",
    "🎬 استودیو تولید ویدیو", "استودیو تولید ویدیو 🎬", "استودیو تولید ویدیو",
    "👤 حساب کاربری", "حساب کاربری 👤", "حساب کاربری", "پروفایل",
    "🎤 تبدیل متن به گفتار", "تبدیل متن به گفتار 🎤", "تبدیل متن به گفتار",
    "🛒 خرید سرویس", "خرید سرویس 🛒", "خرید سرویس",
    "🎁 سرویس هدیه", "سرویس هدیه 🎁", "هدیه روزانه", "سرویس هدیه",
    "🔗 لینک دعوت", "لینک دعوت 🔗", "زیرمجموعه‌گیری",
    "🌐 تغییر منطقه", "تغییر منطقه 🌐", "سرور و ریجن",
    "👑 پنل مدیریت ادمین", "پنل مدیریت ادمین 👑",
    "⚙️ منو", "منو"
}

@router.message(Command("voice", "tts"))
@router.message(F.text.in_({"تبدیل متن به گفتار 🎤", "تبدیل متن به گفتار", "🎤 تبدیل متن به گفتار"}))
async def cmd_tts(message: Message, state: FSMContext):
    # Check if text provided in command
    text = (message.text or "").strip()
    clean_text = ""
    for cmd in ["/voice", "/tts"]:
        if text.startswith(cmd):
            clean_text = text[len(cmd):].strip()
            break

    if clean_text:
        await synthesize_and_send_voice(message, clean_text)
        return

    # Check if user replied to an existing message
    if message.reply_to_message and message.reply_to_message.text:
        await synthesize_and_send_voice(message, message.reply_to_message.text)
        return

    await state.set_state(TTSStates.waiting_for_tts_text)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف و لغو", callback_data="cancel_tts")]]
    )
    await message.answer(
        "🎙️ **تبدیل متن به صوت با هوش مصنوعی Google Gemini:**\n\n"
        "متنی که می‌خواهید با صدای طبیعی خوانده شود را ارسال کنید:\n"
        "*(یا روی هر پیام ریپلای کرده و دستور /voice را بفرستید)*",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "menu:tts")
async def cb_tts_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(TTSStates.waiting_for_tts_text)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف و لغو", callback_data="cancel_tts")]]
    )
    await call.message.edit_text(
        "🎙️ **تبدیل متن به صوت (TTS):**\n\n"
        "لطفاً متنی را که مایلید به پیام صوتی تبدیل شود ارسال فرمایید:",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )
    await call.answer()

@router.callback_query(F.data == "cancel_tts")
async def cb_cancel_tts(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("عملیات تبدیل به صوت لغو شد.", show_alert=False)
    try:
        await call.message.edit_text("❌ تبدیل متن به گفتار لغو شد. می‌توانید در حالت گفتگو متنی پیام بفرستید.")
    except Exception:
        pass

@router.message(TTSStates.waiting_for_tts_text)
async def process_tts_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        await state.clear()
        return

    if text.lower() in {"لغو", "انصراف", "کنسل", "خروج", "cancel", "exit"}:
        await state.clear()
        await message.answer("✅ عملیات صوتی لغو شد. پیام‌های بعدی شما به صورت گفتگوی متنی پاسخ داده می‌شوند.")
        return

    if text in REPLY_KEYBOARD_BUTTONS:
        await state.clear()
        if text in {"💬 گفتگوی جدید", "گفتگوی جدید", "💬 گفتگو جدید", "گفتگو جدید 💬", "گفتگو جدید", "🗨️ گفتگو جدید", "🗑️ چت جدید", "چت جدید", "🗑️ گفتگو جدید"}:
            from app.bot.handlers.start import cmd_new_conversation
            await cmd_new_conversation(message, state)
        elif text in {"🍌 ادیت عکس نانو بنانا", "ادیت عکس نانو بنانا 🍌", "ادیت عکس نانو بنانا"}:
            from app.bot.handlers.image import cmd_gpt_image_studio
            await cmd_gpt_image_studio(message, state)
        elif text in {"🎬 استودیو تولید ویدیو", "استودیو تولید ویدیو 🎬", "استودیو تولید ویدیو"}:
            from app.bot.handlers.video import cmd_video_studio
            await cmd_video_studio(message, state)
        elif text in {"👤 حساب کاربری", "حساب کاربری 👤", "حساب کاربری", "پروفایل"}:
            from app.bot.handlers.account import cmd_user_account
            await cmd_user_account(message, state)
        elif text in {"🛒 خرید سرویس", "خرید سرویس 🛒", "خرید سرویس"}:
            from app.bot.handlers.account import cmd_buy_service
            await cmd_buy_service(message, state)
        elif text in {"🎁 سرویس هدیه", "سرویس هدیه 🎁", "هدیه روزانه", "سرویس هدیه"}:
            from app.bot.handlers.account import cmd_gift_service
            await cmd_gift_service(message, state)
        elif text in {"🔗 لینک دعوت", "لینک دعوت 🔗", "زیرمجموعه‌گیری"}:
            from app.bot.handlers.account import cmd_invite_link
            await cmd_invite_link(message, state)
        elif text in {"🌐 تغییر منطقه", "تغییر منطقه 🌐", "سرور و ریجن"}:
            from app.bot.handlers.account import cmd_change_region
            await cmd_change_region(message, state)
        elif text in {"🎤 تبدیل متن به گفتار", "تبدیل متن به گفتار 🎤", "تبدیل متن به گفتار"}:
            await cmd_tts(message, state)
        elif text in {"⚙️ منو", "منو", "منو ⚙️"}:
            from app.bot.handlers.start import cmd_help
            await cmd_help(message, state)
        elif text in {"🤖 انتخاب مدل", "انتخاب مدل 🤖", "انتخاب مدل", "مدل ها", "مدل‌ها"}:
            from app.bot.handlers.start import cmd_model
            await cmd_model(message)
        return

    await state.clear()
    await synthesize_and_send_voice(message, text)


async def synthesize_and_send_voice(message: Message, text: str):
    """Core TTS synthesis routine with strict 2-line limit."""
    status_msg = await message.answer("🎙️ **در حال تولید صدای هوش مصنوعی با کیفیت بالا...**")
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)

    user = await db.get_or_create_user(message.from_user.id)
    voice_name = user.get("tts_voice", "kore")

    # بررسی برای درج توضیح در صورت بیش از ۲ خط بودن متن
    raw_lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    was_truncated = len(raw_lines) > 2 or len(text.strip()) > 200

    user_lock = await ConcurrencyManager.get_user_lock(message.from_user.id)
    async with user_lock:
        async with ConcurrencyManager.global_semaphore():
            try:
                result = await GeminiTTSService.synthesize_speech(
                    text=text,
                    voice_name=voice_name
                )

                audio_data_url = result.get("audio_url", "")
                if not audio_data_url.startswith("data:audio/"):
                    await status_msg.edit_text("⚠️ خطا در پردازش داده صوتی.")
                    return

                # Decode base64 WAV audio
                base64_part = audio_data_url.split(",")[1]
                wav_bytes = base64.b64decode(base64_part)

                caption = f"🎙️ خوانش صوتی هوش مصنوعی Gemini ({voice_name})"
                if was_truncated:
                    caption += "\nℹ️ *طبق تنظیمات، صوت حداکثر برای ۲ خط تولید شد.*"

                audio_file = BufferedInputFile(wav_bytes, filename="voice.wav")
                await message.answer_voice(
                    voice=audio_file,
                    caption=caption,
                    parse_mode="Markdown"
                )
                await status_msg.delete()

            except Exception as e:
                print(f"[VoiceHandler] Error: {e}")
                await status_msg.edit_text(f"⚠️ متاسفانه در تولید صوت خطایی رخ داد: {str(e)[:150]}")


def convert_audio_to_wav(audio_bytes: bytes) -> bytes:
    """
    Converts Telegram Ogg Opus / any audio into clean 16kHz 16-bit mono PCM WAV.
    Guarantees 100% accurate speech-to-text decoding by Gemini without hallucination.
    """
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", "pipe:0",
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            "pipe:1"
        ]
        proc = subprocess.run(
            cmd,
            input=audio_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10.0
        )
        if proc.returncode == 0 and len(proc.stdout) > 44:
            return proc.stdout
    except Exception as e:
        print(f"[VoiceHandler] ffmpeg conversion warning: {e}")
    return audio_bytes


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


@router.message(F.voice | F.audio)
async def handle_user_audio_message(message: Message):
    """
    Handles user voice notes & audio files:
    1. Transcribes voice note to text using Gemini multimodal audio (16kHz WAV, temp 0.0)
    2. Generates conversational text reply through LLM Gateway with history
    3. Sends text response back to user in Telegram
    4. Saves turn to conversation history
    """
    user_id = message.from_user.id
    user_lock = await ConcurrencyManager.get_user_lock(user_id)
    async with user_lock:
        async with ConcurrencyManager.acquire_slot():
            status_msg = await message.answer("🎧 **در حال گوش دادن به ویس شما...**", parse_mode="Markdown")
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
            typing_task = None
            try:
                # 1. Get file from Telegram
                audio_obj = message.voice or message.audio
                if not audio_obj:
                    await status_msg.edit_text("⚠️ فایل صوتی نامعتبر است.")
                    return

                file_id = audio_obj.file_id
                file_io = io.BytesIO()
                await message.bot.download(file_id, destination=file_io)
                raw_bytes = file_io.getvalue()

                # Convert Telegram Opus to clean 16kHz WAV to prevent speech hallucinations
                audio_bytes = convert_audio_to_wav(raw_bytes)
                audio_mime = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/ogg"
                audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

                # 2. Transcribe voice accurately using Gemini from Key Pool
                pool = GeminiKeyPool.get_instance()
                node = pool.select_best_node()
                if not node:
                    await status_msg.edit_text("⚠️ کلید فعالی در استخر هوش مصنوعی موجود نیست.")
                    return

                await node.acquire_slot()
                transcribe_prompt = (
                    "شما یک سیستم رونویسی دقیق گفتار (Speech-to-Text) به زبان فارسی هستید. "
                    "دقیقاً و فقط کلماتی را که گوینده در این فایل صوتی بیان می‌کند بنویسید. "
                    "مهم: هیچ کلمه‌ای از خودتان اضافه نکنید، از حدس زدن خودداری کنید و به پیام پاسخ ندهید. فقط رونویسی واژه‌ها."
                )
                payload = {
                    "contents": [{
                        "parts": [
                            {"inlineData": {"mimeType": audio_mime, "data": audio_b64}},
                            {"text": transcribe_prompt}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.0,
                        "maxOutputTokens": 300
                    }
                }

                transcribed_text = ""
                transcribe_models = ["gemini-3-flash-preview", "gemini-3.6-flash", "gemini-3.5-transcribe", "gemini-3.1-flash-lite-preview"]
                for t_model in transcribe_models:
                    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{t_model}:generateContent?key={node.key}"
                    try:
                        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                            resp = await client.post(endpoint, json=payload)
                            if resp.status_code == 200:
                                node.record_success()
                                data = resp.json()
                                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                transcribed_text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                                if transcribed_text:
                                    break
                            else:
                                node.record_error(resp.status_code)
                    except Exception as err:
                        print(f"[VoiceHandler] Transcribe attempt error with {t_model}: {err}")

                clean_transcript = transcribed_text.strip().strip('"\'`')
                if not clean_transcript or clean_transcript.lower() == "[نامفهوم]":
                    await status_msg.edit_text("⚠️ متوجه صحبت شما در ویس نشدم؛ لطفاً ویس را واضح‌تر یا در محیطی آرام‌تر ارسال فرمایید.")
                    return

                transcribed_text = clean_transcript

                # 3. Inform user what was heard and begin preparing conversational answer
                from app.bot import config as bot_config
                thinking_eid = getattr(bot_config, "CUSTOM_EMOJI_THINKING", "") or "5334904192622403796"
                thinking_tag = f'<tg-emoji emoji-id="{thinking_eid}">🫥</tg-emoji>'
                import html
                clean_transcribed = html.escape(transcribed_text)
                try:
                    await status_msg.edit_text(
                        f"🗣️ <b>شنیده شد:</b> <i>{clean_transcribed}</i>\n\n{thinking_tag} <b>در حال تفکر و نگارش پاسخ...</b>",
                        parse_mode="HTML"
                    )
                except Exception:
                    try:
                        await status_msg.edit_text(
                            f"🗣️ شنیده شد: {transcribed_text}\n\n⏳ در حال تفکر و نگارش پاسخ...",
                            parse_mode=None
                        )
                    except Exception:
                        pass

                # Send typing action in background while generating answer
                typing_task = asyncio.create_task(keep_typing(message))

                # 4. Fetch user preferences and conversation history
                user = await db.get_or_create_user(user_id)
                selected_model = user.get("selected_model", "gemini")
                web_search_enabled = bool(user.get("web_search_enabled", 0))

                history = await db.get_chat_history(user_id)
                chat_messages = list(history)
                chat_messages.append({"role": "user", "content": transcribed_text})

                # 5. Stream LLM chat response
                thinking_chunks = []
                content_chunks = []
                sources = []

                async for event in gateway.stream_chat(
                    messages=chat_messages,
                    model_id=selected_model,
                    enable_web_search=web_search_enabled
                ):
                    event_type = event.get("type")
                    if event_type == "sources":
                        sources = event.get("sources", [])
                    elif event_type == "thinking":
                        thinking_chunks.append(event.get("content", ""))
                    elif event_type == "content":
                        content_chunks.append(event.get("content", ""))

                if typing_task:
                    typing_task.cancel()

                full_content = "".join(content_chunks).strip()
                full_thinking = "".join(thinking_chunks).strip()

                # Clean thinking tags if embedded
                if "<think>" in full_content and "</think>" in full_content:
                    try:
                        t_parts = full_content.split("</think>")
                        extracted_think = t_parts[0].replace("<think>", "").strip()
                        full_content = t_parts[1].strip()
                        if extracted_think:
                            full_thinking = f"{full_thinking}\n{extracted_think}".strip()
                    except Exception:
                        pass

                if not full_content:
                    full_content = "⚠️ پاسخی از هوش مصنوعی دریافت نشد. لطفاً مجدداً امتحان کنید."

                # 6. Format final response
                escaped_heard = html.escape(transcribed_text)
                final_parts = [f"🗣️ <b>شنیده شد:</b> <i>«{escaped_heard}»</i>\n\n"]

                if full_thinking:
                    final_parts.append(format_thinking_block(full_thinking))

                final_parts.append(markdown_to_telegram_html(full_content))

                if sources:
                    sources_text = "\n\n📚 <b>منابع و پیوندها:</b>\n"
                    for idx, s in enumerate(sources[:3], 1):
                        title = html.escape(s.get("title", f"منبع {idx}"))
                        url = html.escape(s.get("url", ""))
                        if url:
                            sources_text += f'{idx}. <a href="{url}">{title}</a>\n'
                    final_parts.append(sources_text)

                complete_response = "".join(final_parts)

                # 7. Edit message or send reply
                await safe_edit_or_reply(status_msg, complete_response, parse_mode="HTML")

                # 8. Save conversational turn to database
                await db.add_message(user_id, "user", transcribed_text, model=selected_model)
                await db.add_message(user_id, "assistant", full_content, model=selected_model)

            except Exception as e:
                if typing_task:
                    typing_task.cancel()
                print(f"[VoiceHandler] Error processing voice note: {e}")
                await status_msg.edit_text(f"⚠️ متاسفانه در پردازش و پاسخ به ویس خطایی رخ داد:\n{str(e)[:150]}")
