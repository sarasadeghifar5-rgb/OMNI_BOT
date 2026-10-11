import re
import html
import time
import logging
from typing import Dict, Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext

from app.bot.database import BotDatabase
from app.bot.utils import safe_reply
from app.bot.keyboards import get_persistent_reply_keyboard, get_stars_payment_keyboard
from app.bot.config import ADMIN_IDS, MAIN_ADMIN_ID, SECOND_ADMIN_ID
from app.config import get_model_capabilities

logger = logging.getLogger("AccountHandler")
router = Router(name="account_router")
db = BotDatabase.get_instance()

STAR_PLANS = {
    "vip_1d": {
        "title": "⭐ تست ۱ روزه VIP هوش مصنوعی",
        "description": "دسترسی ۲۴ ساعته به تمامی مدل‌های اختصاصی از جمله Claude Opus 5.5، Fable 5.1، GPT-5.6 Sol و...",
        "stars": 25,
        "days": 1,
    },
    "vip_30d": {
        "title": "🌟 اشتراک ۳۰ روزه طلایی VIP",
        "description": "دسترسی نامحدود ۳۰ روزه به تمام مدل‌های پرچمدار و اختصاصی با بالاترین اولویت پردازش سرور",
        "stars": 120,
        "days": 30,
    },
    "vip_life": {
        "title": "👑 اشتراک مادام‌العمر الماس VIP",
        "description": "دسترسی نامحدود دائمی و مادام‌العمر به تمامی مدل‌های فعلی و آینده بدون نیاز به تمدید",
        "stars": 390,
        "days": -1,
    },
}

REGION_INFO = {
    "de": {"name": "آلمان (فرانکفورت)", "flag": "🇩🇪", "ping": "32ms"},
    "fi": {"name": "فنلاند (هلسینکی)", "flag": "🇫🇮", "ping": "40ms"},
    "us": {"name": "آمریکا (اورگان)", "flag": "🇺🇸", "ping": "88ms"},
    "nl": {"name": "هلند (آمستردام)", "flag": "🇳🇱", "ping": "36ms"},
    "ir": {"name": "ایران (مستقیم)", "flag": "🇮🇷", "ping": "18ms"},
}

def get_region_keyboard(current_code: str = "de") -> InlineKeyboardMarkup:
    buttons = []
    for code, info in REGION_INFO.items():
        mark = "✅ " if code == current_code else ""
        text = f"{mark}{info['flag']} {info['name']} (پینگ {info['ping']})"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"set_region:{code}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به حساب کاربری", callback_data="act:profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =====================================================================
# 1. حساب کاربری 👤
# =====================================================================

def _format_vip_status(user_id: int, is_vip: bool, vip_until: float) -> str:
    if user_id == MAIN_ADMIN_ID:
        return "👑 مدیر اصلی · دسترسی نامحدود"
    if user_id == SECOND_ADMIN_ID:
        return "🛡️ ادمین ربات · دسترسی نامحدود"
    if user_id in ADMIN_IDS:
        return "👑 مدیر ارشد · دسترسی نامحدود"
    if is_vip and vip_until == -1:
        return "💎 الماس VIP · مادام‌العمر"
    if is_vip and vip_until > time.time():
        rem_days = int((vip_until - time.time()) // 86400) + 1
        return f"🌟 طلایی VIP · {rem_days} روز باقی‌مانده"
    return "⚪ کاربر عادی · پلن پایه"


def get_clean_model_display_name(model_id: str) -> str:
    if not model_id or model_id == "gemini":
        return "Gemini 3.7 Flash"
    caps = get_model_capabilities(model_id)
    raw_name = caps.get("name", model_id)
    clean = re.sub(r'[\u2600-\u27bf\U0001f300-\U0001f9ff⚡💎🌟🚀👑🍌🎬🧠🆓💡]+', '', raw_name).strip()
    return clean or raw_name


def render_account_dashboard(user: Dict[str, Any], user_id: int, username_raw: str = None) -> tuple[str, InlineKeyboardMarkup]:
    username = f"@{username_raw}" if username_raw else "ندارد"
    selected_model = user.get("selected_model", "gemini")
    model_name = get_clean_model_display_name(selected_model)
    credits = user.get("credits", 50)
    stars_balance = user.get("stars_balance", 0)
    invited = user.get("invited_count", 0)
    total_msgs = user.get("total_messages", 0)
    is_vip = bool(user.get("is_vip", 0))
    vip_until = float(user.get("vip_until", 0) or 0)
    vip_status = _format_vip_status(user_id, is_vip, vip_until)

    text = (
        "👤 <b>پروفایل و داشبورد شما</b>\n\n"
        f"🆔 <b>شناسه کاربری:</b> <code>{user_id}</code>\n"
        f"🏷 <b>نام کاربری:</b> {html.escape(username)}\n\n"
        f"💎 <b>اشتراک:</b> {html.escape(vip_status)}\n"
        f"🤖 <b>مدل فعال:</b> <b>{html.escape(model_name)}</b>\n\n"
        f"⭐ <b>استارها:</b> <code>{stars_balance} XTR</code>\n"
        f"🎁 <b>اعتبار هدیه:</b> <code>{credits} توکن</code>\n"
        f"👥 <b>دعوت‌شده‌ها:</b> <code>{invited} نفر</code>\n"
        f"💬 <b>تعداد پیام‌ها:</b> <code>{total_msgs}</code>\n\n"
        "⚙️ <i>از گزینه‌های زیر برای ارتقای حساب، دریافت هدیه و مدیریت تنظیمات استفاده کنید.</i>"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ خرید اشتراک (استار تلگرام)", callback_data="act:buy_service"),
            InlineKeyboardButton(text="🎁 دریافت هدیه روزانه", callback_data="act:daily_gift"),
        ],
        [
            InlineKeyboardButton(text="🔗 لینک دعوت من", callback_data="act:my_invite"),
            InlineKeyboardButton(text="🤖 تغییر مدل هوش مصنوعی", callback_data="menu:models"),
        ],
        [
            InlineKeyboardButton(text="🔄 بروزرسانی اطلاعات", callback_data="act:profile"),
        ]
    ])

    return text, markup


