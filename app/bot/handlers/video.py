import io
import time
import asyncio
import logging
from typing import Optional, Dict, Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction

from app.services.agnes_video import AgnesVideoService
from app.services.prompt_enhancer import PromptEnhancerService
from app.bot.database import BotDatabase
from app.bot.utils import safe_reply, detect_aspect_ratio

logger = logging.getLogger("VideoHandler")
router = Router(name="video_router")
video_service = AgnesVideoService()
db = BotDatabase.get_instance()


class VideoStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_image = State()


VIDEO_STUDIO_INTRO = """🎬 **استودیوی تولید ویدیو و انیمیشن نانو (Nano Video Studio)**

✨ **حالت استودیو ویدیو فعال شد (اختصاصی تولید ویدیو و انیمیشن):**
• 🎥 **تولید ویدیو از متن (Text-to-Video):** هر توصیفی بفرستید، مستقیماً ویدیوی هوشمند آن با حرکات طبیعی و صدای همگام تولید می‌شود.
• 🖼️ **متحرک‌سازی تصویر (Image-to-Video):** هر عکسی بفرستید، به ویدیو و انیمیشن پویا تبدیل می‌شود.
• 📐 **پشتیبانی از ابعاد مختلف:** افقی (16:9)، استوری و ریلز (9:16)، مربعی (1:1)

⚠️ **توجه:** در این بخش هیچ مدل متنی یا LLM چت نمی‌کند و همه پیام‌ها برای ساخت ویدیو پردازش می‌شوند.
💬 برای **گفتگو و چت متنی با هوش مصنوعی** یا **تحلیل و آنالیز فایل و عکس**، دکمه **«💬 گفتگوی جدید»** را بزنید.

👇 یکی از گزینه‌های زیر را انتخاب کنید یا پرامپت خود را بنویسید:"""


def get_video_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 ساخت ویدیو از متن", callback_data="video_action_prompt"),
                InlineKeyboardButton(text="🖼️ متحرک‌سازی عکس", callback_data="video_action_image"),
            ],
            [
                InlineKeyboardButton(text="📐 نسبت ابعاد (Ratio)", callback_data="video_settings_ratio"),
                InlineKeyboardButton(text="⏱️ مدت زمان (Duration)", callback_data="video_settings_duration"),
            ],
            [
                InlineKeyboardButton(text="💬 گفتگوی جدید (ورود به چت هوش مصنوعی)", callback_data="action:clear_chat"),
            ],
            [
                InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="cb_main_menu")
            ]
        ]
    )


def get_video_ratio_keyboard(current_ratio: str = "16:9") -> InlineKeyboardMarkup:
    ratios = [
        ("🖥️ 16:9 عریض (یوتیوب)", "16:9"),
        ("📱 9:16 استوری (ریلز و تیک‌تاک)", "9:16"),
        ("🔲 1:1 مربعی (اینستاگرام)", "1:1"),
        ("📺 4:3 استاندارد", "4:3"),
        ("📱 3:4 عمودی", "3:4"),
        ("🎬 21:9 سینمایی عریض", "21:9"),
    ]
    buttons = []
    for label, r in ratios:
        prefix = "✅ " if r == current_ratio else ""
        buttons.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"video_set_ratio:{r}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به استودیو ویدیو", callback_data="video_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_video_duration_keyboard(current_sec: str = "5") -> InlineKeyboardMarkup:
    durations = [
        ("⚡ ۵ ثانیه (سریع)", "5"),
        ("⏱️ ۸ ثانیه (استاندارد)", "8"),
        ("⏳ ۱۰ ثانیه (طولانی)", "10"),
    ]
    buttons = []
    for label, sec in durations:
        prefix = "✅ " if sec == current_sec else ""
        buttons.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"video_set_duration:{sec}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به استودیو ویدیو", callback_data="video_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_user_video_settings(state: Optional[FSMContext] = None, user_id: Optional[int] = None) -> tuple[str, str, str]:
    """Retrieves ratio, seconds, and size from FSM state data, falling back to SQLite database."""
    ratio = None
    seconds = None
    size = None
    if state:
        try:
            data = await state.get_data()
            ratio = data.get("video_ratio")
            seconds = data.get("video_seconds")
            size = data.get("video_size")
        except Exception:
            pass

    if user_id and (not ratio or not seconds or not size):
        try:
            db_ratio, db_sec, db_size = await db.get_user_video_settings(user_id)
            if not ratio:
                ratio = db_ratio
            if not seconds:
                seconds = db_sec
            if not size:
                size = db_size
            if state:
                await state.update_data(video_ratio=ratio, video_seconds=seconds, video_size=size)
        except Exception:
            pass

    return ratio or "16:9", seconds or "5", size or "720P"


