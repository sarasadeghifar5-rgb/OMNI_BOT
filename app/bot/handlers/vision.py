import io
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext

from app.services.gateway import LLMGateway
from app.services.vision import VisionService
from app.bot.database import BotDatabase
from app.bot.middlewares import ConcurrencyManager
from app.bot.utils import safe_reply, safe_edit_or_reply, markdown_to_telegram_html, detect_aspect_ratio

router = Router(name="vision_router")
gateway = LLMGateway()
vision_service = VisionService()
db = BotDatabase.get_instance()

from app.config import get_model_capabilities
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(F.photo)
async def handle_photo_message(message: Message, state: FSMContext = None):
    """Handles photos sent directly by the user in Telegram."""
    user = await db.get_or_create_user(message.from_user.id)
    user_model = user.get("selected_model", "gemini")
    caps = get_model_capabilities(user_model)

    # Route to studio if studio model is active
    if caps.get("is_image_studio"):
        from app.bot.handlers.image import handle_image_studio_photo
        await handle_image_studio_photo(message, state)
        return

    if caps.get("is_video_studio"):
        from app.bot.handlers.video import handle_video_photo
        await handle_video_photo(message, state)
        return

    # Automatically detect and persist input photo's aspect ratio
    if message.photo:
        photo = message.photo[-1]
        detected_ratio = detect_aspect_ratio(photo.width, photo.height)
        await db.update_user_image_settings(message.from_user.id, ratio=detected_ratio)
        await db.update_user_video_settings(message.from_user.id, ratio=detected_ratio)

    # If the current model does NOT support vision, alert user and offer vision models
    if not caps.get("supports_vision", False):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ سوییچ به Gemini 3.7 Flash (بینایی سریع)", callback_data="set_model:gemini-3.7-flash"),
            ],
            [
                InlineKeyboardButton(text="💎 سوییچ به Claude Opus 5.5 (بینایی عمیق)", callback_data="set_model:claude-opus-5.5"),
            ],
            [
                InlineKeyboardButton(text="🆓 سوییچ به GLM-4V Flash (بینایی رایگان)", callback_data="set_model:glm-4v-flash"),
            ],
            [
                InlineKeyboardButton(text="🍌 ادیت و بازطراحی تصویر (نانو بنانا)", callback_data="menu:gpt_image"),
            ]
        ])
        await message.reply(
            f"⚠️ **مدل فعال شما (`{caps['name']}`) فقط متنی است و از تحلیل تصاویر پشتیبانی نمی‌کند.**\n\n"
            "برای تحلیل، استخراج متن یا ادیت این عکس، لطفاً یکی از مدل‌های بینایی ماشین زیر را انتخاب فرمایید:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    active_model = user_model

    caption = (message.caption or "").strip()
    if not caption:
        caption = "لطفاً این تصویر را با دقت بررسی و تحلیل کرده و محتوای آن را به زبان فارسی توضیح دهید."

    user_lock = await ConcurrencyManager.get_user_lock(message.from_user.id)
    async with user_lock:
        async with ConcurrencyManager.acquire_slot():
            status_msg = await message.answer(f"👁️ <b>در حال دریافت و اسکن تصویر با بینایی ماشین ({active_model})...</b>", parse_mode="HTML")
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
            try:
                # Download largest photo from Telegram
                photo = message.photo[-1]
                file_io = io.BytesIO()
                await message.bot.download(photo.file_id, destination=file_io)
                raw_bytes = file_io.getvalue()

                # Process & compress image to standard data URL
                data_url, width, height = vision_service.process_and_encode_image(
                    file_bytes=raw_bytes,
                    mime_type="image/jpeg"
                )

                # Prepare conversational history
                history = await db.get_chat_history(message.from_user.id)
                messages = list(history)
                messages.append({"role": "user", "content": caption})

                # Stream response from Gateway
                full_reply = ""
                async for event in gateway.stream_chat(
                    messages=messages,
                    model_id=active_model,
                    images=[data_url]
                ):
                    if event.get("type") == "content":
                        full_reply += event.get("content", "")

                if not full_reply.strip():
                    full_reply = "⚠️ متاسفانه پاسخی از مدل بینایی ماشین دریافت نشد."

                # Seamlessly edit status message with beautifully formatted analysis
                formatted_reply = markdown_to_telegram_html(full_reply)
                await safe_edit_or_reply(status_msg, formatted_reply, parse_mode="HTML")

                # Save turn to database
                await db.add_message(message.from_user.id, "user", f"[تصویر]: {caption}", model=active_model, has_images=True)
                await db.add_message(message.from_user.id, "assistant", full_reply, model=active_model)

            except Exception as e:
                print(f"[VisionHandler] Error: {e}")
                await status_msg.edit_text(f"⚠️ خطا در تحلیل تصویر: {str(e)[:150]}")


from app.services.document import DocumentService

@router.message(F.document)
async def handle_document_message(message: Message, state: FSMContext = None):
    """
    Handles PDF documents, text/code files, and uncompressed images sent by users.
    Enables deep document analysis, summarization, and Q&A across all models.
    """
    doc = message.document
    file_name = doc.file_name or "document.pdf"
    file_size = doc.file_size or 0
    mime_type = (doc.mime_type or "").lower()
    caption = (message.caption or "").strip()

    # Limit file size to 20MB
    if file_size > 20 * 1024 * 1024:
        await message.reply("⚠️ حجم فایل ارسالی بیش از ۲۰ مگابایت است. لطفاً فایلی با حجم کمتر ارسال فرمایید.")
        return

    ext = file_name.split(".")[-1].lower() if "." in file_name else ""

    user = await db.get_or_create_user(message.from_user.id)
    active_model = user.get("selected_model", "gemini")
    caps = get_model_capabilities(active_model)

    if caps.get("is_image_studio"):
        from app.bot.handlers.image import handle_image_studio_doc
        await handle_image_studio_doc(message, state)
        return

    if caps.get("is_video_studio"):
        from app.bot.handlers.video import handle_video_doc
        await handle_video_doc(message, state)
        return

    user_lock = await ConcurrencyManager.get_user_lock(message.from_user.id)
    async with user_lock:
        async with ConcurrencyManager.acquire_slot():
            # 1. Image sent as Document (.png, .jpg, .webp)
            if ext in ["jpg", "jpeg", "png", "webp"] or mime_type.startswith("image/"):
                status_msg = await message.answer(f"👁️ <b>در حال دریافت و اسکن تصویر سند با {active_model}...</b>", parse_mode="HTML")
                await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                try:
                    file_io = io.BytesIO()
                    await message.bot.download(doc.file_id, destination=file_io)
                    raw_bytes = file_io.getvalue()
                    data_url, width, height = vision_service.process_and_encode_image(raw_bytes, mime_type="image/jpeg")

                    history = await db.get_chat_history(message.from_user.id)
                    messages = list(history)
                    base_prompt = caption or "لطفاً این تصویر سند را با دقت بررسی و محتوای آن را به طور کامل تحلیل و توضیح دهید."
                    prompt_text = (
                        f"{base_prompt}\n\n"
                        "نکات قالب‌بندی: پاسخ را با زبان فارسی روان و شکیل ارائه دهید. از جدول‌های لوله‌ای مارک‌داون (|) و فرمول‌های خام لاتک با علامت دلار ($...$) استفاده نکنید؛ اطلاعات را با بالت‌پوینت‌های زیبا (▫️، ▪️) و عبارات ساده یونیکد بنویسید."
                    )
                    messages.append({"role": "user", "content": prompt_text})

                    full_reply = ""
                    async for event in gateway.stream_chat(messages=messages, model_id=active_model, images=[data_url]):
                        if event.get("type") == "content":
                            full_reply += event.get("content", "")

                    if not full_reply.strip():
                        full_reply = "⚠️ پاسخی از مدل دریافت نشد."

                    formatted_reply = markdown_to_telegram_html(full_reply)
                    await safe_edit_or_reply(status_msg, formatted_reply, parse_mode="HTML")
                    await db.add_message(message.from_user.id, "user", f"[سند تصویری {file_name}]: {caption or 'تحلیل تصویر'}", model=active_model, has_images=True)
                    await db.add_message(message.from_user.id, "assistant", full_reply, model=active_model)
                except Exception as e:
                    await status_msg.edit_text(f"⚠️ خطا در تحلیل تصویر: {str(e)[:150]}")
                return

            # 2. PDF Document Analysis
            if ext == "pdf" or mime_type == "application/pdf":
                status_msg = await message.answer(f"📑 <b>در حال خواندن و استخراج صفحات سند PDF «{file_name}»...</b>", parse_mode="HTML")
                await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                try:
                    file_io = io.BytesIO()
                    await message.bot.download(doc.file_id, destination=file_io)
                    raw_bytes = file_io.getvalue()

                    pdf_data = DocumentService.extract_text_from_pdf(raw_bytes)

                    # Case A: Scanned PDF without text layer -> Use Gemini native PDF vision
                    if pdf_data["is_scanned"] or not pdf_data["text"].strip():
                        await status_msg.edit_text(f"🔍 <b>سند اسکن‌شده تصویری است. تحلیل مستقیم صفحات با هوش بینایی گوگل جمینای...</b>", parse_mode="HTML")
                        pdf_data_uri = DocumentService.to_pdf_data_uri(raw_bytes)
                        history = await db.get_chat_history(message.from_user.id)
                        messages = list(history)
                        base_prompt = caption or "لطفاً محتوای این فایل PDF اسکن‌شده را به دقت بررسی، بازخوانی و تحلیل فرمایید."
                        prompt_text = (
                            f"{base_prompt}\n\n"
                            "نکات قالب‌بندی: پاسخ را با زبان فارسی روان، عناوین شکیل، و بدون جدول‌های لوله‌ای مارک‌داون یا فرمول‌های خام لاتک با علامت دلار بنویسید."
                        )
                        messages.append({"role": "user", "content": prompt_text})

                        full_reply = ""
                        async for event in gateway.stream_chat(messages=messages, model_id="gemini", images=[pdf_data_uri]):
                            if event.get("type") == "content":
                                full_reply += event.get("content", "")

                        if not full_reply.strip():
                            full_reply = "⚠️ متاسفانه پردازش سند اسکن‌شده با خطا مواجه شد."

                        formatted_reply = markdown_to_telegram_html(full_reply)
                        await safe_edit_or_reply(status_msg, formatted_reply, parse_mode="HTML")
                        await db.add_message(message.from_user.id, "user", f"[سند اسکن‌شده {file_name}]: {caption or 'تحلیل سند اسکن‌شده'}", model="gemini")
                        await db.add_message(message.from_user.id, "assistant", full_reply, model="gemini")
                        return

                    # Case B: Standard PDF with text layer -> Universal multi-model processing
                    pages_count = pdf_data["total_pages"]
                    await status_msg.edit_text(f"🧠 <b>در حال تحلیل {pages_count} صفحه از سند با هوش مصنوعی ({active_model})...</b>", parse_mode="HTML")

                    structured_prompt = DocumentService.format_analysis_prompt(
                        file_name=file_name,
                        extracted_text=pdf_data["text"],
                        user_query=caption,
                        total_pages=pages_count
                    )

                    history = await db.get_chat_history(message.from_user.id)
                    messages = list(history)
                    messages.append({"role": "user", "content": structured_prompt})

                    full_reply = ""
                    async for event in gateway.stream_chat(messages=messages, model_id=active_model):
                        if event.get("type") == "content":
                            full_reply += event.get("content", "")

                    if not full_reply.strip():
                        full_reply = "⚠️ پاسخی از هوش مصنوعی دریافت نشد."

                    formatted_reply = markdown_to_telegram_html(full_reply)
                    await safe_edit_or_reply(status_msg, formatted_reply, parse_mode="HTML")
                    await db.add_message(message.from_user.id, "user", f"[سند PDF {file_name} ({pages_count} ص)]: {caption or 'تحلیل و خلاصه'}", model=active_model)
                    await db.add_message(message.from_user.id, "assistant", full_reply, model=active_model)
                except Exception as e:
                    print(f"[DocumentHandler] PDF error: {e}")
                    await status_msg.edit_text(f"⚠️ خطا در پردازش فایل PDF: {str(e)[:150]}")
                return

            # 3. Plain Text / Code / CSV / JSON files
            TEXT_EXTS = ["txt", "csv", "json", "py", "md", "js", "html", "css", "log", "xml", "yaml", "yml", "sql", "sh", "bat", "c", "cpp", "java", "rs"]
            if ext in TEXT_EXTS or mime_type.startswith("text/"):
                status_msg = await message.answer(f"📑 <b>در حال خواندن فایل متنی «{file_name}»...</b>", parse_mode="HTML")
                await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                try:
                    file_io = io.BytesIO()
                    await message.bot.download(doc.file_id, destination=file_io)
                    raw_bytes = file_io.getvalue()

                    doc_res = DocumentService.extract_text_from_plain(raw_bytes)
                    if not doc_res["success"] or not doc_res["text"].strip():
                        await status_msg.edit_text("⚠️ محتوای متنی قابل تشخیصی در فایل یافت نشد.")
                        return

                    await status_msg.edit_text(f"🧠 <b>در حال پردازش و تحلیل محتوای کد/متن با {active_model}...</b>", parse_mode="HTML")
                    prompt_text = DocumentService.format_analysis_prompt(
                        file_name=file_name,
                        extracted_text=doc_res["text"],
                        user_query=caption,
                        total_pages=1
                    )

                    history = await db.get_chat_history(message.from_user.id)
                    messages = list(history)
                    messages.append({"role": "user", "content": prompt_text})

                    full_reply = ""
                    async for event in gateway.stream_chat(messages=messages, model_id=active_model):
                        if event.get("type") == "content":
                            full_reply += event.get("content", "")

                    if not full_reply.strip():
                        full_reply = "⚠️ پاسخی از هوش مصنوعی دریافت نشد."

                    formatted_reply = markdown_to_telegram_html(full_reply)
                    await safe_edit_or_reply(status_msg, formatted_reply, parse_mode="HTML")
                    await db.add_message(message.from_user.id, "user", f"[فایل {file_name}]: {caption or 'تحلیل محتوا'}", model=active_model)
                    await db.add_message(message.from_user.id, "assistant", full_reply, model=active_model)
                except Exception as e:
                    await status_msg.edit_text(f"⚠️ خطا در خواندن فایل: {str(e)[:150]}")
                return

                # 4. Unsupported file formats
            await message.reply(
                f"⚠️ فرمت فایل ارسالی (`.{ext}`) برای تحلیل مستقیم پشتیبانی نمی‌شود.\n\n"
                "📌 **فرمت‌های قابل تحلیل توسط ربات:**\n"
                "• **اسناد PDF:** کتاب‌ها، مقالات، جزوه‌ها، پایان‌نامه‌ها (`.pdf`)\n"
                "• **فایل‌های متنی و کد:** پایتون، جاوااسکریپت، مارک‌داون، لاگ، داده‌های متنی (`.txt`, `.csv`, `.json`, `.py`, `.md`)\n"
                "• **تصاویر و اسناد اسکن‌شده:** (`.png`, `.jpg`, `.jpeg`, `.webp`)"
            )


@router.message(F.video)
async def handle_video_message(message: Message):
    """Handles videos sent directly to the bot to detect aspect ratio and configure subsequent generations."""
    video = message.video
    user_id = message.from_user.id
    detected_ratio = detect_aspect_ratio(video.width, video.height)
    await db.update_user_video_settings(user_id, ratio=detected_ratio)
    await db.update_user_image_settings(user_id, ratio=detected_ratio)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 استودیو تولید ویدیو نانو", callback_data="video_menu"),
            InlineKeyboardButton(text="🍌 استودیو ادیت عکس نانو بنانا", callback_data="menu:gpt_image"),
        ],
        [
            InlineKeyboardButton(text="🔙 منوی اصلی", callback_data="cb_main_menu")
        ]
    ])
    await message.reply(
        f"🎬 **ویدیوی شما دریافت شد!**\n\n"
        f"📐 **نسبت ابعاد شناسایی شده:** `{detected_ratio}` (وضوح: {video.width}x{video.height})\n"
        f"✅ تنظیمات ربات به صورت خودکار روی نسبت `{detected_ratio}` ذخیره شد تا تمام خروجی‌های بعدی عکس و ویدیو با همین ابعاد تولید شوند.\n\n"
        f"💡 تا زمانی که خودتان نسبت را در تنظیمات تغییر ندهید، نسبت ابعاد روی `{detected_ratio}` فعال خواهد ماند.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