@router.message(Command("account", "profile"))
@router.message(F.text.in_({"👤 حساب کاربری", "حساب کاربری 👤", "حساب کاربری", "پروفایل"}))
async def cmd_user_account(message: Message, state: FSMContext = None):
    """Displays comprehensive and elegant user account dashboard."""
    if state:
        await state.clear()
    user = await db.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    text, markup = render_account_dashboard(user, message.from_user.id, message.from_user.username)
    await safe_reply(message, text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "act:profile")
async def cb_user_account(call: CallbackQuery):
    user = await db.get_or_create_user(
        user_id=call.from_user.id,
        username=call.from_user.username,
        first_name=call.from_user.first_name
    )

    text, markup = render_account_dashboard(user, call.from_user.id, call.from_user.username)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass
    await call.answer("داشبورد حساب کاربری به‌روز شد ✅")


# =====================================================================
# 2. خرید سرویس با استار تلگرام (Telegram Stars XTR) 🛒
# =====================================================================

@router.message(Command("buy", "shop", "plans", "stars"))
@router.message(F.text.in_({"🛒 خرید سرویس", "خرید سرویس 🛒", "خرید سرویس", "خرید اشتراک", "استار تلگرام", "خرید استار"}))
async def cmd_buy_service(message: Message, state: FSMContext = None):
    if state:
        await state.clear()
    text = (
        "🛒 **فروشگاه اشتراک‌های VIP و پرچمدار هوش مصنوعی (با استار تلگرام)**\n\n"
        "⭐ با استار تلگرام (Telegram Stars) به راحتی و با یک کلیک قفل برترین مدل‌های جهان را باز کنید:\n\n"
        "💎 **مدل‌های اختصاصی پلن VIP:**\n"
        "• **Claude Fable 5.1 & Fable 5 🌟** (استدلال و خلاقیت بی‌نظیر)\n"
        "• **Claude Opus 5.5 & Opus 5 💎** (پرچمدار اول جهان در مهندسی و حل مسئله)\n"
        "• **GPT-5.6 Sol ☀️ & GPT-5.5 Pro 🚀** (غول‌های نسل جدید OpenAI)\n"
        "• **DeepSeek V4 Pro Max 🧠** (استدلال عمیق ریاضی و کدنویسی)\n"
        "• استودیو نامحدود ادیت عکس و ساخت ویدیو نانو بنانا 🍌\n"
        "• اولویت پردازش حداکثری و بدون صف انتظار\n\n"
        "👇 **یکی از بسته‌های زیر را با استار تلگرام انتخاب فرمایید:**"
    )

    markup = get_stars_payment_keyboard()
    await safe_reply(message, text, reply_markup=markup)


@router.callback_query(F.data == "act:buy_service")
async def cb_buy_service(call: CallbackQuery):
    await cmd_buy_service(call.message)
    await call.answer()


