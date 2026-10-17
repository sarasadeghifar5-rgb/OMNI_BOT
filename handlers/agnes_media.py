"""
Multimedia Studio handlers:
- Text-to-Image Generation (Powered by GPT Image)
- Single & Multi-Image Editing (Powered by GPT Image)
- Text-to-Video Generation (Powered by VEO 3)
- Photo Animation / Image-to-Video (Powered by VEO 3)
Clean captions, bold headers, concise text, no parentheses in loading.
"""
import io
import asyncio
import logging
from typing import List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
from api_services.agnes import agnes_client
from database import db
from keyboards import get_main_keyboard, get_cancel_keyboard, get_multi_photo_keyboard, get_loading_keyboard
from utils.progress_helper import run_charging_progress, format_charging_bar

router = Router()
logger = logging.getLogger(__name__)

class MediaStates(StatesGroup):
    waiting_for_image_prompt = State()
    waiting_for_video_prompt = State()
    waiting_for_edit_photo = State()
    waiting_for_edit_instruction = State()
    waiting_for_animate_photo = State()

MEDIA_GROUP_CACHE: dict = {}

# ================= 1. TEXT TO IMAGE =================
@router.message(F.text.in_(["ساخت عکس", "تولید عکس", "🎨 ساخت عکس", "🎨 تولید عکس"]))
async def ask_image_prompt(message: Message, state: FSMContext):
    await state.set_state(MediaStates.waiting_for_image_prompt)
    await message.answer(
        "🎨 **استودیو تولید عکس:**\n\n"
        "توصیف تصویر دلخواه خود را ارسال کنید:\n\n"
        "💡 *مثال:* `یک قصر کریستالی درخشان در کهکشان، کیفیت 4K`",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(Command("image"))
async def cmd_image(message: Message, state: FSMContext):
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        prompt = parts[1].strip()
        await process_image_generation(message, prompt)
    else:
        await ask_image_prompt(message, state)

@router.message(MediaStates.waiting_for_image_prompt, F.text)
async def handle_image_prompt(message: Message, state: FSMContext):
    if message.text in ("انصراف و بازگشت", "❌ انصراف و بازگشت"):
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    prompt = message.text.strip()
    await state.clear()
    await process_image_generation(message, prompt)

@router.message(MediaStates.waiting_for_image_prompt, F.document)
async def handle_image_prompt_doc(message: Message, state: FSMContext):
    if message.document and message.document.file_name.endswith(('.txt', '.text')):
        file_io = io.BytesIO()
        await message.bot.download(message.document, destination=file_io)
        prompt = file_io.getvalue().decode('utf-8', errors='ignore').strip()
        await state.clear()
        await process_image_generation(message, prompt)
    else:
        await message.answer("لطفاً متن پرامپت یا فایل متنی ارسال کنید.")

async def process_image_generation(message: Message, prompt: str):
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
    title = "🎨 **در حال تولید تصویر...**"
    status_msg = await message.answer(
        f"{title}\n\n{format_charging_bar(10)}",
        parse_mode="Markdown",
        reply_markup=get_loading_keyboard("⚡️ شروع تولید تصویر...")
    )

    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(
        run_charging_progress(status_msg, title, stop_event, start_percent=12, target_percent=95, step_delay=2.0)
    )

    try:
        success, result = await agnes_client.generate_image(prompt=prompt)
    finally:
        stop_event.set()
        await progress_task

    await status_msg.delete()

    if success:
        await db.log_generation(message.from_user.id, "image", prompt, result)
        preview_prompt = prompt[:250] + ("..." if len(prompt) > 250 else "")
        caption = (
            f"🎨 **تصویر شما آماده شد!**\n\n"
            f"📝 **پرامپت:** `{preview_prompt}`\n"
            f"⚡ **موتور:** GPT Image"
        )
        try:
            await message.answer_photo(
                photo=result,
                caption=caption,
                reply_markup=get_main_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
        except Exception:
            await message.answer(
                f"{caption}\n\n🔗 [دانلود فایل تصویر]({result})",
                reply_markup=get_main_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
    else:
        await message.answer(
            f"❌ {result}",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

# ================= 2. BATCH & MULTI-IMAGE EDITING =================
@router.message(F.text.in_(["ادیت عکس", "ادیت و ترکیب عکس‌ها", "✏️ ادیت عکس", "✏️ ادیت و ترکیب عکس‌ها"]))
@router.message(Command("edit"))
async def ask_edit_photos(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MediaStates.waiting_for_edit_photo)
    await state.update_data(images_list=[])

    await message.answer(
        "✏️ **استودیو ادیت و ترکیب عکس:**\n\n"
        "عکس‌های خود را ارسال کنید:\n"
        "• می‌توانید یک یا چند عکس بفرستید.\n"
        "• پس از ارسال، دکمه تایید را لمس فرمایید.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(MediaStates.waiting_for_edit_photo, F.photo)
async def handle_edit_photos_received(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_io = io.BytesIO()
    await message.bot.download(photo, destination=file_io)
    image_bytes = file_io.getvalue()

    data = await state.get_data()
    images_list = data.get("images_list", [])
    images_list.append(image_bytes)

    caption = message.caption
    if caption and len(caption.strip()) > 1:
        await state.update_data(caption=caption.strip())

    await state.update_data(images_list=images_list)
    count = len(images_list)

    mg_id = message.media_group_id
    if mg_id:
        if mg_id not in MEDIA_GROUP_CACHE:
            MEDIA_GROUP_CACHE[mg_id] = 1
            async def notify_album():
                await asyncio.sleep(1.2)
                cur_data = await state.get_data()
                cur_count = len(cur_data.get("images_list", []))
                await message.answer(
                    f"📸 **تعداد {cur_count} عکس دریافت شد!**\n\n"
                    f"برای نوشتن پرامپت، دکمه تایید زیر را بزنید:",
                    reply_markup=get_multi_photo_keyboard(cur_count),
                    parse_mode="Markdown"
                )
                MEDIA_GROUP_CACHE.pop(mg_id, None)

            asyncio.create_task(notify_album())
        else:
            MEDIA_GROUP_CACHE[mg_id] += 1
    else:
        await message.answer(
            f"📸 **عکس شماره {count} ذخیره شد!** مجموعاً {count} عکس\n\n"
            f"دکمه تایید زیر را برای شروع ادیت لمس کنید:",
            reply_markup=get_multi_photo_keyboard(count),
            parse_mode="Markdown"
        )

@router.message(MediaStates.waiting_for_edit_photo, F.text.startswith("تایید عکس‌ها") | F.text.startswith("✅ تایید عکس‌ها"))
async def confirm_photos_and_ask_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    images_list = data.get("images_list", [])
    count = len(images_list)

    if count == 0:
        await message.answer("هنوز عکسی ارسال نشده است.")
        return

    saved_caption = data.get("caption")
    await state.set_state(MediaStates.waiting_for_edit_instruction)

    if saved_caption:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 اعمال ادیت با همین متن", callback_data="edit_use_caption")],
                [InlineKeyboardButton(text="✍️ نوشتن پرامپت جدید", callback_data="edit_enter_long_prompt")]
            ]
        )
        await message.answer(
            f"📸 **تعداد {count} عکس آماده است.**\n\n"
            f"متن ارسالی: _{saved_caption[:100]}..._\n\n"
            f"آیا با همین متن اجرا شود؟",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"📸 **تعداد {count} عکس آماده است.**\n\n"
            f"✍️ **دستور ادیت یا ترکیب را بنویسید:**\n"
            f"💡 *مثال:* `تغییر لباس به کت و شلوار رسمی و پس‌زمینه دفتر مدرن`",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )

@router.callback_query(F.data == "edit_use_caption")
async def cb_edit_use_caption(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    images_list = data.get("images_list", [])
    caption = data.get("caption", "")
    await state.clear()
    await callback.message.delete()

    if images_list and caption:
        await process_multi_image_edit(callback.message, images_list, caption)
    else:
        await callback.message.answer("اطلاعات منقضی شد. مجدداً تلاش کنید.", reply_markup=get_main_keyboard(callback.from_user.id))

@router.callback_query(F.data == "edit_enter_long_prompt")
async def cb_edit_enter_long_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MediaStates.waiting_for_edit_instruction)
    await callback.message.edit_text(
        "✍️ **پرامپت ادیت را به صورت متن ارسال کنید:**",
        parse_mode="Markdown"
    )

@router.message(MediaStates.waiting_for_edit_instruction, F.text)
async def handle_edit_instruction_received(message: Message, state: FSMContext):
    if message.text in ("انصراف و بازگشت", "❌ انصراف و بازگشت"):
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    prompt = message.text.strip()
    data = await state.get_data()
    images_list = data.get("images_list", [])
    await state.clear()

    if not images_list:
        await message.answer("تصویری یافت نشد. لطفاً از دکمه «✏️ ادیت عکس» شروع کنید.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    await process_multi_image_edit(message, images_list, prompt)

@router.message(MediaStates.waiting_for_edit_instruction, F.document)
async def handle_edit_instruction_doc(message: Message, state: FSMContext):
    if message.document and message.document.file_name.endswith(('.txt', '.text')):
        file_io = io.BytesIO()
        await message.bot.download(message.document, destination=file_io)
        prompt = file_io.getvalue().decode('utf-8', errors='ignore').strip()
        data = await state.get_data()
        images_list = data.get("images_list", [])
        await state.clear()
        if images_list:
            await process_multi_image_edit(message, images_list, prompt)
    else:
        await message.answer("لطفاً دستور ادیت را ارسال فرمایید.")

async def process_image_edit(message: Message, image_bytes: bytes, prompt: str):
    await process_multi_image_edit(message, [image_bytes], prompt)

async def process_multi_image_edit(message: Message, images_list: List[bytes], prompt: str):
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
    count = len(images_list)
    title = f"✏️ **در حال ادیت و ترکیب {count} عکس...**"
    status_msg = await message.answer(
        f"{title}\n\n{format_charging_bar(10)}",
        parse_mode="Markdown",
        reply_markup=get_loading_keyboard(f"🎨 در حال ادیت و ترکیب {count} عکس...")
    )

    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(
        run_charging_progress(status_msg, title, stop_event, start_percent=10, target_percent=95, step_delay=2.2)
    )

    try:
        success, result = await agnes_client.edit_multiple_images(images_bytes_list=images_list, prompt=prompt)
    finally:
        stop_event.set()
        await progress_task

    await status_msg.delete()

    if success:
        await db.log_generation(message.from_user.id, "image_edit", prompt, result)
        preview_prompt = prompt[:250] + ("..." if len(prompt) > 250 else "")
        caption = (
            f"✨ **تصویر ادیت‌شده شما آماده شد!**\n\n"
            f"📝 **تغییرات:** `{preview_prompt}`\n"
            f"⚡ **موتور:** GPT Image"
        )
        try:
            await message.answer_photo(
                photo=result,
                caption=caption,
                reply_markup=get_main_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
        except Exception:
            await message.answer(
                f"{caption}\n\n🔗 [دانلود مستقیم تصویر]({result})",
                reply_markup=get_main_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
    else:
        await message.answer(
            f"❌ {result}",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

# ================= 3. PHOTO ANIMATION (IMAGE-TO-VIDEO) =================
@router.message(F.text.in_(["متحرک‌سازی عکس", "🎞 متحرک‌سازی عکس"]))
@router.message(Command("animate"))
async def ask_animate_photo(message: Message, state: FSMContext):
    await state.set_state(MediaStates.waiting_for_animate_photo)
    await message.answer(
        "🎞 **استودیو متحرک‌سازی عکس:**\n\n"
        "عکس خود را برای تبدیل به ویدیو ارسال کنید:\n\n"
        "💡 *نکته:* می‌توانید نوع حرکت را در متن یا همراه عکس مشخص فرمایید.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(MediaStates.waiting_for_animate_photo, F.photo)
async def handle_animate_photo_received(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_io = io.BytesIO()
    await message.bot.download(photo, destination=file_io)
    image_bytes = file_io.getvalue()
    prompt = message.caption or "Smooth cinematic motion, natural lifelike animation"

    await state.clear()
    await process_image_animation(message, image_bytes, prompt)

async def process_image_animation(message: Message, image_bytes: bytes, prompt: str):
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VIDEO)
    title = "🎞 **در حال متحرک‌سازی فریم‌های عکس...**"
    status_msg = await message.answer(
        f"{title}\n\n{format_charging_bar(8)}",
        parse_mode="Markdown",
        reply_markup=get_loading_keyboard("🎞 در حال متحرک‌سازی عکس...")
    )

    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(
        run_charging_progress(status_msg, title, stop_event, start_percent=8, target_percent=94, step_delay=2.5)
    )

    try:
        success, result = await agnes_client.animate_image(image_bytes=image_bytes, prompt=prompt)
    finally:
        stop_event.set()
        await progress_task

    await status_msg.delete()

    if success:
        await db.log_generation(message.from_user.id, "animate", prompt, result)
        preview_prompt = prompt[:250] + ("..." if len(prompt) > 250 else "")
        caption = (
            f"🎬 **ویدیوی شما آماده شد!**\n\n"
            f"📝 **حرکت:** `{preview_prompt}`\n"
            f"⚡ **موتور:** VEO 3"
        )
        try:
            await message.answer_video(
                video=result,
                caption=caption,
                reply_markup=get_main_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
        except Exception:
            await message.answer(
                f"{caption}\n\n🔗 [دانلود مستقیم ویدیو]({result})",
                reply_markup=get_main_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
    else:
        await message.answer(
            result,
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )

# ================= 4. TEXT TO VIDEO =================
@router.message(F.text.in_(["تولید ویدیو", "🎬 تولید ویدیو"]))
async def ask_video_prompt(message: Message, state: FSMContext):
    await state.set_state(MediaStates.waiting_for_video_prompt)
    await message.answer(
        "🎬 **استودیو تولید ویدیو:**\n\n"
        "سناریوی ویدیوی مورد نظر خود را بنویسید:\n\n"
        "💡 *مثال:* `پرواز یک عقاب بر فراز کوهستان برفی در غروب آفتاب`",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@router.message(Command("video"))
async def cmd_video(message: Message, state: FSMContext):
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        prompt = parts[1].strip()
        await process_video_generation(message, prompt)
    else:
        await ask_video_prompt(message, state)

@router.message(MediaStates.waiting_for_video_prompt, F.text)
async def handle_video_prompt(message: Message, state: FSMContext):
    if message.text in ("انصراف و بازگشت", "❌ انصراف و بازگشت"):
        await state.clear()
        await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    prompt = message.text.strip()
    await state.clear()
    await process_video_generation(message, prompt)

async def process_video_generation(message: Message, prompt: str):
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VIDEO)
    title = "🎬 **در حال تولید و رندر ویدیو...**"
    status_msg = await message.answer(
        f"{title}\n\n{format_charging_bar(8)}",
        parse_mode="Markdown",
        reply_markup=get_loading_keyboard("🎬 در حال ساخت ویدیو هوشمند...")
    )

    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(
        run_charging_progress(status_msg, title, stop_event, start_percent=8, target_percent=94, step_delay=2.5)
    )

    try:
        success, result = await agnes_client.generate_video(prompt=prompt)
    finally:
        stop_event.set()
        await progress_task

    await status_msg.delete()

    if success:
        await db.log_generation(message.from_user.id, "video", prompt, result)
        preview_prompt = prompt[:250] + ("..." if len(prompt) > 250 else "")
        caption = (
            f"🎬 **ویدیوی شما آماده شد!**\n\n"
            f"📝 **سناریو:** `{preview_prompt}`\n"
            f"⚡ **موتور:** VEO 3"
        )
        try:
            await message.answer_video(
                video=result,
                caption=caption,
                reply_markup=get_main_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
        except Exception:
            await message.answer(
                f"{caption}\n\n🔗 [دانلود مستقیم ویدیو]({result})",
                reply_markup=get_main_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
    else:
        await message.answer(
            result,
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )
