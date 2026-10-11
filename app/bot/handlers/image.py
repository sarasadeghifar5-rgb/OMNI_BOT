import io
import time
import asyncio
import html
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

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
from aiogram.enums import ChatAction, ParseMode

from app.services.agnes_image import AgnesImageService
from app.services.prompt_enhancer import PromptEnhancerService
from app.bot.database import BotDatabase
from app.bot.keyboards import (
    get_gpt_image_menu_keyboard,
    get_aspect_ratio_keyboard,
    get_resolution_keyboard,
    get_image_action_keyboard,
    get_main_menu_keyboard
)
from app.bot.utils import safe_reply, detect_aspect_ratio

logger = logging.getLogger("GPTImageHandler")
router = Router(name="image_router")
agnes_service = AgnesImageService()
db = BotDatabase.get_instance()

# Fast Image Cache for immediate document delivery
IMAGE_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "image_cache"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
RECENT_IMAGE_CACHE: Dict[int, bytes] = {}
RECENT_PROMPT_CACHE: Dict[int, str] = {}


def format_image_progress(pct: int, elapsed_sec: int) -> str:
    """Renders the image generation progress matching user specification."""
    filled = min(10, max(1, int(round(pct / 10))))
    bar = "▰" * filled + "▱" * (10 - filled)
    if elapsed_sec < 60:
        elapsed_str = f"{elapsed_sec}s"
    else:
        elapsed_str = f"{elapsed_sec // 60}m {elapsed_sec % 60}s"
    return (
        "🎨 <b>در حال پردازش تصویر</b>\n\n"
        f"{bar} {max(5, pct)}%\n\n"
        f"⏱ {elapsed_str} / ~2m\n\n"
        "✨ لطفاً کمی صبر کنید…"
    )


def format_delivering_status() -> str:
    """Fast delivery progress indicator."""
    return (
        "🎨 <b>تصویر با موفقیت تولید شد!</b>\n\n"
        "▰▰▰▰▰▰▰▰▰▰ 100%\n\n"
        "🚀 <b>در حال ارسال آنی به تلگرام...</b>"
    )


def save_image_to_cache(msg_id: int, img_bytes: bytes, prompt: str = ""):
    """Caches generated image in memory and disk for instant document retrieval."""
    if not msg_id or not img_bytes:
        return
    try:
        RECENT_IMAGE_CACHE[msg_id] = img_bytes
        if prompt:
            RECENT_PROMPT_CACHE[msg_id] = prompt
        file_path = IMAGE_CACHE_DIR / f"img_{msg_id}.png"
        file_path.write_bytes(img_bytes)
    except Exception as e:
        logger.warning(f"Failed to cache image for msg {msg_id}: {e}")

async def get_image_for_message(bot, message: Optional[Message], state: FSMContext) -> Tuple[Optional[bytes], str]:
    """
    Lightning-fast multi-tier resolver for image bytes:
    1. Memory cache (0ms)
    2. Local NVMe/SSD disk cache (1ms)
    3. FSM State cache (1ms)
    4. Telegram API CDN direct download (fallback for previous sessions)
    """
    msg_id = message.message_id if message else 0
    prompt = RECENT_PROMPT_CACHE.get(msg_id, "")

    # 1. Check in-memory cache
    if msg_id and msg_id in RECENT_IMAGE_CACHE:
        return RECENT_IMAGE_CACHE[msg_id], prompt

    # 2. Check local disk cache
    if msg_id:
        file_path = IMAGE_CACHE_DIR / f"img_{msg_id}.png"
        if file_path.exists():
            try:
                data = file_path.read_bytes()
                RECENT_IMAGE_CACHE[msg_id] = data
                return data, prompt
            except Exception:
                pass

    # 3. Check FSM State
    if state:
        try:
            sdata = await state.get_data()
            if sdata.get("last_image_bytes"):
                return sdata.get("last_image_bytes"), sdata.get("last_prompt", prompt)
            if sdata.get("last_image_url"):
                url_bytes = await agnes_service.download_image(sdata.get("last_image_url"), timeout=15.0)
                if url_bytes:
                    return url_bytes, sdata.get("last_prompt", prompt)
        except Exception:
            pass

    # 4. Fallback: Download highest quality photo directly from Telegram servers
    if message and getattr(message, "photo", None):
        try:
            photo = message.photo[-1]
            file_io = io.BytesIO()
            await bot.download(photo.file_id, destination=file_io)
            data = file_io.getvalue()
            if data:
                save_image_to_cache(msg_id, data, prompt)
                return data, prompt
        except Exception as e:
            logger.warning(f"Failed downloading photo from Telegram: {e}")

    return None, prompt