@router.callback_query(F.data.startswith("buy_stars:"))
async def cb_buy_stars_invoice(call: CallbackQuery):
    """Sends native Telegram Stars invoice for the chosen package."""
    plan_key = call.data.split("buy_stars:")[1]
    plan = STAR_PLANS.get(plan_key)
    if not plan:
        await call.answer("⚠️ پلن مورد نظر یافت نشد.", show_alert=True)
        return

    try:
        await call.bot.send_invoice(
            chat_id=call.message.chat.id,
            title=plan["title"],
            description=plan["description"],
            payload=plan_key,
            currency="XTR",
            prices=[LabeledPrice(label=plan["title"][:30], amount=plan["stars"])],
            provider_token=""  # Native Telegram Stars requires empty provider_token
        )
        await call.answer("⭐ فاکتور پرداخت استار تلگرام ارسال شد.")
    except Exception as e:
        logger.error(f"Error sending Stars invoice: {e}")
        await call.answer("⚠️ خطا در ایجاد فاکتور استار. لطفاً بعداً تلاش فرمایید.", show_alert=True)


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Approve checkout immediately for Telegram Stars."""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Fulfill order upon successful Telegram Stars payment."""
    payment = message.successful_payment
    payload = payment.invoice_payload
    charge_id = payment.telegram_payment_charge_id
    stars_amount = payment.total_amount
    user_id = message.from_user.id

    plan = STAR_PLANS.get(payload, {"days": 30, "title": "اشتراک VIP"})
    days = plan["days"]

    # Record in database & activate VIP
    await db.record_star_transaction(user_id=user_id, charge_id=charge_id, payload=payload, stars=stars_amount)
    new_until = await db.set_user_vip(user_id=user_id, days=days)

    until_str = "دائمی (مادام‌العمر)" if days == -1 else f"{days} روز آینده"

    success_text = (
        "🎉 **تبریک! پرداخت استار تلگرام شما با موفقیت انجام شد!** ⭐\n\n"
        f"✨ **پلن فعال‌شده:** `{plan['title']}`\n"
        f"⏳ **اعتبار اشتراک:** `{until_str}`\n"
        f"💰 **مبلغ پرداختی:** `{stars_amount} Telegram Stars`\n\n"
        "🚀 **قفل تمامی مدل‌های فوق‌پیشرفته برای شما باز شد:**\n"
        "• Claude Opus 5.5 & Opus 5 💎\n"
        "• Claude Fable 5.1 & Fable 5 🌟\n"
        "• GPT-5.6 Sol & GPT-5.5 Pro 🚀\n"
        "• DeepSeek V4 Pro Max 🧠\n\n"
        "جهت انتخاب مدل، روی دکمه زیر کلیک فرمایید:"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 انتخاب مدل هوش مصنوعی", callback_data="menu:models")],
        [InlineKeyboardButton(text="💬 گفتگوی جدید", callback_data="action:clear_chat")]
    ])

    await message.answer(success_text, reply_markup=markup, parse_mode="Markdown")

    # Alert bot administrators
    for admin_id in ADMIN_IDS:
        try:
            uname = f"@{message.from_user.username}" if message.from_user.username else f"ID: {user_id}"
            await message.bot.send_message(
                chat_id=admin_id,
                text=(
                    "💰 **دریافت استار جدید تلگرام!** ⭐\n\n"
                    f"👤 **کاربر:** {uname} (`{user_id}`)\n"
                    f"📦 **پلن:** {plan['title']}\n"
                    f"⭐ **تعداد استار:** {stars_amount} XTR\n"
                    f"🔖 **شناسه پرداخت:** `{charge_id}`"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("req_star:"))
async def cb_req_star_paywall(call: CallbackQuery):
    """Pops up paywall prompt when trying to select a Star-exclusive model."""
    model_id = call.data.split("req_star:")[1]
    text = (
        f"🔒 **مدل پرچمدار و اختصاصی VIP:** `{model_id}`\n\n"
        "این مدل یکی از باهوش‌ترین و قدرتمندترین هوش‌های مصنوعی نسل جدید در **CodeCraft API** است و نیازمند اشتراک ویژه می‌باشد.\n\n"
        "⭐ با خرید اشتراک استار تلگرام فوراً به این مدل و تمام مدل‌های برتر (Claude Opus 5.5, Fable 5.1, GPT-5.6 Sol) دسترسی پیدا خواهید کرد:\n\n"
        "پلن مورد نظر خود را انتخاب نمایید:"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ تست ۱ روزه VIP (۲۵ استار)", callback_data="buy_stars:vip_1d"),
        ],
        [
            InlineKeyboardButton(text="🌟 اشتراک ۳۰ روزه طلایی (۱۲۰ استار)", callback_data="buy_stars:vip_30d"),
        ],
        [
            InlineKeyboardButton(text="👑 اشتراک مادام‌العمر الماس (۳۹۰ استار)", callback_data="buy_stars:vip_life"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به دسته‌بندی مدل‌ها", callback_data="menu:models"),
        ]
    ])
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()



