"""
Chat handlers for general text messages, photo analysis, document/file analysis (PDF, DOCX, Code, TXT),
and conversational memory.
All file and photo analyses are processed by the user's active AI model.
"""
import io
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from database import db
from api_services import route_chat_completion, route_vision_completion
from api_services.gemini import gemini_client
from utils.text_helpers import split_text_for_telegram, clean_math_formatting, send_formatted_telegram_response
from utils.file_parser import parse_uploaded_file, extract_images_from_pdf
from keyboards import get_photo_actions_keyboard, get_cancel_keyboard, get_loading_keyboard
from handlers.agnes_media import MediaStates, process_image_edit, process_image_animation
from config import AVAILABLE_MODELS

router = Router()
logger = logging.getLogger(__name__)

# In-memory cache for recent user photos
USER_LAST_PHOTO: dict = {}

@router.message(F.text)
async def handle_user_text(message: Message):
    # Ignore commands or buttons that are handled elsewhere
    if message.text.startswith("/") or message.text in (
        "تغییر مدل هوشمند", "تغییر مدل هوش مصنوعی", "🤖 تغییر مدل هوشمند", "🤖 تغییر مدل هوش مصنوعی",
        "مدل هوشمند پرو", "استدلال عمیق (Atria)", "🧠 مدل هوشمند پرو", "🧠 استدلال عمیق (Atria)",
        "ساخت عکس", "تولید عکس", "🎨 ساخت عکس", "🎨 تولید عکس",
        "ادیت عکس", "ادیت و ترکیب عکس‌ها", "✏️ ادیت عکس", "✏️ ادیت و ترکیب عکس‌ها",
        "تولید ویدیو", "🎬 تولید ویدیو", "متحرک‌سازی عکس", "🎞 متحرک‌سازی عکس",
        "پاکسازی گفتگو", "🗑 پاکسازی گفتگو", "راهنما و وضعیت", "ℹ️ راهنما و وضعیت",
        "پنل مدیریت", "⚙️ پنل مدیریت", "انصراف و بازگشت", "❌ انصراف و بازگشت"
    ):
        return

    user_id = message.from_user.id
    user_prompt = message.text.strip()

    # Get active model for user
    user_model = await db.get_user_model(user_id)
    model_info = AVAILABLE_MODELS.get(user_model, {})
    model_name = model_info.get("name", user_model)

    # Clean thinking status without parentheses + animated loading keyboard
    thinking_text = f"🧠 **در حال فکر کردن و پردازش پاسخ...**\nمدل: **{model_name}** ⏳"
    thinking_msg = await message.answer(
        thinking_text,
        parse_mode="Markdown",
        reply_markup=get_loading_keyboard(f"در حال پردازش با {model_name}...")
    )

    # Send typing action in background
    async def keep_typing():
        while True:
            try:
                await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(4.0)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    typing_task = asyncio.create_task(keep_typing())

    try:
        # Get conversation history for multi-turn context
        history = await db.get_history(user_id, limit=8)
        history.append({"role": "user", "content": user_prompt})

        # Call AI model
        response_text = await route_chat_completion(model_name=user_model, messages=history)

        # Save to history
        await db.add_message(user_id, role="user", content=user_prompt, model=user_model)
        await db.add_message(user_id, role="assistant", content=response_text, model=user_model)

        # Send response formatted with Telegram HTML blockquotes, code, and math
        await send_formatted_telegram_response(
            target_message=message,
            response_text=response_text,
            status_msg=thinking_msg
        )

    except Exception as e:
        logger.error(f"Error handling chat message: {e}")
        await thinking_msg.edit_text("متأسفانه در پردازش پاسخ خطایی رخ داد. لطفاً مجدداً تلاش فرمایید.")
    finally:
        typing_task.cancel()