# FSM States
class GPTImageStates(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_edit_photo = State()
    waiting_for_edit_prompt = State()

STUDIO_INTRO_TEXT = """🍌 **استودیوی ادیت عکس نانو بنانا (Nano Banana Studio)**

✨ **حالت استودیو عکس فعال شد (اختصاصی تولید و ادیت تصویر):**
• 🎨 **تولید عکس با پرامپت متنی:** هر توصیف متنی به فارسی یا انگلیسی ارسال کنید، مستقیماً بدون نیاز به دستور اضافی برای تولید تصویر پردازش می‌شود.
• 🖌️ **ادیت هوشمند عکس:** هر تصویری بفرستید، می‌توانید تغییرات، رنگ، سبک یا پس‌زمینه آن را با حفظ ترکیب اصلی تغییر دهید.
• 📐 **پشتیبانی از انواع ابعاد:** مربعی (1:1)، عریض (16:9)، استوری (9:16)، پرتره و سینمایی
• 📏 **کیفیت و رزولوشن:** از 1K تا 4K Ultra HD

⚠️ **توجه:** در این بخش هیچ مدل متنی یا LLM چت نمی‌کند و همه پیام‌ها برای ساخت یا ادیت عکس هستند.
💬 برای **گفتگو و چت با هوش مصنوعی** یا **تحلیل و آنالیز فایل و عکس**، حتماً دکمه **«💬 گفتگوی جدید»** را بزنید.

👇 یکی از گزینه‌های زیر را انتخاب کنید یا پرامپت خود را بنویسید:"""


async def get_user_settings(state: Optional[FSMContext] = None, user_id: Optional[int] = None) -> tuple[str, str]:
    """Retrieves ratio and size from FSM state data, falling back to SQLite database."""
    ratio = None
    size = None
    if state:
        try:
            data = await state.get_data()
            ratio = data.get("ratio")
            size = data.get("size")
        except Exception:
            pass

    if user_id and (not ratio or not size):
        try:
            db_ratio, db_size = await db.get_user_image_settings(user_id)
            if not ratio:
                ratio = db_ratio
            if not size:
                size = db_size
            if state:
                await state.update_data(ratio=ratio, size=size)
        except Exception:
            pass

    return ratio or "1:1", size or "1K"


async def update_user_settings(
    state: Optional[FSMContext] = None,
    user_id: Optional[int] = None,
    ratio: Optional[str] = None,
    size: Optional[str] = None
):
    """Updates ratio and size in both FSM state and SQLite database."""
    if state:
        data = {}
        if ratio:
            data["ratio"] = ratio
        if size:
            data["size"] = size
        if data:
            try:
                await state.update_data(**data)
            except Exception:
                pass
    if user_id:
        try:
            await db.update_user_image_settings(user_id, ratio=ratio, size=size)
        except Exception:
            pass


# =====================================================================
# 1. Main Studio Entrypoints (Commands, Menu Buttons, Callbacks)
# =====================================================================

@router.message(Command("image", "img", "photo", "generate", "banana"))
@router.message(F.text.in_({
    "🍌 ادیت عکس نانو بنانا", "ادیت عکس نانو بنانا", "ادیت عکس نانو بنانا 🍌",
    "🎨 تولید و ادیت عکس جی پی تی", "تولید و ادیت عکس جی پی تی",
    "🎨 استودیو عکس 🍌", "استودیو عکس", "تولید عکس", "ادیت عکس"
}))
async def cmd_gpt_image_studio(message: Message, state: FSMContext):
    """Opens the GPT Image Studio main menu or generates directly if prompt is passed."""
    user_id = message.from_user.id
    # Switch user's active model to Image Studio
    await db.update_user_model(user_id, "agnes-image-2.5-flash")

    command_args = ""
    if message.text and message.text.startswith("/"):
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            command_args = parts[1].strip()

    # If the user passed prompt directly in command (e.g. /image a cute cat)
    if command_args:
        ratio, size = await get_user_settings(state, user_id)
        await execute_text_generation(message, command_args, ratio, size, state)
        return

    ratio, size = await get_user_settings(state, user_id)
    await state.clear()
    await safe_reply(
        message,
        STUDIO_INTRO_TEXT,
        reply_markup=get_gpt_image_menu_keyboard(ratio=ratio, size=size)
    )


@router.message(Command("edit", "edit_image"))
async def cmd_edit_image_direct(message: Message, state: FSMContext):
    """Direct command to edit a photo (handles replied photo or asks for photo)."""
    user_id = message.from_user.id
    await db.update_user_model(user_id, "agnes-image-2.5-flash")
    # Check if this command is a reply to a photo
    if message.reply_to_message and message.reply_to_message.photo:
        instruction = ""
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1:
            instruction = parts[1].strip()

        # Download photo
        photo = message.reply_to_message.photo[-1]
        detected_ratio = detect_aspect_ratio(photo.width, photo.height)
        await update_user_settings(state, user_id, ratio=detected_ratio)
        await db.update_user_video_settings(user_id, ratio=detected_ratio)

        file_io = io.BytesIO()
        await message.bot.download(photo.file_id, destination=file_io)
        photo_bytes = file_io.getvalue()

        ratio, size = await get_user_settings(state, user_id)

        if instruction:
            await execute_image_edit(message, photo_bytes, instruction, ratio, size, state)
        else:
            await state.update_data(edit_image_bytes=photo_bytes)
            await state.set_state(GPTImageStates.waiting_for_edit_prompt)
            await message.answer(
                f"🖌️ **تصویر ریپلای شده دریافت شد!**\n\n"
                f"📐 **نسبت ابعاد عکس:** `{detected_ratio}` (تنظیم خودکار ✅)\n\n"
                "لطفاً بنویسید چه تغییری می‌خواهید در این تصویر اعمال شود؟\n"
                "(مثال: «لباس را به رنگ قرمز درآور»، «پس‌زمینه را به یک ساحل آفتابی تبدیل کن»)"
            )
        return

    await state.set_state(GPTImageStates.waiting_for_edit_photo)
    await message.answer(
        "🖌️ **حالت ویرایش عکس فعال شد.**\n\n"
        "لطفاً تصویری که قصد ویرایش آن را دارید بفرستید:"
    )


@router.callback_query(F.data.in_({"menu:gpt_image", "menu:image_studio"}))
async def cb_gpt_image_studio(call: CallbackQuery, state: FSMContext):
    """Handles callback query opening the image studio."""
    user_id = call.from_user.id
    await db.update_user_model(user_id, "agnes-image-2.5-flash")
    ratio, size = await get_user_settings(state, user_id)
    await state.clear()
    try:
        await call.message.edit_text(
            STUDIO_INTRO_TEXT,
            reply_markup=get_gpt_image_menu_keyboard(ratio=ratio, size=size)
        )
    except Exception:
        await call.message.answer(
            STUDIO_INTRO_TEXT,
            reply_markup=get_gpt_image_menu_keyboard(ratio=ratio, size=size)
        )
    await call.answer()


# =====================================================================
# 2. Studio Configuration (Aspect Ratio & Resolution)
# =====================================================================

@router.callback_query(F.data == "gpt_img:select_ratio")
async def cb_select_ratio(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    ratio, _ = await get_user_settings(state, user_id)
    await call.message.edit_text(
        "📐 **انتخاب نسبت ابعاد تصویر (Aspect Ratio):**\n\n"
        "یکی از ابعاد استاندارد زیر را برای تصویر خود انتخاب فرمایید:\n"
        "💡 همچنین اگر تصویری با نسبت مشخص (مثلاً 16:9 یا 9:16) بفرستید، نسبت آن خودکار تنظیم شده و تا تغییر دستی روی همان باقی می‌ماند.",
        reply_markup=get_aspect_ratio_keyboard(current_ratio=ratio)
    )
    await call.answer()


@router.callback_query(F.data.startswith("gpt_img:set_ratio:"))
async def cb_set_ratio(call: CallbackQuery, state: FSMContext):
    new_ratio = call.data[len("gpt_img:set_ratio:"):]
    user_id = call.from_user.id
    await update_user_settings(state, user_id, ratio=new_ratio)
    # Also synchronize video ratio
    await db.update_user_video_settings(user_id, ratio=new_ratio)
    _, size = await get_user_settings(state, user_id)
    await call.answer(f"نسبت ابعاد به {new_ratio} تغییر کرد ✅")
    await call.message.edit_text(
        STUDIO_INTRO_TEXT,
        reply_markup=get_gpt_image_menu_keyboard(ratio=new_ratio, size=size)
    )


@router.callback_query(F.data == "gpt_img:select_size")
async def cb_select_size(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    is_vip = await db.is_user_vip(user_id)
    _, size = await get_user_settings(state, user_id)
    await call.message.edit_text(
        "📏 **انتخاب کیفیت و رزولوشن خروجی (Resolution):**\n\n"
        "⚡ کیفیت **1K** به صورت رایگان برای تمام کاربران در دسترس است.\n"
        "⭐ کیفیت‌های **2K** ، **3K** و **4K** فقط با اشتراک استار تلگرام باز می‌شوند.\n\n"
        "رزولوشن مورد نظر را برای تولید تصویر انتخاب فرمایید:",
        reply_markup=get_resolution_keyboard(current_size=size, is_vip=is_vip)
    )
    await call.answer()


@router.callback_query(F.data.startswith("gpt_img:set_size:"))
async def cb_set_size(call: CallbackQuery, state: FSMContext):
    new_size = call.data[len("gpt_img:set_size:"):]
    user_id = call.from_user.id
    is_vip = await db.is_user_vip(user_id)

    if new_size in ("2K", "3K", "4K") and not is_vip:
        await call.answer("⭐ کیفیت‌های 2K و 3K و 4K فقط با استار تلگرام باز می‌شوند!", show_alert=True)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ خرید اشتراک با استار تلگرام (VIP)", callback_data="act:buy_service")],
            [InlineKeyboardButton(text="🔙 بازگشت به انتخاب کیفیت", callback_data="gpt_img:select_size")]
        ])
        await call.message.answer(
            f"🔒 **کیفیت `{new_size}` نیازمند اشتراک استار تلگرام است!**\n\n"
            f"کیفیت‌های اولترا HD شامل **2K** ، **3K** و **4K** به همراه مدل‌های برتر هوش مصنوعی مخصوص کاربران دارای اشتراک استار هستند.\n"
            f"با تهیه اشتراک، قفل این کیفیت‌ها فوراً برای شما باز خواهد شد. ⭐",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return

    await update_user_settings(state, user_id, size=new_size)
    ratio, _ = await get_user_settings(state, user_id)
    await call.answer(f"رزولوشن به {new_size} تغییر یافت ✅")
    await call.message.edit_text(
        STUDIO_INTRO_TEXT,
        reply_markup=get_gpt_image_menu_keyboard(ratio=ratio, size=new_size)
    )


# =====================================================================
# 3. Text to Image Flow
# =====================================================================

@router.callback_query(F.data == "gpt_img:new_text")
async def cb_new_text_image(call: CallbackQuery, state: FSMContext):
    """Starts waiting for text prompt."""
    await state.set_state(GPTImageStates.waiting_for_prompt)
    await call.message.answer(
        "🎨 **ساخت عکس جدید با پرامپت متنی:**\n\n"
        "توصیف تصویر مورد نظر خود را ارسال کنید (به فارسی یا انگلیسی).\n"
        "هرچه جزئیات بیشتری درباره سبک، نورپردازی و محیط بنویسید، نتیجه جذاب‌تر خواهد بود!\n\n"
        "مثال: «یک فضانورد سوار بر اسب سفید روی سطح مریخ، سبک نقاشی رنگ روغن با نور غروب خورشید»"
    )
    await call.answer()


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

async def is_image_studio_active(user_id: int) -> bool:
    user = await db.get_or_create_user(user_id)
    from app.config import get_model_capabilities
    caps = get_model_capabilities(user.get("selected_model", "gemini"))
    return bool(caps.get("is_image_studio"))

async def image_studio_text_filter(message: Message, state: FSMContext) -> bool:
    if not message.text or message.text.startswith("/") or not message.from_user:
        return False
    if message.text.strip() in SYSTEM_BUTTON_TEXTS:
        return False
    cur_state = await state.get_state()
    if cur_state == GPTImageStates.waiting_for_edit_prompt.state:
        return False
    return await is_image_studio_active(message.from_user.id)


@router.message(GPTImageStates.waiting_for_prompt, F.text)
@router.message(image_studio_text_filter)
async def handle_prompt_received(message: Message, state: FSMContext):
    """Processes user text prompt for image generation in studio mode directly without any LLM."""
    prompt = message.text.strip()
    if prompt.startswith("/"):
        await state.clear()
        return

    user_id = message.from_user.id
    ratio, size = await get_user_settings(state, user_id)

    # Check if there is an image awaiting edit prompt
    data = await state.get_data()
    edit_bytes = data.get("edit_image_bytes")
    if edit_bytes:
        await state.update_data(edit_image_bytes=None)
        await execute_image_edit(message, edit_bytes, prompt, ratio, size, state)
        return

    await state.clear()
    await execute_text_generation(message, prompt, ratio, size, state)


async def deliver_image_safely(
    message: Message,
    status_msg: Message,
    img_bytes: Optional[bytes],
    img_url: Optional[str],
    caption_title: str,
    prompt: str,
    ratio: str,
    size: str,
    can_regen: bool = True,
    state: Optional[FSMContext] = None
):
    """
    Guarantees lightning-fast photo/document delivery to Telegram without ever failing on
    caption length limits, markdown parse errors, or connection quirks.
    Uses ultra-fast direct URL delivery so users receive photos in < 1 second.
    """
    clean_prompt = (prompt or "").strip()
    is_long_prompt = len(clean_prompt) > 650

    if is_long_prompt:
        caption_prompt = clean_prompt[:320] + "..."
        caption_text = (
            f"{caption_title}\n\n"
            f"📝 **پرامپت:** {caption_prompt}\n"
            f"📐 **نسبت:** `{ratio}` | 📏 **کیفیت:** `{size}`\n"
            f"✨ **مدل:** `Nano Banana Pro`\n\n"
            f"*(متن کامل پرامپت در پیام زیر ارسال شد 👇)*"
        )
    else:
        caption_text = (
            f"{caption_title}\n\n"
            f"📝 **پرامپت:** {clean_prompt}\n"
            f"📐 **نسبت:** `{ratio}` | 📏 **کیفیت:** `{size}`\n"
            f"✨ **مدل:** `Nano Banana Pro`"
        )
    if len(caption_text) > 950:
        caption_text = caption_text[:947] + "..."

    reply_markup = get_image_action_keyboard(can_edit=True, can_regen=can_regen)

    delivered = False
    sent_msg = None

    # Step 1: Lightning-Fast Direct URL Delivery via Telegram Datacenters
    # Telegram servers fetch directly from the high-speed CDN in < 1 second,
    # completely eliminating local download & re-upload bottleneck!
    if img_url:
        try:
            sent_msg = await message.answer_photo(
                photo=img_url,
                caption=caption_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            delivered = True
        except Exception as e_url1:
            logger.info(f"Direct URL delivery (Markdown) failed: {e_url1}. Trying plain caption...")
            try:
                short_cap = f"{caption_title}\n📐 نسبت: {ratio} | 📏 کیفیت: {size}"
                sent_msg = await message.answer_photo(
                    photo=img_url,
                    caption=short_cap,
                    reply_markup=reply_markup
                )
                delivered = True
            except Exception as e_url2:
                logger.warning(f"Direct URL delivery failed: {e_url2}. Falling back to byte download/upload...")

    # Step 2: Fallback to byte download & upload only if direct URL failed
    if not delivered:
        try:
            await status_msg.edit_text(
                "📤 <b>در حال دانلود و ارسال مستقیم تصویر...</b>\n\n▰▰▰▰▰▰▰▰▰▰ 100%",
                parse_mode="HTML"
            )
        except Exception:
            pass

        if not img_bytes and img_url:
            img_bytes = await agnes_service.download_image(img_url, timeout=25.0)

        if img_bytes:
            photo_file = BufferedInputFile(img_bytes, filename=f"nano_banana_{int(time.time())}.png")
            try:
                sent_msg = await message.answer_photo(
                    photo=photo_file,
                    caption=caption_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                delivered = True
            except Exception as eb1:
                logger.warning(f"Buffered photo delivery failed: {eb1}")
                try:
                    short_cap = f"{caption_title}\n📐 نسبت: {ratio} | 📏 کیفیت: {size}"
                    sent_msg = await message.answer_photo(
                        photo=photo_file,
                        caption=short_cap,
                        reply_markup=reply_markup
                    )
                    delivered = True
                except Exception as eb2:
                    logger.warning(f"Buffered photo delivery 2 failed: {eb2}")

        if not delivered and img_bytes:
            # Step 3: Final fallback - uncompressed document
            doc_file = BufferedInputFile(img_bytes, filename=f"nano_banana_{int(time.time())}.png")
            try:
                sent_msg = await message.answer_document(
                    document=doc_file,
                    caption=caption_text[:900],
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                delivered = True
            except Exception as ed:
                logger.error(f"Doc delivery failed: {ed}")

    # Post-delivery cleanup & background caching
    if delivered and sent_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

        # If prompt was long, deliver the full untruncated prompt in a dedicated text message
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
                logger.debug(f"Sending long prompt text failed: {e_pmsg}")

        # Non-blocking background caching: prepares RAM & disk cache for instant document requests
        async def _bg_cache_and_state():
            try:
                b = img_bytes
                if not b and img_url:
                    b = await agnes_service.download_image(img_url, timeout=20.0)
                if not b and getattr(sent_msg, "photo", None):
                    bio = io.BytesIO()
                    await message.bot.download(sent_msg.photo[-1].file_id, destination=bio)
                    b = bio.getvalue()
                if b:
                    save_image_to_cache(sent_msg.message_id, b, prompt)
                    if state:
                        await state.update_data(last_image_bytes=b)
            except Exception as e_bg:
                logger.debug(f"Background image caching: {e_bg}")

        asyncio.create_task(_bg_cache_and_state())
    elif not delivered:
        await status_msg.edit_text(
            "⚠️ تصویر با موفقیت تولید شد اما در ارسال آن به تلگرام خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_markup=reply_markup
        )


async def execute_text_generation(
    message: Message,
    prompt: str,
    ratio: str,
    size: str,
    state: FSMContext
):
    """Executes Agnes AI text-to-image request and delivers photo to user."""
    user_id = message.from_user.id
    is_vip = await db.is_user_vip(user_id)
    if size in ("2K", "3K", "4K") and not is_vip:
        size = "1K"
        await update_user_settings(state, user_id, size="1K")

    start_time = time.time()
    status_msg = await message.answer(format_image_progress(5, 0), parse_mode="HTML")

    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
    except Exception:
        pass

    # Clean command prefixes directly without running any LLM
    from app.services.prompt_enhancer import clean_command_prefixes
    enhanced_prompt = clean_command_prefixes(prompt)

    stop_ticker = asyncio.Event()

    async def _progress_ticker():
        steps = [20, 35, 50, 65, 80, 90, 95]
        idx = 0
        while not stop_ticker.is_set():
            try:
                await asyncio.sleep(3.5)
            except asyncio.CancelledError:
                break
            if stop_ticker.is_set():
                break
            elapsed_sec = int(time.time() - start_time)
            pct = steps[min(idx, len(steps) - 1)]
            idx += 1
            try:
                await status_msg.edit_text(format_image_progress(pct, elapsed_sec), parse_mode="HTML")
            except Exception:
                pass

    ticker_task = asyncio.create_task(_progress_ticker())

    try:
        result = await agnes_service.generate_image(
            prompt=enhanced_prompt,
            size=size,
            ratio=ratio,
            timeout=120.0
        )
    finally:
        stop_ticker.set()
        ticker_task.cancel()
        try:
            await ticker_task
        except asyncio.CancelledError:
            pass

    if not result.get("success"):
        logger.warning(f"Agnes generation failed ({result.get('error')}). Failing over to Puter AI...")
        try:
            from app.services.puter_image import PuterImageService
            puter_res = await PuterImageService.generate_image(
                prompt=enhanced_prompt,
                model="nano-banana-pro" if size in ("2K", "4K") else "nano-banana",
                aspect_ratio=ratio,
                resolution=size if size in ("1K", "2K", "4K") else "1K"
            )
            if (puter_res.get("success") or puter_res.get("status") == "success") and (puter_res.get("url") or puter_res.get("image_url")):
                result = {
                    "success": True,
                    "url": puter_res.get("url") or puter_res.get("image_url")
                }
        except Exception as e_pt:
            logger.warning(f"Puter fallback also failed: {e_pt}")

    if not result.get("success"):
        err = result.get("error", "خطای ناشناخته")
        await status_msg.edit_text(
            f"⚠️ **متاسفانه در تولید تصویر خطایی رخ داد:**\n\n`{err}`\n\n"
            f"می‌توانید پرامپت خود را تغییر دهید یا دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 تلاش مجدد", callback_data="gpt_img:new_text")],
                [InlineKeyboardButton(text="🔙 منوی استودیو", callback_data="menu:gpt_image")]
            ]),
            parse_mode="Markdown"
        )
        return

    # Update status to indicate immediate delivery
    try:
        await status_msg.edit_text(
            format_delivering_status(),
            parse_mode="HTML"
        )
    except Exception:
        pass

    img_url = result.get("url")

    # Save last generated image data in state for quick editing / regeneration
    await state.update_data(
        last_prompt=prompt,
        last_image_url=img_url,
        ratio=ratio,
        size=size
    )

    await deliver_image_safely(
        message=message,
        status_msg=status_msg,
        img_bytes=None,
        img_url=img_url,
        caption_title="🍌 **ادیت عکس نانو بنانا**",
        prompt=prompt,
        ratio=ratio,
        size=size,
        can_regen=True,
        state=state
    )


# =====================================================================
# 4. Image to Image (Editing) Flow
# =====================================================================

@router.callback_query(F.data == "gpt_img:new_edit")
async def cb_new_edit_image(call: CallbackQuery, state: FSMContext):
    """Starts waiting for photo to edit."""
    await state.set_state(GPTImageStates.waiting_for_edit_photo)
    await call.message.answer(
        "🖌️ **ادیت و تغییر عکس ارسالی (Image-to-Image):**\n\n"
        "لطفاً تصویری که می‌خواهید ویرایش شود را بفرستید.\n"
        "💡 می‌توانید دستور ویرایش را در کپشن (توضیح) عکس نیز بنویسید."
    )
    await call.answer()


@router.callback_query(F.data == "gpt_img:edit_last")
async def cb_edit_last_image(call: CallbackQuery, state: FSMContext):
    """Triggers editing of the last generated image."""
    data = await state.get_data()
    last_bytes = data.get("last_image_bytes")
    last_url = data.get("last_image_url")

    target_img = last_bytes or last_url
    if not target_img:
        await call.answer("⚠️ تصویر قبلی یافت نشد. لطفاً عکس جدیدی ارسال کنید.", show_alert=True)
        await state.set_state(GPTImageStates.waiting_for_edit_photo)
        await call.message.answer("📸 لطفاً عکس مورد نظر را ارسال کنید:")
        return

    await state.update_data(edit_image_bytes=target_img)
    await state.set_state(GPTImageStates.waiting_for_edit_prompt)
    await call.message.answer(
        "🖌️ **آماده دریافت دستور ادیت:**\n\n"
        "لطفاً بنویسید چه تغییری در این تصویر داده شود؟\n"
        "(مثال: «لباسش رو قرمز کن»، «پس‌زمینه رو ساحل کن»، «سبک عکس رو سایبرپانک کن»)"
    )
    await call.answer()


@router.callback_query(F.data == "gpt_img:regen_last")
async def cb_regen_last_image(call: CallbackQuery, state: FSMContext):
    """Regenerates the last prompt with fresh random variation."""
    data = await state.get_data()
    last_prompt = data.get("last_prompt")
    if not last_prompt:
        await call.answer("⚠️ پرامپت قبلی یافت نشد.", show_alert=True)
        return

    user_id = call.from_user.id
    ratio, size = await get_user_settings(state, user_id)
    await call.answer("🔄 در حال تولید مجدد تصویر...")
    await execute_text_generation(call.message, last_prompt, ratio, size, state)


@router.message(GPTImageStates.waiting_for_edit_photo, F.photo)
async def handle_photo_for_edit(message: Message, state: FSMContext):
    """Receives photo when user was prompted to send one for editing."""
    photo = message.photo[-1]
    user_id = message.from_user.id

    # Auto-detect aspect ratio from input photo dimensions
    detected_ratio = detect_aspect_ratio(photo.width, photo.height)
    await update_user_settings(state, user_id, ratio=detected_ratio)
    await db.update_user_video_settings(user_id, ratio=detected_ratio)

    file_io = io.BytesIO()
    await message.bot.download(photo.file_id, destination=file_io)
    photo_bytes = file_io.getvalue()

    caption = (message.caption or "").strip()
    ratio, size = await get_user_settings(state, user_id)

    if caption:
        # User supplied prompt in caption directly
        await state.set_state(None)
        await execute_image_edit(message, photo_bytes, caption, ratio, size, state)
    else:
        # Prompt user for instructions
        await state.update_data(edit_image_bytes=photo_bytes)
        await state.set_state(GPTImageStates.waiting_for_edit_prompt)
        await message.answer(
            f"🖌️ **تصویر شما با موفقیت دریافت شد!**\n\n"
            f"📐 **نسبت ابعاد عکس:** `{detected_ratio}` (تنظیم خودکار برای تمام خروجی‌های بعدی ✅)\n"
            f"تا زمانی که خودتان نسبت را عوض نکنید، خروجی‌ها با نسبت `{detected_ratio}` ساخته می‌شوند.\n\n"
            "اکنون بفرمایید چه تغییری می‌خواهید در این تصویر اعمال شود؟\n"
            "(مثال: «لباسش رو قرمز کن»، «پس‌زمینه رو ساحل کن»، «سبک عکس رو نقاشی رنگ روغن کن»)"
        )


@router.message(GPTImageStates.waiting_for_edit_prompt, F.text)
async def handle_edit_prompt_received(message: Message, state: FSMContext):
    """Receives edit instructions text and executes image-to-image transformation."""
    instruction = message.text.strip()
    if instruction.startswith("/"):
        await state.set_state(None)
        return

    data = await state.get_data()
    photo_bytes = data.get("edit_image_bytes")
    if not photo_bytes:
        await state.set_state(GPTImageStates.waiting_for_edit_photo)
        await message.answer("⚠️ تصویری برای ویرایش پیدا نشد. لطفاً ابتدا عکس را ارسال کنید.")
        return

    user_id = message.from_user.id
    ratio, size = await get_user_settings(state, user_id)
    await state.set_state(None)
    await execute_image_edit(message, photo_bytes, instruction, ratio, size, state)


async def execute_image_edit(
    message: Message,
    image_input: bytes,
    prompt: str,
    ratio: str,
    size: str,
    state: FSMContext
):
    """Executes Agnes AI image-to-image edit and delivers result."""
    user_id = message.from_user.id
    is_vip = await db.is_user_vip(user_id)
    if size in ("2K", "3K", "4K") and not is_vip:
        size = "1K"
        await update_user_settings(state, user_id, size="1K")

    # Double check image dimensions using PIL to ensure exact ratio match
    try:
        from PIL import Image
        pil_img = Image.open(io.BytesIO(image_input))
        detected_ratio = detect_aspect_ratio(pil_img.width, pil_img.height)
        ratio = detected_ratio
        await update_user_settings(state, user_id, ratio=detected_ratio)
        await db.update_user_video_settings(user_id, ratio=detected_ratio)
    except Exception:
        pass

    start_time = time.time()
    status_msg = await message.answer(format_image_progress(5, 0), parse_mode="HTML")

    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
    except Exception:
        pass

    # Clean command prefixes directly without running any LLM
    from app.services.prompt_enhancer import clean_command_prefixes
    enhanced_prompt = clean_command_prefixes(prompt)

    stop_ticker = asyncio.Event()

    async def _progress_ticker():
        steps = [20, 35, 50, 65, 80, 90, 95]
        idx = 0
        while not stop_ticker.is_set():
            try:
                await asyncio.sleep(3.5)
            except asyncio.CancelledError:
                break
            if stop_ticker.is_set():
                break
            elapsed_sec = int(time.time() - start_time)
            pct = steps[min(idx, len(steps) - 1)]
            idx += 1
            try:
                await status_msg.edit_text(format_image_progress(pct, elapsed_sec), parse_mode="HTML")
            except Exception:
                pass

    ticker_task = asyncio.create_task(_progress_ticker())

    try:
        edit_prompt = enhanced_prompt.strip()
        lowered = edit_prompt.lower()
        if any(w in lowered for w in ("quality", "enhance", "upscale", "sharpen", "improve", "restore", "hd", "high resolution")):
            edit_prompt = (
                f"{edit_prompt}. Upscale and restore this photo: increase sharpness, resolution and fine detail, "
                "reduce noise and blur, improve lighting and colors."
            )
        edit_prompt += " Keep the original composition, subject, face identity, pose and background exactly the same."

        result = await agnes_service.edit_image(
            image_input=image_input,
            prompt=edit_prompt,
            size=size,
            ratio=ratio,
            timeout=120.0
        )
    finally:
        stop_ticker.set()
        ticker_task.cancel()
        try:
            await ticker_task
        except asyncio.CancelledError:
            pass

    if not result.get("success"):
        err = result.get("error", "خطای ادیت تصویر")
        await status_msg.edit_text(
            f"⚠️ **متاسفانه در ادیت تصویر خطایی رخ داد:**\n\n`{err}`\n\n"
            f"می‌توانید عکس دیگری بفرستید یا دستور ادیت را اصلاح کنید.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🖌️ ارسال مجدد عکس", callback_data="gpt_img:new_edit")],
                [InlineKeyboardButton(text="🔙 منوی استودیو", callback_data="menu:gpt_image")]
            ]),
            parse_mode="Markdown"
        )
        return

    try:
        await status_msg.edit_text(
            format_delivering_status(),
            parse_mode="HTML"
        )
    except Exception:
        pass

    img_url = result.get("url")

    # Save newly edited image as the last image so user can keep chaining edits!
    await state.update_data(
        last_prompt=prompt,
        last_image_url=img_url,
        edit_image_bytes=img_url,
        ratio=ratio,
        size=size
    )

    await deliver_image_safely(
        message=message,
        status_msg=status_msg,
        img_bytes=None,
        img_url=img_url,
        caption_title="🖌️ **تصویر با موفقیت ادیت شد!**",
        prompt=prompt,
        ratio=ratio,
        size=size,
        can_regen=False,
        state=state
    )