# =====================================================================
# 3. سرویس هدیه 🎁
# =====================================================================

@router.message(Command("gift"))
@router.message(F.text.in_({"🎁 سرویس هدیه", "سرویس هدیه 🎁", "سرویس هدیه", "هدیه", "هدیه روزانه"}))
async def cmd_gift_service(message: Message, state: FSMContext = None):
    if state:
        await state.clear()
    user_id = message.from_user.id
    success, amount, remaining = await db.claim_daily_gift(user_id)
    user = await db.get_or_create_user(user_id)
    new_credits = user.get("credits", 50)
    invited_count = user.get("invited_count", 0)
    total_earned = invited_count * 50

    bot_info = await message.bot.get_me()
    invite_url = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    share_url = f"https://t.me/share/url?url={invite_url}&text=سلام! این ربات فوق‌العاده هوش مصنوعی با قابلیت ساخت ویدیو، ادیت عکس نانو بنانا، استدلال عمیق و چت نامحدود رو امتحان کن:"

    if success:
        gift_banner = (
            "🎉 **تبریک! هدیه روزانه شما فعال شد!** 🎁\n\n"
            f"✨ شما مقدار **{amount} توکن هدیه** دریافت نمودید.\n"
            f"💰 موجودی کل فعلی شما: `{new_credits} توکن`\n"
            "⏳ هدیه بعدی شما ۲۴ ساعت دیگر فعال خواهد شد.\n"
        )
    else:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        gift_banner = (
            "🎁 **وضعیت سرویس هدیه روزانه:**\n\n"
            "شما امروز هدیه روزانه خود را دریافت کرده‌اید.\n"
            f"⏳ زمان باقی‌مانده تا دریافت هدیه بعدی: **{hours} ساعت و {minutes} دقیقه**\n"
            f"💰 موجودی کل فعلی شما: `{new_credits} توکن`\n"
        )

    invite_section = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 **لینک دعوت و پاداش رفرال:**\n"
        "با دعوت از هر دوست به ربات، **۵۰ توکن هدیه** به شما و **۵۰ توکن** به دوستتان تعلق می‌گیرد!\n\n"
        f"👥 دوستان دعوت‌شده توسط شما: `{invited_count} نفر`\n"
        f"🎁 مجموع پاداش کسب‌شده: `{total_earned} توکن`\n\n"
        "👇 **لینک اختصاصی دعوت شما (لمس کنید تا کپی شود):**\n"
        f"`{invite_url}`"
    )

    full_text = f"{gift_banner}\n{invite_section}"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 اشتراک‌گذاری لینک دعوت در تلگرام", url=share_url)],
        [InlineKeyboardButton(text="🔄 بروزرسانی وضعیت هدیه", callback_data="act:daily_gift")],
        [InlineKeyboardButton(text="👤 بازگشت به حساب کاربری", callback_data="act:profile")]
    ])

    await safe_reply(message, full_text, reply_markup=markup)


@router.callback_query(F.data == "act:daily_gift")
async def cb_daily_gift(call: CallbackQuery):
    await cmd_gift_service(call.message)
    await call.answer()


# =====================================================================
# 4. لینک دعوت 🔗
# =====================================================================