# ================= DOCUMENT & FILE HANDLER (PDF, DOCX, TXT, CODE) =================
@router.message(F.document)
async def handle_user_document(message: Message):
    """Handle files and documents (PDF, Word, Code, Text, Uncompressed images)."""
    doc = message.document
    user_id = message.from_user.id
    file_name = doc.file_name or "document"

    # Telegram Bot API file download limit is 20MB
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.answer("⚠️ حجم فایل بیش از حد مجاز تلگرام (۲۰ مگابایت) است. لطفاً فایل کم‌حجم‌تری ارسال فرمایید.")
        return

    # Download file into memory
    file_io = io.BytesIO()
    await message.bot.download(doc, destination=file_io)
    file_bytes = file_io.getvalue()

    # Parse document
    file_type, extracted_text, count = parse_uploaded_file(file_name, file_bytes)

    # If it's an uncompressed image sent as document
    if file_type == "image":
        USER_LAST_PHOTO[user_id] = file_bytes
        caption = message.caption
        if caption and len(caption.strip()) > 1:
            await _process_photo_analysis(message, file_bytes, caption.strip())
        else:
            await message.answer(
                f"📸 **تصویر {file_name} دریافت شد!**\nیکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=get_photo_actions_keyboard(),
                parse_mode="Markdown"
            )
        return

    # If unsupported file
    if file_type == "unsupported":
        await message.answer(
            f"⚠️ فرمت فایل `{file_name}` پشتیبانی نمی‌شود.\n\n"
            "📄 **فرمت‌های مجاز:**\n"
            "• کتاب و اسناد: `PDF` و `Word (.docx)`\n"
            "• متن و داده: `.txt`, `.csv`, `.json`, `.md`\n"
            "• کدهای برنامه‌نویسی: `.py`, `.js`, `.html`, `.css`, `.sql` و ...\n"
            "• تصاویر: `JPG`, `PNG`, `WebP`",
            parse_mode="Markdown"
        )
        return

    # User active model
    user_model = await db.get_user_model(user_id)
    model_info = AVAILABLE_MODELS.get(user_model, {})
    model_name = model_info.get("name", user_model)

    caption_text = message.caption.strip() if message.caption else ""
    if caption_text:
        doc_instruction = (
            f"🎯 دستور یا پرسش کاربر:\n{caption_text}\n\n"
            f"بر اساس محتوای سند پیوست‌شده، به این پرسش یا حل سوال به سبک تمیز و حرفه‌ای اپلیکیشن ChatGPT پاسخ بده:\n"
            f"- از نقل‌قول (Quote با علامت >) برای صورت سوال، فرمول‌های کلیدی و پاسخ نهایی استفاده کن.\n"
            f"- مراحل را گام‌به‌گام با تیترهای منظم و فرمول‌های تمیز یونیکد (²، ³، √، ∫، ·، ➜) بنویس."
        )
    else:
        doc_instruction = (
            "🎯 وظیفه شما:\n"
            "۱. مشخصات برگه امتحانی و جدول تفکیک‌شده فهرست سوالات (شماره، موضوع، بارم) را مرتب بنویس.\n"
            "۲. سوال ۱ را به عنوان نمونه به سبک تمیز و زیبای اپلیکیشن ChatGPT حل کن:\n"
            "   > 📌 **صورت سوال ۱:**\n"
            "   > 💡 **فرمول کلیدی / ایده حل:**\n"
            "   مراحل گام‌به‌گام با نمادهای یونیکد (بدون خرد کردن در بلوک کد)\n"
            "   > 🏁 **پاسخ نهایی سوال ۱:**\n"
            "۳. در پایان با لحنی محترمانه اعلام کن که برای دریافت حل تشریحی سایر سوالات می‌توانند از دکمه‌های زیر استفاده کنند یا شماره آن را ارسال نمایند."
        )

    formatting_rules = (
        "\n\n📐 **استاندارد حیاتی زیبایی و تمیزی نگارش ریاضی (به سبک اپلیکیشن ChatGPT):**\n"
        "• برای این بخش‌ها حتماً از نقل‌قول (Quote با علامت >) استفاده کنید:\n"
        "  > 📌 **صورت سوال:**\n"
        "  > 💡 **فرمول‌های کلیدی:**\n"
        "  > 🏁 **پاسخ نهایی:**\n"
        "• هرگز پاسخ‌ها را با ده‌ها بلوک کد خاکستری (```) قطعه‌قطعه نکنید. محاسبات باید روان و زیبا در متن با نمادهای یونیکد (²، ³، √، ∫، ·، ➜) نوشته شوند.\n"
        "• مراحل حل را با تیترهای مشخص (گام ۱، گام ۲، ...) توضیح دهید."
    )

    # Case A: Text was successfully extracted from PDF, DOCX, or Text file
    if extracted_text and len(extracted_text.strip()) > 0:
        info_prefix = f"📄 **تعداد صفحات/بخش‌ها:** {count}\n" if file_type == "pdf" and count > 1 else ""
        thinking_msg = await message.answer(
            f"📄 **در حال مطالعه عمیق و حل تشریحی مسائل سند با مدل {model_name}...** ⏳\n"
            f"📁 نام فایل: `{file_name}`\n{info_prefix}",
            parse_mode="Markdown",
            reply_markup=get_loading_keyboard(f"در حال تحلیل سند با {model_name}...")
        )

        async def keep_doc_typing():
            while True:
                try:
                    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                    await asyncio.sleep(4.0)
                except (asyncio.CancelledError, Exception):
                    break

        typing_task = asyncio.create_task(keep_doc_typing())

        try:
            # Build unified context with extracted text (up to 35,000 characters)
            context_text = (
                f"📄 [محتوای سند پیوست شده: {file_name}]\n\n"
                f"```text\n{extracted_text[:35000]}\n```\n\n"
                f"────────────────────\n"
                f"{doc_instruction}"
                f"{formatting_rules}"
            )

            response_text = await route_chat_completion(
                model_name=user_model,
                messages=[{"role": "user", "content": context_text}]
            )

            # Record in conversation history with full extracted text up to 8000 chars so follow-up question solving has full context!
            record_prompt = f"[فایل {file_name}]:\n{extracted_text[:8000]}\n\nدرخواست کاربر: {caption_text or 'تحلیل برگه و حل سوال ۱'}"
            await db.add_message(user_id, role="user", content=record_prompt, model=user_model)
            await db.add_message(user_id, role="assistant", content=response_text, model=user_model)

            # Quick interactive buttons for questions 2 to 7
            exam_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔢 حل سوال ۲", callback_data="solve_q:2"), InlineKeyboardButton(text="🔢 حل سوال ۳", callback_data="solve_q:3")],
                [InlineKeyboardButton(text="🔢 حل سوال ۴", callback_data="solve_q:4"), InlineKeyboardButton(text="🔢 حل سوال ۵", callback_data="solve_q:5")],
                [InlineKeyboardButton(text="🔢 حل سوال ۶", callback_data="solve_q:6"), InlineKeyboardButton(text="🔢 حل سوال ۷", callback_data="solve_q:7")]
            ])

            # Deliver response with native Telegram HTML blockquotes, code, and math
            await send_formatted_telegram_response(
                target_message=message,
                response_text=response_text,
                status_msg=thinking_msg,
                reply_markup=exam_kb
            )

        except Exception as e:
            logger.error(f"Document analysis error: {e}")
            await thinking_msg.edit_text("متأسفانه در تحلیل محتوای سند مشکلی پیش آمد. لطفاً مجدداً امتحان کنید.")
        finally:
            typing_task.cancel()

    # Case B: PDF has no extractable text (Scanned images / OCR needed)
    elif file_type == "pdf":
        thinking_msg = await message.answer(
            f"📄 **سند تصویری/اسکن‌شده شناسایی شد.**\n"
            f"در حال تحلیل بینایی، بازخوانی سوالات و حل تشریحی مسائل با مدل {model_name}... ⏳",
            parse_mode="Markdown"
        )
        try:
            prompt_for_scanned = f"{doc_instruction}{formatting_rules}"
            pdf_images = extract_images_from_pdf(file_bytes, max_images=3)

            if pdf_images:
                # Analyze primary page image with vision router
                analysis = await route_vision_completion(
                    model_name=user_model,
                    image_bytes=pdf_images[0],
                    mime_type="image/jpeg",
                    prompt=prompt_for_scanned
                )
            else:
                # Direct route
                analysis = await route_vision_completion(
                    model_name=user_model,
                    image_bytes=file_bytes,
                    mime_type="application/pdf",
                    prompt=prompt_for_scanned
                )

            await send_formatted_telegram_response(
                target_message=message,
                response_text=analysis,
                status_msg=thinking_msg
            )
        except Exception as e:
            logger.error(f"Scanned PDF analysis error: {e}")
            await thinking_msg.edit_text("متأسفانه در پردازش بینایی فایل PDF مشکلی پیش آمد.")
    else:
        await message.answer("⚠️ متنی در این فایل یافت نشد یا فرمت فایل پشتیبانی نمی‌شود.")