@router.callback_query(F.data == "gpt_img:send_doc")
async def cb_send_image_as_document(call: CallbackQuery, state: FSMContext):
    """
    Sends the generated/edited image as an uncompressed document inside Telegram.
    Guaranteed lightning-fast delivery with multi-tier caching (RAM -> SSD -> FSM -> Telegram CDN).
    """
    # 1. Immediately acknowledge the callback query so the button spinner stops INSTANTLY!
    try:
        await call.answer("⚡ در حال ارسال فایل با کیفیت اصلی...")
    except Exception:
        pass

    chat_id = call.message.chat.id if call.message else call.from_user.id

    # 2. Show 'upload_document' chat action in Telegram header
    try:
        await call.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    except Exception:
        pass

    # 3. Retrieve image bytes from RAM cache / disk / state / Telegram CDN
    img_bytes, prompt = await get_image_for_message(call.bot, call.message, state)

    if not img_bytes:
        await call.bot.send_message(
            chat_id=chat_id,
            text="⚠️ متاسفانه فایل این تصویر در حافظه موقت یافت نشد. لطفاً دستور ادیت یا تصویر جدیدی ارسال فرمایید."
        )
        return

    # 4. Prepare caption and filename
    filename = f"nano_banana_hd_{int(time.time())}.png"
    clean_prompt = (prompt or "").strip()
    caption = "📁 <b>فایل با کیفیت اصلی و بدون فشرده‌سازی تلگرام</b>"
    if clean_prompt:
        safe_p = html.escape(clean_prompt[:350])
        caption += f"\n📝 <b>پرامپت:</b> {safe_p}"

    # 5. Deliver document reliably with multi-stage fallbacks
    sent = False
    try:
        doc_file = BufferedInputFile(img_bytes, filename=filename)
        await call.bot.send_document(
            chat_id=chat_id,
            document=doc_file,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
        sent = True
    except Exception as e1:
        logger.warning(f"Failed sending doc with HTML caption: {e1}")

    if not sent:
        try:
            doc_file = BufferedInputFile(img_bytes, filename=filename)
            await call.bot.send_document(
                chat_id=chat_id,
                document=doc_file,
                caption="📁 فایل با کیفیت اصلی و بدون فشرده‌سازی تلگرام",
                parse_mode=None
            )
            sent = True
        except Exception as e2:
            logger.warning(f"Failed sending doc with plain caption: {e2}")

    if not sent:
        try:
            doc_file = BufferedInputFile(img_bytes, filename=filename)
            await call.bot.send_document(
                chat_id=chat_id,
                document=doc_file
            )
            sent = True
        except Exception as e3:
            logger.error(f"Fatal error sending document: {e3}")
            await call.bot.send_message(
                chat_id=chat_id,
                text="⚠️ متاسفانه در ارسال فایل به تلگرام خطایی رخ داد. لطفاً چند لحظه بعد مجدداً امتحان فرمایید."
            )


# =====================================================================
# 5. Studio Photo & Document Interception (No LLM in Studio)
# =====================================================================

async def image_studio_photo_filter(message: Message) -> bool:
    if not message.photo or not message.from_user:
        return False
    return await is_image_studio_active(message.from_user.id)


@router.message(image_studio_photo_filter)
async def handle_image_studio_photo(message: Message, state: FSMContext):
    """
    Directly receives photos in Image Studio mode for editing.
    No LLM vision analysis is ever called.
    """
    photo = message.photo[-1]
    user_id = message.from_user.id

    detected_ratio = detect_aspect_ratio(photo.width, photo.height)
    await update_user_settings(state, user_id, ratio=detected_ratio)
    await db.update_user_video_settings(user_id, ratio=detected_ratio)

    file_io = io.BytesIO()
    await message.bot.download(photo.file_id, destination=file_io)
    photo_bytes = file_io.getvalue()

    ratio, size = await get_user_settings(state, user_id)
    caption = (message.caption or "").strip()

    if caption:
        from app.services.prompt_enhancer import clean_command_prefixes
        clean_instruction = clean_command_prefixes(caption)
        await execute_image_edit(message, photo_bytes, clean_instruction, ratio, size, state)
    else:
        await state.update_data(edit_image_bytes=photo_bytes, edit_ratio=detected_ratio)
        await state.set_state(GPTImageStates.waiting_for_edit_prompt)
        await message.answer(
            f"🖌️ **تصویر شما دریافت شد!**\n\n"
            f"📐 **نسبت ابعاد عکس:** `{detected_ratio}` (تنظیم خودکار ✅)\n\n"
            "لطفاً بنویسید چه تغییری می‌خواهید در این تصویر اعمال شود؟\n"
            "(مثال: «لباس را به رنگ قرمز درآور»، «پس‌زمینه را به ساحل تبدیل کن»)"
        )


async def image_studio_doc_filter(message: Message) -> bool:
    if not message.document or not message.from_user:
        return False
    return await is_image_studio_active(message.from_user.id)


@router.message(image_studio_doc_filter)
async def handle_image_studio_doc(message: Message, state: FSMContext):
    """
    Handles documents sent in Image Studio mode.
    If image document -> edits photo.
    If non-image document -> informs user that LLM file analysis requires 'New Chat'.
    """
    doc = message.document
    file_name = doc.file_name or ""
    mime_type = (doc.mime_type or "").lower()
    ext = file_name.split(".")[-1].lower() if "." in file_name else ""
    user_id = message.from_user.id

    # If image sent as document
    if ext in ["jpg", "jpeg", "png", "webp"] or mime_type.startswith("image/"):
        file_io = io.BytesIO()
        await message.bot.download(doc.file_id, destination=file_io)
        photo_bytes = file_io.getvalue()
        ratio, size = await get_user_settings(state, user_id)
        caption = (message.caption or "").strip()
        if caption:
            from app.services.prompt_enhancer import clean_command_prefixes
            clean_instruction = clean_command_prefixes(caption)
            await execute_image_edit(message, photo_bytes, clean_instruction, ratio, size, state)
        else:
            await state.update_data(edit_image_bytes=photo_bytes)
            await state.set_state(GPTImageStates.waiting_for_edit_prompt)
            await message.answer(
                "🖌️ **تصویر سند دریافت شد!**\n\n"
                "لطفاً بنویسید چه تغییری می‌خواهید در این تصویر اعمال شود؟"
            )
        return

    # Non-image documents in studio mode
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 گفتگوی جدید (ورود به چت هوش مصنوعی)", callback_data="action:clear_chat")]
    ])
    await message.reply(
        "⚠️ **شما هم‌اکنون در استودیوی ادیت عکس نانو بنانا هستید.**\n\n"
        "در این بخش هیچ مدل متنی یا LLM فعال نیست و فقط پرامپت تولید و ادیت عکس دریافت می‌شود.\n\n"
        "💬 برای **چت کردن با هوش مصنوعی** و **فرستادن فایل و عکس برای آنالیز و تحلیل**، باید حتماً وارد گزینه **«💬 گفتگوی جدید»** شوید.",
        reply_markup=markup,
        parse_mode="Markdown"
    )