@router.message(Command("invite", "referral"))
@router.message(F.text.in_({"🔗 لینک دعوت", "لینک دعوت 🔗", "لینک دعوت", "دعوت دوستان"}))
async def cmd_invite_link(message: Message, state: FSMContext = None):
    if state:
        await state.clear()
    bot_info = await message.bot.get_me()
    user_id = message.from_user.id
    invite_url = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    user = await db.get_or_create_user(user_id)
    invited_count = user.get("invited_count", 0)
    total_earned = invited_count * 50

    text = (
        "🔗 **سیستم دعوت از دوستان و دریافت پاداش**\n\n"
        "با معرفی این ربات به دوستان خود، هم شما و هم دوستتان پاداش اعتبار رایگان دریافت کنید!\n\n"
        "🎁 **طرح پاداش دعوت:**\n"
        "• به ازای هر فرد جدیدی که با لینک شما وارد ربات شود:\n"
        "  ➕ **۵۰ توکن هدیه** به شما تعلق می‌گیرد.\n"
        "  ➕ **۵۰ توکن هدیه** به دوست شما تعلق می‌گیرد.\n\n"
        "📊 **وضعیت دعوت‌های شما:**\n"
        f"👥 تعداد دوستان دعوت‌شده: `{invited_count} نفر`\n"
        f"💰 مجموع توکن‌های دریافتی: `{total_earned} توکن`\n\n"
        "👇 **لینک اختصاصی شما (کپی کنید و بفرستید):**\n"
        f"`{invite_url}`"
    )

    share_text = f"سلام! این ربات فوق‌العاده هوش مصنوعی با قابلیت ساخت ویدیو، ادیت عکس نانو بنانا، استدلال عمیق و چت نامحدود رو امتحان کن:\n{invite_url}"
    share_url = f"https://t.me/share/url?url={invite_url}&text=سلام! این ربات فوق‌العاده هوش مصنوعی رو امتحان کن:"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 ارسال مستقیم به دوستان در تلگرام", url=share_url)],
        [InlineKeyboardButton(text="🎁 ورود به سرویس هدیه", callback_data="act:daily_gift")],
        [InlineKeyboardButton(text="👤 بازگشت به حساب کاربری", callback_data="act:profile")]
    ])

    # If triggered by old keyboard button, also refresh the persistent keyboard
    if message.text in {"🔗 لینک دعوت", "لینک دعوت 🔗", "لینک دعوت"}:
        await message.answer("🔄 پنل دسترسی سریع به‌روزرسانی شد.", reply_markup=get_persistent_reply_keyboard())

    await safe_reply(message, text, reply_markup=markup)


@router.callback_query(F.data == "act:my_invite")
async def cb_my_invite(call: CallbackQuery):
    await cmd_invite_link(call.message)
    await call.answer()


# =====================================================================
# 5. تغییر منطقه 🌐
# =====================================================================

@router.message(Command("region"))
@router.message(F.text.in_({"🌐 تغییر منطقه", "تغییر منطقه 🌐", "تغییر منطقه", "منطقه"}))
async def cmd_change_region(message: Message, state: FSMContext = None):
    if state:
        await state.clear()
    user = await db.get_or_create_user(message.from_user.id)
    current_code = user.get("region", "de")
    reg = REGION_INFO.get(current_code, REGION_INFO["de"])

    text = (
        "🌐 **تنظیمات منطقه و سرور پردازش هوش مصنوعی**\n\n"
        f"📍 منطقه فعلی سرور شما: {reg['flag']} **{reg['name']}** (پینگ: `{reg['ping']}`)\n\n"
        "با انتخاب نزدیک‌ترین سرور، تاخیر ارتباطی به حداقل رسیده و پاسخ‌ها با حداکثر سرعت رندر می‌شوند:\n"
        "👇 سرور مورد نظر خود را انتخاب نمایید:"
    )

    if message.text in {"تغییر منطقه 🌐", "تغییر منطقه"}:
        await message.answer("🔄 پنل دسترسی سریع به‌روزرسانی شد.", reply_markup=get_persistent_reply_keyboard())

    await safe_reply(message, text, reply_markup=get_region_keyboard(current_code))


@router.callback_query(F.data == "act:change_region")
async def cb_change_region(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    current_code = user.get("region", "de")
    reg = REGION_INFO.get(current_code, REGION_INFO["de"])

    text = (
        "🌐 **تنظیمات منطقه و سرور پردازش هوش مصنوعی**\n\n"
        f"📍 منطقه فعلی سرور شما: {reg['flag']} **{reg['name']}** (پینگ: `{reg['ping']}`)\n\n"
        "با انتخاب نزدیک‌ترین سرور، تاخیر ارتباطی به حداقل رسیده و پاسخ‌ها با حداکثر سرعت رندر می‌شوند:\n"
        "👇 سرور مورد نظر خود را انتخاب نمایید:"
    )

    await call.message.edit_text(text, reply_markup=get_region_keyboard(current_code), parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data.startswith("set_region:"))
async def cb_set_region(call: CallbackQuery):
    code = call.data.split("set_region:")[1]
    if code in REGION_INFO:
        await db.update_user_region(call.from_user.id, code)
        reg = REGION_INFO[code]
        await call.answer(f"منطقه به {reg['name']} با پینگ {reg['ping']} تغییر یافت!", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=get_region_keyboard(code))