# ================= PHOTO HANDLER =================
async def _process_photo_analysis(message: Message, image_bytes: bytes, prompt: str):
    """Helper to process photo vision with active AI model."""
    user_id = message.from_user.id
    user_model = await db.get_user_model(user_id)
    model_info = AVAILABLE_MODELS.get(user_model, {})
    model_name = model_info.get("name", user_model)

    thinking_msg = await message.answer(
        f"👁 **در حال بررسی تصویر با مدل {model_name}...** ⏳",
        parse_mode="Markdown",
        reply_markup=get_loading_keyboard(f"در حال تحلیل تصویر با {model_name}...")
    )

    async def keep_vision_typing():
        while True:
            try:
                await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(4.0)
            except (asyncio.CancelledError, Exception):
                break

    typing_task = asyncio.create_task(keep_vision_typing())

    try:
        refined_prompt = (
            f"{prompt}\n\n"
            "💎 **استاندارد حیاتی زیبایی و تمیزی نگارش (به سبک اپلیکیشن ChatGPT):**\n"
            "• از نقل‌قول (Quote با علامت >) برای صورت سوال، فرمول‌های کلیدی و پاسخ نهایی استفاده کنید.\n"
            "• مسائل و روابط ریاضی را با نمادهای تمیز یونیکد (²، ³، √، ∫، ·، ➜) بدون خرد کردن در ده‌ها بلوک کد حل کنید."
        )

        analysis = await route_vision_completion(
            model_name=user_model,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            prompt=refined_prompt
        )

        # Save to history
        await db.add_message(user_id, role="user", content=f"[تصویر]: {prompt}", model=user_model)
        await db.add_message(user_id, role="assistant", content=analysis, model=user_model)

        await send_formatted_telegram_response(
            target_message=message,
            response_text=analysis,
            status_msg=thinking_msg
        )

    except Exception as e:
        logger.error(f"Photo analysis error: {e}")
        await thinking_msg.edit_text("متأسفانه در تحلیل تصویر مشکلی پیش آمد.")
    finally:
        typing_task.cancel()