async def update_user_video_settings(
    state: Optional[FSMContext] = None,
    user_id: Optional[int] = None,
    ratio: Optional[str] = None,
    seconds: Optional[str] = None,
    size: Optional[str] = None
):
    """Updates video settings in both FSM state and SQLite database."""
    if state:
        data = {}
        if ratio:
            data["video_ratio"] = ratio
        if seconds:
            data["video_seconds"] = seconds
        if size:
            data["video_size"] = size
        if data:
            try:
                await state.update_data(**data)
            except Exception:
                pass
    if user_id:
        try:
            await db.update_user_video_settings(user_id, ratio=ratio, seconds=seconds, size=size)
        except Exception:
            pass


@router.message(Command("video", "clip", "animation"))
@router.message(F.text.in_({
    "🎬 استودیو تولید ویدیو", "استودیو تولید ویدیو 🎬", "استودیو تولید ویدیو",
    "🎬 استودیو ویدیو نانو", "استودیو ویدیو نانو", "استودیو ویدیو",
    "🎬 ساخت ویدیو", "ساخت ویدیو", "تولید ویدیو", "ویدیو", "ویدئو"
}))
async def cmd_video_studio(message: Message, state: FSMContext = None):
    """Opens Nano Video Studio main panel."""
    user_id = message.from_user.id
    await db.update_user_model(user_id, "agnes-video-2.5")
    if state:
        await state.clear()
    await message.answer(
        VIDEO_STUDIO_INTRO,
        reply_markup=get_video_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "video_menu")