def has_edit_caption(message: Message) -> bool:
    """Checks if photo caption contains image editing intent."""
    caption = (message.caption or "").lower()
    edit_keywords = ["ادیت", "ویرایش", "تغییر", "عوض کن", "edit", "change", "transform"]
    return any(kw in caption for kw in edit_keywords)


@router.message(F.photo, has_edit_caption)
async def handle_photo_with_edit_caption(message: Message, state: FSMContext):
    """
    If a user sends any photo with a caption containing edit keywords while in chat mode,
    we route to Agnes Image editing directly!
    """
    user_id = message.from_user.id
    await db.update_user_model(user_id, "agnes-image-2.5-flash")

    caption = (message.caption or "").strip()
    from app.services.prompt_enhancer import clean_command_prefixes
    instruction = clean_command_prefixes(caption)

    photo = message.photo[-1]
    detected_ratio = detect_aspect_ratio(photo.width, photo.height)
    await update_user_settings(state, user_id, ratio=detected_ratio)
    await db.update_user_video_settings(user_id, ratio=detected_ratio)

    file_io = io.BytesIO()
    await message.bot.download(photo.file_id, destination=file_io)
    photo_bytes = file_io.getvalue()

    ratio, size = await get_user_settings(state, user_id)
    await execute_image_edit(message, photo_bytes, instruction, ratio, size, state)