@router.message(F.photo)
async def handle_user_photo(message: Message):
    """Handle photos sent directly in chat."""
    photo = message.photo[-1]
    file_io = io.BytesIO()
    await message.bot.download(photo, destination=file_io)
    image_bytes = file_io.getvalue()

    # Save to user cache
    USER_LAST_PHOTO[message.from_user.id] = image_bytes

    caption = message.caption

    # If user provided a question in the caption, analyze immediately with active model
    if caption and len(caption.strip()) > 1:
        await _process_photo_analysis(message, image_bytes, caption.strip())
    else:
        # If no caption, offer quick action buttons
        await message.answer(
            "📸 **تصویر شما با موفقیت دریافت شد!**\n\n"
            "مایلید چه کاری روی این تصویر انجام دهم؟\n"
            "یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=get_photo_actions_keyboard(),
            parse_mode="Markdown"
        )

# ================= PHOTO ACTION CALLBACKS =================
@router.callback_query(F.data == "photo:edit")
async def cb_photo_edit(callback: CallbackQuery, state: FSMContext):
    image_bytes = USER_LAST_PHOTO.get(callback.from_user.id)
    if not image_bytes:
        await callback.answer("عکس در حافظه موقت منقضی شده است. لطفاً عکس را مجدداً ارسال کنید.", show_alert=True)
        return

    await state.update_data(images_list=[image_bytes])
    await state.set_state(MediaStates.waiting_for_edit_instruction)
    await callback.message.answer(
        "✏️ **دستور ادیت و ترکیب را بنویسید:**\n\n"
        "چه تغییری با مدل هوشمند پرو روی این عکس اعمال شود؟ (مثلاً: `لباسش را رسمی کن`، `پس‌زمینه را به طبیعت تغییر بده` یا پرامپت دلخواه)",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data == "photo:animate")