async def cb_video_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    await db.update_user_model(user_id, "agnes-video-2.5")
    if state:
        await state.clear()
    if callback.message:
        try:
            await callback.message.edit_text(
                VIDEO_STUDIO_INTRO,
                reply_markup=get_video_menu_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            await callback.message.answer(
                VIDEO_STUDIO_INTRO,
                reply_markup=get_video_menu_keyboard(),
                parse_mode="Markdown"
            )


@router.callback_query(F.data == "video_action_prompt")
async def cb_video_action_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(VideoStates.waiting_for_prompt)
    ratio, seconds, size = await get_user_video_settings(state)
    prompt_help = (
        "🎬 **تولید ویدیو از متن (Text-to-Video)**\n\n"
        f"⚙️ تنظیمات فعلی: نسبت `{ratio}` | مدت زمان `{seconds} ثانیه` | کیفیت `{size}`\n\n"
        "لطفاً توصیف و صحنه‌ای که می‌خواهید ساخته شود را به فارسی یا انگلیسی بنویسید:\n"
        "*(مثال: پرواز یک شاهین بر فراز کوهستان‌های برفی با نور غروب آفتاب)*"
    )
    if callback.message:
        await callback.message.answer(prompt_help, parse_mode="Markdown")


@router.callback_query(F.data == "video_action_image")
async def cb_video_action_image(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(VideoStates.waiting_for_image)
    await callback.message.answer(
        "🖼️ **متحرک‌سازی تصویر (Image-to-Video)**\n\n"
        "لطفاً تصویری که قصد متحرک‌سازی آن را دارید ارسال فرمایید.\n"
        "می‌توانید در کپشن تصویر، نحوه حرکت یا جزئیات مورد نظرتان را هم بنویسید.",
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "video_settings_ratio")
async def cb_video_settings_ratio(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    ratio, _, _ = await get_user_video_settings(state, user_id)
    await callback.message.edit_text(
        "📐 **انتخاب نسبت ابعاد ویدیو (Aspect Ratio):**\n\n"
        "یکی از ابعاد استاندارد زیر را انتخاب کنید:\n"
        "💡 همچنین اگر تصویر یا ویدیویی با ابعاد دلخواه (مثل 16:9 یا 9:16) بفرستید، نسبت آن خودکار تنظیم شده و تا تغییر دستی روی همان باقی می‌ماند.",
        reply_markup=get_video_ratio_keyboard(ratio),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("video_set_ratio:"))
async def cb_video_set_ratio(callback: CallbackQuery, state: FSMContext):
    selected_ratio = callback.data[len("video_set_ratio:"):]
    user_id = callback.from_user.id
    await update_user_video_settings(state, user_id, ratio=selected_ratio)
    # Also synchronize with image studio settings
    await db.update_user_image_settings(user_id, ratio=selected_ratio)
    await callback.answer(f"نسبت ویدیو روی {selected_ratio} تنظیم شد ✅")
    await callback.message.edit_text(
        f"✅ نسبت ابعاد ویدیو با موفقیت روی `{selected_ratio}` تنظیم گردید.\n\nبه استودیو بازگردید یا دستور ساخت ویدیو را صادر کنید:",
        reply_markup=get_video_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "video_settings_duration")
async def cb_video_settings_duration(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    _, seconds, _ = await get_user_video_settings(state, user_id)
    await callback.message.edit_text(
        "⏱️ **مدت زمان ویدیو (Duration):**\n\nطول ویدیوی تولیدی را انتخاب کنید:",
        reply_markup=get_video_duration_keyboard(seconds),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("video_set_duration:"))
async def cb_video_set_duration(callback: CallbackQuery, state: FSMContext):
    selected_sec = callback.data[len("video_set_duration:"):]
    user_id = callback.from_user.id
    await update_user_video_settings(state, user_id, seconds=selected_sec)
    await callback.answer(f"مدت زمان روی {selected_sec} ثانیه تنظیم شد ✅")
    await callback.message.edit_text(
        f"✅ مدت زمان ویدیو روی `{selected_sec} ثانیه` تنظیم گردید.\n\nبه استودیو بازگردید یا دستور ساخت ویدیو را صادر کنید:",
        reply_markup=get_video_menu_keyboard(),
        parse_mode="Markdown"
    )


SYSTEM_BUTTON_TEXTS = {
    "💬 گفتگوی جدید", "گفتگوی جدید", "💬 گفتگو جدید", "گفتگو جدید", "🗑️ گفتگو جدید", "🗨️ گفتگو جدید", "🗑️ چت جدید", "چت جدید",
    "🤖 انتخاب مدل", "انتخاب مدل 🤖", "انتخاب مدل",
    "🍌 ادیت عکس نانو بنانا", "ادیت عکس نانو بنانا 🍌", "ادیت عکس نانو بنانا", "🎨 تولید و ادیت عکس جی پی تی", "تولید و ادیت عکس جی پی تی", "🎨 استودیو عکس 🍌", "استودیو عکس", "تولید عکس", "ادیت عکس",
    "🎬 استودیو تولید ویدیو", "استودیو تولید ویدیو 🎬", "استودیو تولید ویدیو", "🎬 استودیو ویدیو نانو", "استودیو ویدیو نانو", "استودیو ویدیو", "🎬 ساخت ویدیو", "ساخت ویدیو", "تولید ویدیو", "ویدیو", "ویدئو",
    "👤 حساب کاربری", "حساب کاربری 👤", "حساب کاربری", "پروفایل",
    "🛒 خرید سرویس", "خرید سرویس 🛒", "خرید سرویس",
    "🎁 سرویس هدیه", "سرویس هدیه 🎁", "هدیه روزانه", "سرویس هدیه",
    "🎤 تبدیل متن به گفتار", "تبدیل متن به گفتار 🎤", "تبدیل متن به گفتار",
    "🔗 لینک دعوت", "لینک دعوت 🔗", "زیرمجموعه‌گیری",
    "🌐 تغییر منطقه", "تغییر منطقه 🌐", "سرور و ریجن",
    "👑 پنل مدیریت ادمین", "پنل مدیریت ادمین 👑",
    "⚙️ منو", "منو",
}

async def is_video_studio_active(user_id: int) -> bool:
    user = await db.get_or_create_user(user_id)
    from app.config import get_model_capabilities
    caps = get_model_capabilities(user.get("selected_model", "gemini"))
    return bool(caps.get("is_video_studio"))

async def video_studio_text_filter(message: Message, state: FSMContext) -> bool:
    if not message.text or message.text.startswith("/") or not message.from_user:
        return False
    if message.text.strip() in SYSTEM_BUTTON_TEXTS:
        return False
    return await is_video_studio_active(message.from_user.id)


@router.message(VideoStates.waiting_for_prompt, F.text & ~F.text.startswith("/"))
@router.message(video_studio_text_filter)
async def handle_video_prompt(message: Message, state: FSMContext):
    """Processes user text prompt for Text-to-Video generation directly without any LLM."""
    prompt = message.text.strip()
    if prompt.startswith("/"):
        await state.clear()
        return
    await state.clear()
    user_id = message.from_user.id
    ratio, seconds, size = await get_user_video_settings(state, user_id)
    await execute_video_generation(message, prompt=prompt, mode="text", ratio=ratio, seconds=seconds, size=size)


def format_video_progress(pct: int, elapsed_sec: int) -> str:
    """Renders the video generation progress matching user specification."""
    filled = min(10, max(1, int(round(pct / 10))))
    bar = "▰" * filled + "▱" * (10 - filled)
    if elapsed_sec < 60:
        elapsed_str = f"{elapsed_sec}s"
    else:
        elapsed_str = f"{elapsed_sec // 60}m {elapsed_sec % 60}s"
    return (
        "🎬 <b>در حال پردازش ویدیو</b>\n\n"
        f"{bar} {max(5, pct)}%\n\n"
        f"⏱ {elapsed_str} / ~2m\n\n"
        "✨ لطفاً کمی صبر کنید…"
    )


def format_video_delivering_status() -> str:
    """Renders immediate delivery status when video generation finishes."""
    return (
        "🎬 <b>ویدیو با موفقیت ساخته شد!</b>\n\n"
        "▰▰▰▰▰▰▰▰▰▰ 100%\n\n"
        "🚀 <b>در حال ارسال آنی ویدیو به تلگرام...</b>"
    )


async def video_studio_photo_filter(message: Message) -> bool:
    if not message.photo or not message.from_user:
        return False
    return await is_video_studio_active(message.from_user.id)


@router.message(VideoStates.waiting_for_image, F.photo)
@router.message(video_studio_photo_filter)
async def handle_video_photo(message: Message, state: FSMContext):
    """Processes image for Image-to-Video animation in Video Studio without any LLM vision."""
    await state.clear()
    user_id = message.from_user.id

    photo = message.photo[-1]
    # Auto-detect aspect ratio from input image
    detected_ratio = detect_aspect_ratio(photo.width, photo.height)
    await update_user_video_settings(state, user_id, ratio=detected_ratio)
    await db.update_user_image_settings(user_id, ratio=detected_ratio)

    prompt = (message.caption or "").strip() or "Cinematic motion, lively and dynamic animation, high quality"
    ratio, seconds, size = await get_user_video_settings(state, user_id)

    status_msg = await message.answer(format_video_progress(5, 0), parse_mode="HTML")
    try:
        file_obj = await message.bot.get_file(photo.file_id)
        file_bytes = await message.bot.download_file(file_obj.file_path)
        raw_bytes = file_bytes.read()

        from app.services.agnes_image import AgnesImageService
        data_uri = AgnesImageService.optimize_image_to_data_uri(raw_bytes, max_dimension=1024)

        await execute_video_generation(
            message,
            prompt=prompt,
            mode="keyframe",
            ratio=detected_ratio,
            seconds=seconds,
            size=size,
            first_frame=data_uri,
            status_msg=status_msg
        )
    except Exception as e:
        logger.error(f"Error handling video photo: {e}")
        await status_msg.edit_text(f"❌ خطا در پردازش تصویر: {e}")


async def video_studio_doc_filter(message: Message) -> bool:
    if not message.document or not message.from_user:
        return False
    return await is_video_studio_active(message.from_user.id)


@router.message(video_studio_doc_filter)
async def handle_video_doc(message: Message, state: FSMContext):
    """Handles documents sent in Video Studio mode."""
    doc = message.document
    file_name = doc.file_name or ""
    mime_type = (doc.mime_type or "").lower()
    ext = file_name.split(".")[-1].lower() if "." in file_name else ""
    user_id = message.from_user.id

    if ext in ["jpg", "jpeg", "png", "webp"] or mime_type.startswith("image/"):
        file_obj = await message.bot.get_file(doc.file_id)
        file_bytes = await message.bot.download_file(file_obj.file_path)
        raw_bytes = file_bytes.read()
        ratio, seconds, size = await get_user_video_settings(state, user_id)
        prompt = (message.caption or "").strip() or "Cinematic motion, lively and dynamic animation, high quality"
        status_msg = await message.answer(format_video_progress(5, 0), parse_mode="HTML")
        from app.services.agnes_image import AgnesImageService
        data_uri = AgnesImageService.optimize_image_to_data_uri(raw_bytes, max_dimension=1024)
        await execute_video_generation(
            message,
            prompt=prompt,
            mode="keyframe",
            ratio=ratio,
            seconds=seconds,
            size=size,
            first_frame=data_uri,
            status_msg=status_msg
        )
        return

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 گفتگوی جدید (ورود به چت هوش مصنوعی)", callback_data="action:clear_chat")]
    ])
    await message.reply(
        "⚠️ **شما هم‌اکنون در استودیوی تولید ویدیو هستید.**\n\n"
        "در این بخش هیچ مدل متنی یا LLM فعال نیست و فقط پرامپت یا عکس برای ساخت ویدیو دریافت می‌شود.\n\n"
        "💬 برای **چت کردن با هوش مصنوعی** و **فرستادن فایل و عکس برای آنالیز و تحلیل**، باید حتماً وارد گزینه **«💬 گفتگوی جدید»** شوید.",
        reply_markup=markup,
        parse_mode="Markdown"
    )


@router.message(VideoStates.waiting_for_image, F.video)
async def handle_video_file_input(message: Message, state: FSMContext):
    """Processes video sent to studio to detect aspect ratio and configure future generations."""
    await state.clear()
    user_id = message.from_user.id
    video = message.video

    detected_ratio = detect_aspect_ratio(video.width, video.height)
    await update_user_video_settings(state, user_id, ratio=detected_ratio)
    await db.update_user_image_settings(user_id, ratio=detected_ratio)

    await message.answer(
        f"🎬 **ویدیوی شما دریافت و ابعاد آن تحلیل شد!**\n\n"
        f"📐 **نسبت ابعاد شناسایی شده:** `{detected_ratio}` (وضوح: {video.width}x{video.height})\n"
        f"✅ تنظیمات ربات به صورت خودکار روی نسبت `{detected_ratio}` تنظیم گردید تا تمام خروجی‌های بعدی عکس و ویدیو با همین ابعاد تولید شوند.\n\n"
        f"💡 تا زمانی که خودتان نسبت را عوض نکنید، نسبت ابعاد روی `{detected_ratio}` باقی می‌ماند.",
        reply_markup=get_video_menu_keyboard(),
        parse_mode="Markdown"
    )


async def execute_video_generation(
    message: Message,
    prompt: str,
    mode: str = "text",
    ratio: str = "16:9",
    seconds: str = "5",
    size: str = "720P",
    first_frame: Optional[str] = None,
    status_msg: Optional[Message] = None
):
    """Creates video task, polls progress, and sends mp4 to user."""
    start_time = time.time()
    init_text = format_video_progress(5, 0)
    if not status_msg:
        status_msg = await message.answer(init_text, parse_mode="HTML")
    else:
        try:
            await status_msg.edit_text(init_text, parse_mode="HTML")
        except Exception:
            pass

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VIDEO)

    # Clean command prefixes directly without running any LLM
    from app.services.prompt_enhancer import clean_command_prefixes
    enhanced_prompt = clean_command_prefixes(prompt)

    create_res = await video_service.create_video_task(
        prompt=enhanced_prompt,
        mode=mode,
        seconds=seconds,
        size=size,
        aspect_ratio=ratio,
        first_frame=first_frame
    )

    if not create_res.get("success"):
        err = create_res.get("error", "خطای نامشخص در ایجاد تسک ویدیو")
        await status_msg.edit_text(f"❌ **عدم موفقیت در ساخت ویدیو:**\n\n`{err}`", parse_mode="Markdown")
        return

    video_id = create_res.get("video_id")
    task_id = create_res.get("task_id")
    model_used = create_res.get("model_used")
    key_used = create_res.get("key_used")

    last_edit_time = 0.0

    async def update_progress(pct: int, status_str: str):
        nonlocal last_edit_time
        now = time.time()
        # Edit message at most once every 3.5 seconds to avoid Telegram flood limits
        if now - last_edit_time >= 3.5:
            last_edit_time = now
            elapsed_sec = int(now - start_time)
            try:
                await status_msg.edit_text(
                    format_video_progress(pct, elapsed_sec),
                    parse_mode="HTML"
                )
            except Exception:
                pass

    # Poll until ready
    poll_res = await video_service.poll_video_task(
        video_id=video_id,
        task_id=task_id,
        model_name=model_used,
        key=key_used,
        max_wait_seconds=300,
        poll_interval=5.0,
        progress_callback=update_progress
    )

    if not poll_res.get("success"):
        err = poll_res.get("error", "تولید ویدیو با خطا متوقف شد.")
        await status_msg.edit_text(f"❌ **خطا در تولید ویدیو:**\n\n`{err}`", parse_mode="Markdown")
        return

    video_url = poll_res.get("url")
    if not video_url:
        await status_msg.edit_text("❌ ویدیوی خروجی یافت نشد.")
        return

    try:
        await status_msg.edit_text(
            format_video_delivering_status(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO)

    # Safeguard prompt length and caption size for Telegram limit (1024 chars)
    clean_prompt = (prompt or "").strip()
    is_long_prompt = len(clean_prompt) > 650

    if is_long_prompt:
        caption_prompt = clean_prompt[:320] + "..."
        caption = (
            f"🎬 **ویدیوی شما آماده شد!**\n\n"
            f"📝 **توصیف:** {caption_prompt}\n"
            f"📐 **نسبت:** `{ratio}` | ⏱ **مدت:** `{seconds} ثانیه`\n"
            f"⚡ **موتور:** Nano Video Studio (Synchronized Audio-Video)\n\n"
            f"*(متن کامل پرامپت در پیام زیر ارسال شد 👇)*"
        )
    else:
        caption = (
            f"🎬 **ویدیوی شما آماده شد!**\n\n"
            f"📝 **توصیف:** {clean_prompt}\n"
            f"📐 **نسبت:** `{ratio}` | ⏱ **مدت:** `{seconds} ثانیه`\n"
            f"⚡ **موتور:** Nano Video Studio (Synchronized Audio-Video)"
        )
    if len(caption) > 950:
        caption = caption[:945] + "..."

    delivered = False
    filename = f"nano_video_{int(time.time())}.mp4"

    # Priority 1: Lightning-Fast Direct URL Delivery via Telegram Datacenters!
    # Telegram servers stream and cache the MP4 directly from CDN in < 3 seconds,
    # completely eliminating the massive local download & re-upload bottleneck!
    if video_url:
        try:
            await message.answer_video(
                video=video_url,
                caption=caption,
                parse_mode="Markdown",
                supports_streaming=True
            )
            delivered = True
        except Exception as e_url1:
            logger.info(f"Direct URL video delivery (Markdown) failed: {e_url1}. Trying plain caption...")
            try:
                short_caption = f"🎬 ویدیوی شما آماده شد!\n📐 نسبت: {ratio} | ⏱ مدت: {seconds} ثانیه\n⚡ Nano Video Studio"
                await message.answer_video(
                    video=video_url,
                    caption=short_caption,
                    supports_streaming=True
                )
                delivered = True
            except Exception as e_url2:
                logger.warning(f"Direct URL video delivery failed: {e_url2}. Falling back to byte download...")

    # Priority 2: Fallback to byte download & upload only if direct URL failed
    if not delivered:
        try:
            await status_msg.edit_text(
                "📤 <b>در حال دانلود و ارسال مستقیم ویدیو...</b>\n\n▰▰▰▰▰▰▰▰▰▰ 100%",
                parse_mode="HTML"
            )
        except Exception:
            pass

        video_bytes = await video_service.download_video(video_url, timeout=35.0)
        if video_bytes:
            try:
                video_file = BufferedInputFile(video_bytes, filename=filename)
                await message.answer_video(
                    video=video_file,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True
                )
                delivered = True
            except Exception as eb1:
                logger.warning(f"Buffered video delivery failed: {eb1}")
                try:
                    short_caption = f"🎬 ویدیوی شما آماده شد!\n📐 نسبت: {ratio} | ⏱ مدت: {seconds} ثانیه\n⚡ Nano Video Studio"
                    video_file = BufferedInputFile(video_bytes, filename=filename)
                    await message.answer_video(
                        video=video_file,
                        caption=short_caption,
                        supports_streaming=True
                    )
                    delivered = True
                except Exception as eb2:
                    logger.warning(f"Buffered video delivery 2 failed: {eb2}")

            if not delivered:
                try:
                    doc_file = BufferedInputFile(video_bytes, filename=filename)
                    await message.answer_document(
                        document=doc_file,
                        caption="📁 فایل ویدیو با کیفیت اصلی",
                        parse_mode=None
                    )
                    delivered = True
                except Exception as ed:
                    logger.error(f"Doc video delivery failed: {ed}")

    if delivered:
        try:
            await status_msg.delete()
        except Exception:
            pass

        if is_long_prompt:
            try:
                from app.bot.utils import split_message
                for p_chunk in split_message(clean_prompt, max_length=3800):
                    await message.answer(
                        f"📝 **متن کامل پرامپت ({len(clean_prompt)} کاراکتر):**\n\n"
                        f"```text\n{p_chunk}\n```",
                        parse_mode="Markdown"
                    )
            except Exception as e_pmsg:
                logger.debug(f"Sending long video prompt text failed: {e_pmsg}")
    else:
        await status_msg.edit_text(
            "⚠️ **ویدیو با موفقیت ساخته شد، اما به دلیل اختلال ارتباطی سرور در ارسال به تلگرام با تاخیر مواجه شد.**\n"
            "لطفاً لحظاتی دیگر مجدداً تلاش فرمایید.",
            parse_mode="Markdown"
        )