async def cb_photo_animate(callback: CallbackQuery):
    image_bytes = USER_LAST_PHOTO.get(callback.from_user.id)
    if not image_bytes:
        await callback.answer("عکس در حافظه موقت منقضی شده است. لطفاً عکس را مجدداً ارسال کنید.", show_alert=True)
        return

    await callback.answer("در حال شروع متحرک‌سازی با مدل هوشمند پرو... 🎬")
    await process_image_animation(callback.message, image_bytes, prompt="Smooth cinematic motion, natural lifelike animation")

@router.callback_query(F.data == "photo:analyze")
async def cb_photo_analyze(callback: CallbackQuery):
    image_bytes = USER_LAST_PHOTO.get(callback.from_user.id)
    if not image_bytes:
        await callback.answer("عکس در حافظه موقت منقضی شده است. لطفاً عکس را مجدداً ارسال کنید.", show_alert=True)
        return

    await callback.answer("در حال شروع تحلیل...")
    await _process_photo_analysis(
        callback.message,
        image_bytes,
        prompt="این تصویر را به طور جامع، با تمام جزئیات و عناصر موجود در آن، به زبان فارسی روان تحلیل و توصیف کن."
    )

@router.message(F.voice)
async def handle_user_voice(message: Message):
    """Voice note message handler."""
    await message.answer(
        "🎙 پیام صوتی شما دریافت شد! لطفاً پرسش خود را به صورت متنی بنویسید تا توسط مدل‌های هوش مصنوعی پاسخ داده شود."
    )

@router.callback_query(F.data.startswith("solve_q:"))
async def cb_solve_question(callback: CallbackQuery):
    """Handle interactive question solving buttons for documents and exams."""
    q_num = callback.data.split(":")[1]
    await callback.answer(f"در حال حل سوال {q_num}...")
    user_id = callback.from_user.id
    user_model = await db.get_user_model(user_id)
    model_info = AVAILABLE_MODELS.get(user_model, {})
    model_name = model_info.get("name", user_model)

    status_msg = await callback.message.answer(
        f"🔢 **در حال حل تشریحی و گام‌به‌گام سوال {q_num} با مدل {model_name}...** ⏳",
        parse_mode="Markdown",
        reply_markup=get_loading_keyboard(f"در حال حل سوال {q_num} با {model_name}...")
    )

    try:
        history = await db.get_history(user_id, limit=6)
        history.append({
            "role": "user",
            "content": (
                f"بر اساس سند و فایل ارسالی، لطفاً سوال {q_num} را دقیقاً به سبک تمیز و زیبای اپلیکیشن ChatGPT حل کن:\n"
                f"- از Quote (با علامت >) برای صورت سوال، فرمول‌های کلیدی و پاسخ نهایی استفاده کن:\n"
                f"  > 📌 **صورت سوال {q_num}:**\n"
                f"  > 💡 **فرمول کلیدی / ایده حل:**\n"
                f"  > 🏁 **پاسخ نهایی سوال {q_num}:**\n"
                f"- مراحل حل را گام‌به‌گام با تیترهای منظم (گام ۱، گام ۲، ...) بنویس.\n"
                f"- فرمول‌ها را بسیار شیک با نمادهای تمیز یونیکد (²، ³، √، ∫، ·، ➜) بنویس و از خرد کردن در ده‌ها بلوک کد خودداری کن."
            )
        })

        response_text = await route_chat_completion(model_name=user_model, messages=history)
        await db.add_message(user_id, role="user", content=f"حل سوال {q_num}", model=user_model)
        await db.add_message(user_id, role="assistant", content=response_text, model=user_model)

        await send_formatted_telegram_response(
            target_message=callback.message,
            response_text=response_text,
            status_msg=status_msg
        )
    except Exception as e:
        logger.error(f"Error solving question {q_num}: {e}")
        await status_msg.edit_text(f"متأسفانه در حل سوال {q_num} مشکلی رخ داد. لطفاً مجدداً امتحان فرمایید.")

@router.callback_query(F.data == "loading_notice")
async def handle_loading_notice(callback: CallbackQuery):
    """Answers clicks on the animated loading indicator button."""
    await callback.answer("⏳ شکیبا باشید، پردازش با هوش مصنوعی در حال انجام است...", show_alert=False)


