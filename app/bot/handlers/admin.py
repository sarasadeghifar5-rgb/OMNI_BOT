import os
import time
import asyncio
import logging
import httpx
from typing import Dict, Any, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatMemberStatus

from app.bot.config import ADMIN_IDS, BASE_DIR, MAIN_ADMIN_ID, SECOND_ADMIN_ID
from app.bot.database import BotDatabase
from app.config import AVAILABLE_MODELS, STAR_LOCKED_MODELS
from app.bot.keyboards import (
    get_admin_main_keyboard,
    get_admin_channel_keyboard,
    get_admin_user_keyboard,
    get_admin_key_pools_keyboard,
    get_main_menu_keyboard
)
from app.services.codecraft_client import CodeCraftKeyPool
from app.services.atria_client import AtriaKeyPool
from app.services.agnes_client import AgnesKeyPool

logger = logging.getLogger("AdminHandler")
router = Router(name="admin_router")
db = BotDatabase.get_instance()

class AdminStates(StatesGroup):
    waiting_channel_id = State()
    waiting_channel_link = State()
    waiting_user_search = State()
    waiting_broadcast_msg = State()
    waiting_codecraft_key = State()
    waiting_add_key_codecraft = State()
    waiting_add_key_atria = State()
    waiting_add_key_agnes = State()

def is_admin(user_id: int) -> bool:
    if not ADMIN_IDS:
        return True  # If no admin IDs set, permit for initial setup
    return user_id in ADMIN_IDS or user_id in (MAIN_ADMIN_ID, SECOND_ADMIN_ID)

def normalize_chat_id(ch: Any) -> Any:
    s = str(ch).strip()
    if (s.startswith("-") and s[1:].isdigit()) or s.isdigit():
        return int(s)
    return s

def _format_time(ts: float) -> str:
    if not ts or ts <= 0:
        return "ندارد"
    if ts == -1:
        return "مادام‌العمر (دائمی)"
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


# =========================================================================
# 1. داشبورد اصلی پنل مدیریت ادمین
# =========================================================================

async def render_admin_dashboard(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    stats = await db.get_detailed_stats()
    lock_info = await db.get_channel_lock_info()

    cc_pool = CodeCraftKeyPool.get_instance().get_status()
    atr_pool = AtriaKeyPool.get_instance().get_status()
    agn_pool = AgnesKeyPool.get_instance().get_status()

    cc_status = f"🟢 {cc_pool['healthy']}/{cc_pool['total']} کلید فعال"
    atr_status = f"🟢 {atr_pool['healthy']}/{atr_pool['total']} کلید فعال"
    agn_status = f"🟢 {agn_pool['healthy']}/{agn_pool['total']} کلید فعال"

    ch_status = f"🟢 فعال ({lock_info['channel_id']})" if lock_info["enabled"] else "🔴 غیرفعال"
    main_admin_str = f"`{MAIN_ADMIN_ID}`"
    second_admin_str = f"`{SECOND_ADMIN_ID}`" if SECOND_ADMIN_ID else "تنظیم نشده"

    text = (
        "👑 **پنل مدیریت پیشرفته ربات هوش مصنوعی (OmniLLM Hub)**\n\n"
        f"👑 **مدیر اصلی:** {main_admin_str}\n"
        f"🛡️ **ادمین دوم:** {second_admin_str}\n\n"
        "📊 **خلاصه وضعیت آماری سرور (Real-Time):**\n"
        f"• 👥 **کل کاربران ثبت‌شده:** `{stats['total_users']:,}` نفر\n"
        f"• 🟢 **کاربران آنلاین (۱ ساعت اخیر):** `{stats['active_1h']:,}` نفر\n"
        f"• ⚡ **کاربران فعال امروز (۲۴ ساعت):** `{stats['active_today']:,}` نفر\n"
        f"• 📅 **کاربران فعال هفته (۷ روز):** `{stats['active_week']:,}` نفر\n"
        f"• 🆕 **عضویت‌های جدید امروز:** `{stats['new_today']:,}` نفر\n"
        f"• 🌟 **مشترکین ویژه (VIP):** `{stats['total_vips']:,}` نفر\n"
        f"• 💬 **کل پیام‌های پردازش‌شده:** `{stats['total_messages']:,}` پیام\n"
        f"• ⭐ **درآمد استار تلگرام:** `{stats['total_stars']:,} XTR`\n"
        f"• 🚫 **کاربران مسدود شده (Ban):** `{stats['total_banned']:,}` نفر\n\n"
        f"📢 **قفل جوین اجباری کانال:** {ch_status}\n\n"
        "🔐 **استخر کلیدهای فعال (Key Pools & Load Balancing):**\n"
        f"• 💎 **کدکرفت (CodeCraft API - ۳۳ مدل):** {cc_status}\n"
        f"• 🌅 **آتریا (Atria ASI - مدل استدلالی):** {atr_status}\n"
        f"• 🍌 **استودیو نانو (Agnes AI - عکس، ویدیو، متن):** {agn_status}\n\n"
        "👇 _برای مشاهده آمار فوق‌دقیق یا اعمال تنظیمات، از کلیدهای زیر استفاده فرمایید:_"
    )
    markup = get_admin_main_keyboard()
    return text, markup


@router.message(Command("admin", "panel"))
@router.message(F.text.in_({"پنل مدیریت ادمین 👑", "👑 پنل مدیریت ادمین", "پنل مدیریت ⚙️", "پنل مدیریت", "ادمین"}))
async def cmd_admin_panel(message: Message, state: FSMContext = None):
    if not is_admin(message.from_user.id):
        return
    if state:
        await state.clear()
    text, markup = await render_admin_dashboard(message.from_user.id)
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")


@router.callback_query(F.data == "admin:main")
async def cb_admin_main(call: CallbackQuery, state: FSMContext = None):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی غیرمجاز", show_alert=True)
        return
    if state:
        await state.clear()
    text, markup = await render_admin_dashboard(call.from_user.id)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "admin:cancel")
async def cb_admin_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("عملیات لغو شد.")
    text, markup = await render_admin_dashboard(call.from_user.id)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="Markdown")


# =========================================================================
# 1.1 آمار تفصیلی و فوق‌دقیق کاربران و سیستم (Real-time Analytics)
# =========================================================================

async def render_admin_stats_view(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    stats = await db.get_detailed_stats()

    tot_u = max(1, stats["total_users"])
    tot_m = stats["total_messages"]
    avg_msg = f"{tot_m / tot_u:.1f}" if tot_u > 0 else "0"

    models_str = ""
    if stats["top_models"]:
        for model_id, count in stats["top_models"]:
            pct = (count / tot_u) * 100
            models_str += f"  • `{model_id}`: **{count}** کاربر ({pct:.1f}%)\n"
    else:
        models_str = "  • هنوز داده‌ای ثبت نشده است.\n"

    top_users_str = ""
    if stats["top_users"]:
        for u in stats["top_users"]:
            uname = f"@{u.get('username')}" if u.get('username') else f"ID: `{u['user_id']}`"
            vip_mark = "🌟 VIP" if u.get("is_vip") else "⚪"
            top_users_str += f"  • {uname}: **{u.get('total_messages', 0):,}** پیام ({vip_mark})\n"
    else:
        top_users_str = "  • کاربری ثبت نشده است.\n"

    recent_users_str = ""
    if stats["recent_users"]:
        for u in stats["recent_users"]:
            uname = f"@{u.get('username')}" if u.get('username') else f"`{u['user_id']}`"
            c_time = _format_time(u.get("created_at", 0))
            recent_users_str += f"  • {uname} ({u.get('first_name', '') or 'بی‌نام'}) — _{c_time}_\n"
    else:
        recent_users_str = "  • کاربری ثبت نشده است.\n"

    text = (
        "📊 **گزارش آماری فوق‌دقیق و زنده ربات (Real-Time Analytics):**\n\n"
        "👥 **آمار دقیق کاربران:**\n"
        f"• 👥 **کل کاربران ثبت‌شده در ربات:** `{stats['total_users']:,}` نفر\n"
        f"• 🟢 **کاربران آنلاین (۱ ساعت گذشته):** `{stats['active_1h']:,}` نفر\n"
        f"• ⚡ **کاربران فعال روزانه (۲۴ ساعت - DAU):** `{stats['active_today']:,}` نفر\n"
        f"• 📅 **کاربران فعال هفتگی (۷ روز - WAU):** `{stats['active_week']:,}` نفر\n"
        f"• 🗓️ **کاربران فعال ماهانه (۳۰ روز - MAU):** `{stats['active_month']:,}` نفر\n\n"
        "📈 **روند جذب کاربران جدید:**\n"
        f"• 🆕 **عضویت‌های ۲۴ ساعت گذشته:** `{stats['new_today']:,}` کاربر جدید\n"
        f"• 📈 **عضویت‌های ۷ روز گذشته:** `{stats['new_week']:,}` کاربر جدید\n"
        f"• 📊 **عضویت‌های ۳۰ روز گذشته:** `{stats['new_month']:,}` کاربر جدید\n\n"
        "🌟 **آمار اشتراک ویژه (VIP) و مالی:**\n"
        f"• 👑 **کل مشترکین فعال VIP:** `{stats['total_vips']:,}` نفر\n"
        f"  ├ مادام‌العمر (دائمی): `{stats['lifetime_vips']:,}` نفر\n"
        f"  └ مدت‌دار (فعال): `{stats['temporary_vips']:,}` نفر\n"
        f"• ⭐ **کل درآمد استار تلگرام:** `{stats['total_stars']:,} XTR`\n"
        f"• 🧾 **تعداد کل تراکنش‌های موفق:** `{stats['total_transactions']:,}` تراکنش\n"
        f"• 🚫 **کاربران مسدود شده (Ban):** `{stats['total_banned']:,}` نفر\n\n"
        "💬 **آمار ترافیک و پیام‌ها:**\n"
        f"• 💬 **کل پیام‌های پردازش‌شده:** `{stats['total_messages']:,}` پیام\n"
        f"• ⚡ **پیام‌های ارسال‌شده در ۲۴ ساعت گذشته:** `{stats['messages_24h']:,}` پیام\n"
        f"• 📊 **میانگین پیام به ازای هر کاربر:** `{avg_msg}` پیام\n\n"
        "🤖 **محبوب‌ترین مدل‌های مورد استفاده کاربران:**\n"
        f"{models_str}\n"
        "🏆 **فعال‌ترین کاربران ربات:**\n"
        f"{top_users_str}\n"
        "🆕 **آخرین کاربران پیوسته به ربات:**\n"
        f"{recent_users_str}\n"
        "⏱️ _آمار فوق مستقیماً از جداول سرور به صورت بلادرنگ و با دقت ۱۰۰٪ استخراج شده است._"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 بروزرسانی زنده آمار", callback_data="admin:stats"),
            InlineKeyboardButton(text="📋 خروجی لیست کل کاربران", callback_data="admin:export_users"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به پنل ادمین", callback_data="admin:main")
        ]
    ])
    return text, markup


@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(call: CallbackQuery, state: FSMContext = None):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی غیرمجاز", show_alert=True)
        return
    if state:
        await state.clear()
    text, markup = await render_admin_stats_view(call.from_user.id)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer("📊 آمار با موفقیت بروزرسانی شد.")


@router.callback_query(F.data == "admin:export_users")
async def cb_admin_export_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("دسترسی غیرمجاز", show_alert=True)
        return
    await call.answer("در حال استخراج لیست کل کاربران...")
    users = await db.get_all_users_export(limit=1000)

    lines = [
        "=" * 75,
        "📋 گزارش رسمی و جامع کاربران ربات هوش مصنوعی (OmniLLM Hub)",
        f"تاریخ گزارش: {_format_time(time.time())}",
        f"تعداد کل کاربران موجود در خروجی: {len(users)} نفر",
        "=" * 75,
        ""
    ]
    for idx, u in enumerate(users, 1):
        uname = f"@{u['username']}" if u.get('username') else "بدون یوزرنیم"
        fname = u.get('first_name', '') or 'بی‌نام'
        vip_status = "VIP Lifetime" if u.get('vip_until') == -1 else ("VIP Active" if u.get('is_vip') else "Regular")
        reg_time = _format_time(u.get('created_at', 0))
        act_time = _format_time(u.get('last_active', 0))
        lines.append(
            f"#{idx} | UserID: {u['user_id']} | User: {uname} ({fname}) | Model: {u.get('selected_model')} | "
            f"Msgs: {u.get('total_messages', 0)} | Credits: {u.get('credits', 0)} | Stars: {u.get('stars_balance', 0)} XTR | "
            f"Status: {vip_status} | Joined: {reg_time} | LastActive: {act_time}"
        )

    report_text = "\n".join(lines)
    file_bytes = report_text.encode("utf-8")
    doc = BufferedInputFile(file_bytes, filename=f"users_export_{int(time.time())}.txt")

    await call.message.answer_document(
        document=doc,
        caption=f"📁 **خروجی مشخصات `{len(users)}` کاربر ربات تلگرام**\nشامل شناسه‌های عددی، نام‌های کاربری، پیام‌ها و وضعیت VIP.",
        parse_mode="Markdown"
    )


# =========================================================================
# 2. مدیریت قفل اجباری عضویت در کانال (Force-Join Channel)
# =========================================================================

@router.callback_query(F.data == "admin:channel")
async def cb_admin_channel(call: CallbackQuery, state: FSMContext = None):
    if not is_admin(call.from_user.id):
        return
    if state:
        await state.clear()

    lock_info = await db.get_channel_lock_info()
    enabled = lock_info["enabled"]
    ch_id = lock_info["channel_id"] or "تنظیم نشده"
    ch_link = lock_info["channel_link"] or "تنظیم نشده"

    status_str = "🟢 **روشن (فعال)** - کاربران قبل از استفاده باید عضو شوند" if enabled else "🔴 **خاموش (غیرفعال)**"

    text = (
        "📢 **مدیریت قفل عضویت اجباری در کانال (Force-Join Lock)**\n\n"
        f"• **وضعیت فعلی:** {status_str}\n"
        f"• **آیدی کانال:** `{ch_id}`\n"
        f"• **لینک جوین کانال:** `{ch_link}`\n\n"
        "💡 **نکات مهم:**\n"
        "۱. ربات باید حتماً در کانال شما **ادمین** باشد تا بتواند عضویت کاربران را بررسی کند.\n"
        "۲. می‌توانید آیدی پابلیک مثل `@MyChannel` یا آیدی عددی مثل `-1001234567890` وارد نمایید."
    )
    markup = get_admin_channel_keyboard(enabled=enabled, channel_id=ch_id, channel_link=ch_link)
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "admin:toggle_channel")
async def cb_toggle_channel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    is_enabled = await db.is_channel_lock_enabled()
    new_val = "0" if is_enabled else "1"
    await db.set_setting("channel_lock_enabled", new_val)

    alert_txt = "قفل کانال خاموش شد 🔴" if new_val == "0" else "قفل کانال روشن و فعال شد 🟢"
    try:
        await call.answer(alert_txt, show_alert=True)
    except Exception:
        pass

    lock_info = await db.get_channel_lock_info()
    enabled = lock_info["enabled"]
    ch_id = lock_info["channel_id"] or "تنظیم نشده"
    ch_link = lock_info["channel_link"] or "تنظیم نشده"

    status_str = "🟢 **روشن (فعال)** - کاربران قبل از استفاده باید عضو شوند" if enabled else "🔴 **خاموش (غیرفعال)**"

    text = (
        "📢 **مدیریت قفل عضویت اجباری در کانال (Force-Join Lock)**\n\n"
        f"• **وضعیت فعلی:** {status_str}\n"
        f"• **آیدی کانال:** `{ch_id}`\n"
        f"• **لینک جوین کانال:** `{ch_link}`\n\n"
        "💡 **نکات مهم:**\n"
        "۱. ربات باید حتماً در کانال شما **ادمین** باشد تا بتواند عضویت کاربران را بررسی کند.\n"
        "۲. می‌توانید آیدی پابلیک مثل `@MyChannel` یا آیدی عددی مثل `-1001234567890` وارد نمایید."
    )
    markup = get_admin_channel_keyboard(enabled=enabled, channel_id=ch_id, channel_link=ch_link)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass


@router.callback_query(F.data == "admin:set_channel_id")
async def cb_set_channel_id(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_channel_id)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="admin:channel")]
    ])
    await call.message.edit_text(
        "✏️ **تنظیم آیدی کانال:**\n\n"
        "لطفاً آیدی یا یوزرنیم کانال مورد نظر را ارسال فرمایید:\n"
        "• برای کانال عمومی: `@ChannelUsername`\n"
        "• برای کانال خصوصی: `-1001234567890` (شناسه عددی)\n\n"
        "جهت انصراف می‌توانید روی دکمه زیر کلیک کنید یا عبارت /cancel را بفرستید.",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await call.answer()


@router.message(AdminStates.waiting_channel_id)
async def state_save_channel_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    ch_id = message.text.strip()
    if ch_id.lower() == "/cancel":
        await state.clear()
        text, markup = await render_admin_dashboard(message.from_user.id)
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
        return

    await db.set_setting("channel_lock_id", ch_id)
    # If no link set yet and it's a public @username, auto-set link
    if ch_id.startswith("@"):
        current_link = await db.get_setting("channel_lock_link", "")
        if not current_link:
            await db.set_setting("channel_lock_link", f"https://t.me/{ch_id.lstrip('@')}")

    await state.clear()
    lock_info = await db.get_channel_lock_info()
    enabled = lock_info["enabled"]
    ch_id_val = lock_info["channel_id"] or "تنظیم نشده"
    ch_link_val = lock_info["channel_link"] or "تنظیم نشده"
    markup = get_admin_channel_keyboard(enabled=enabled, channel_id=ch_id_val, channel_link=ch_link_val)

    await message.answer(
        f"✅ **آیدی کانال با موفقیت ذخیره شد:** `{ch_id}`\n\n"
        "فراموش نکنید که ربات را در این کانال **ادمین** کنید.\n"
        "جهت بررسی دسترسی ادمین ربات، از دکمه زیر استفاده نمایید:",
        reply_markup=markup,
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:set_channel_link")
async def cb_set_channel_link(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_channel_link)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="admin:channel")]
    ])
    await call.message.edit_text(
        "🔗 **تنظیم لینک دعوت کانال:**\n\n"
        "لطفاً لینک عضویت کانال را ارسال نمایید (مثال: `https://t.me/MyChannel` یا لینک خصوصی):\n\n"
        "جهت انصراف می‌توانید روی دکمه زیر کلیک کنید یا /cancel را بفرستید.",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await call.answer()


@router.message(AdminStates.waiting_channel_link)
async def state_save_channel_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    link = message.text.strip()
    if link.lower() == "/cancel":
        await state.clear()
        text, markup = await render_admin_dashboard(message.from_user.id)
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
        return

    await db.set_setting("channel_lock_link", link)
    await state.clear()

    lock_info = await db.get_channel_lock_info()
    enabled = lock_info["enabled"]
    ch_id_val = lock_info["channel_id"] or "تنظیم نشده"
    ch_link_val = lock_info["channel_link"] or "تنظیم نشده"
    markup = get_admin_channel_keyboard(enabled=enabled, channel_id=ch_id_val, channel_link=ch_link_val)

    await message.answer(
        f"✅ **لینک دعوت کانال با موفقیت ثبت شد:**\n`{link}`",
        reply_markup=markup,
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:test_channel")
async def cb_test_channel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ch_id = await db.get_setting("channel_lock_id", "")
    if not ch_id:
        await call.answer("⚠️ ابتدا آیدی کانال را تنظیم فرمایید.", show_alert=True)
        return

    target_chat_id = normalize_chat_id(ch_id)
    try:
        bot_info = await call.bot.get_me()
        member = await call.bot.get_chat_member(chat_id=target_chat_id, user_id=bot_info.id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await call.answer("✅ عالی! ربات در کانال ادمین است و قفل به صورت کامل و دقیق کار می‌کند.", show_alert=True)
        else:
            await call.answer(f"⚠️ وضعیت ربات در کانال: {member.status}. برای کارکرد صحیح قفل، باید ربات را در کانال ادمین کنید.", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ خطا در بررسی کانال: {e}\nآیا آیدی کانال صحیح است و ربات عضو آن است؟", show_alert=True)


# هندلر بررسی عضویت برای کاربران عادی که روی دکمه کلیک می‌کنند
@router.callback_query(F.data == "check_channel_join")
async def cb_check_channel_join_user(call: CallbackQuery):
    user_id = call.from_user.id
    lock_info = await db.get_channel_lock_info()

    if not lock_info["enabled"] or not lock_info["channel_id"]:
        await call.answer("✅ قفل غیرفعال است. خوش آمدید!", show_alert=True)
        try:
            await call.message.delete()
        except Exception:
            pass
        return

    ch_id = lock_info["channel_id"].strip()
    target_chat_id = normalize_chat_id(ch_id)
    try:
        member = await call.bot.get_chat_member(chat_id=target_chat_id, user_id=user_id)
        if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await call.answer("🎉 تبریک! عضویت شما در کانال تایید شد.", show_alert=True)
            try:
                await call.message.delete()
            except Exception:
                pass
            user = await db.get_or_create_user(user_id)
            is_adm = (user_id in ADMIN_IDS)
            await call.message.answer(
                "🚀 **به ربات هوش مصنوعی خوش آمدید!**\nهم‌اکنون می‌توانید از تمامی خدمات ربات استفاده فرمایید.",
                reply_markup=get_main_menu_keyboard(web_search_enabled=bool(user.get("web_search_enabled", 0)), is_admin=is_adm),
                parse_mode="Markdown"
            )
            return
    except Exception as e:
        logger.warning(f"Error checking channel join for {user_id}: {e}")

    await call.answer("❌ شما هنوز در کانال عضو نشده‌اید! لطفاً ابتدا دکمه عضویت را زده و پس از عضویت روی این دکمه کلیک فرمایید.", show_alert=True)


# =========================================================================
# 3. مدیریت کاربران (User Management)
# =========================================================================

@router.callback_query(F.data == "admin:users")
async def cb_admin_users(call: CallbackQuery, state: FSMContext = None):
    if not is_admin(call.from_user.id):
        return
    if state:
        await state.clear()

    await state.set_state(AdminStates.waiting_user_search)
    text = (
        "👤 **مدیریت و جستجوی کاربران:**\n\n"
        "لطفاً **شناسه عددی (User ID)** کاربر مورد نظر را ارسال فرمایید تا پروفایل، وضعیت VIP، موجودی و امکان بن/آن‌بن نمایش داده شود:\n\n"
        "جهت انصراف می‌توانید روی دکمه زیر کلیک کنید یا عبارت /cancel را بفرستید."
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت به پنل", callback_data="admin:cancel")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


async def render_user_profile_card(target_id: int) -> tuple[Optional[str], Optional[InlineKeyboardMarkup]]:
    user = await db.get_user_by_id(target_id)
    if not user:
        return None, None

    is_vip = bool(user.get("is_vip", 0))
    vip_until = float(user.get("vip_until", 0) or 0)
    is_banned = await db.is_user_banned(target_id)

    role_str = "کاربر عادی ⚪"
    if target_id == MAIN_ADMIN_ID:
        role_str = "👑 مدیر اصلی و مالک ربات"
    elif target_id == SECOND_ADMIN_ID:
        role_str = "🛡️ ادمین دوم ربات"
    elif target_id in ADMIN_IDS:
        role_str = "👑 مدیر ارشد ربات"
    elif is_vip:
        role_str = "🌟 مشترک VIP"

    vip_str = "دائمی (مادام‌العمر ادمین) 🌟" if (target_id in ADMIN_IDS or target_id in (MAIN_ADMIN_ID, SECOND_ADMIN_ID)) else ("دائمی 🌟" if vip_until == -1 else (_format_time(vip_until) if (is_vip and vip_until > time.time()) else "ندارد ⚪"))
    ban_str = "مسدود شده 🚫" if is_banned else "فعال ✅"

    text = (
        f"👤 **مشخصات و پنل کاربر `{target_id}`:**\n\n"
        f"• **نام:** {user.get('first_name', 'نامشخص')}\n"
        f"• **یوزرنیم:** @{user.get('username') or 'ندارد'}\n"
        f"• **نقش در ربات:** {role_str}\n"
        f"• **وضعیت VIP:** `{vip_str}`\n"
        f"• **وضعیت دسترسی:** `{ban_str}`\n"
        f"• **موجودی توکن:** `{user.get('credits', 0):,}`\n"
        f"• **مجموع استار پرداختی:** `{user.get('stars_balance', 0):,} XTR`\n"
        f"• **تعداد پیام‌ها:** `{user.get('total_messages', 0):,}`\n"
        f"• **مدل فعال:** `{user.get('selected_model', 'نامشخص')}`\n"
        f"• **آخرین فعالیت:** {_format_time(user.get('last_active', 0))}\n"
        f"• **تاریخ عضویت:** {_format_time(user.get('created_at', 0))}\n\n"
        "عملیات مورد نظر روی این کاربر را انتخاب فرمایید:"
    )
    markup = get_admin_user_keyboard(target_user_id=target_id, is_vip=is_vip, is_banned=is_banned)
    return text, markup


@router.message(AdminStates.waiting_user_search)
async def state_user_search(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    query = message.text.strip()
    if query.lower() == "/cancel":
        await state.clear()
        text, markup = await render_admin_dashboard(message.from_user.id)
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
        return

    if not query.isdigit():
        await message.answer("⚠️ لطفاً فقط شناسه عددی (User ID) کاربر را بفرستید (مثال: `8108907825`):", parse_mode="Markdown")
        return

    target_id = int(query)
    text, markup = await render_user_profile_card(target_id)
    if not text or not markup:
        await message.answer(f"❌ کاربری با شناسه `{target_id}` در دیتابیس یافت نشد.", parse_mode="Markdown")
        return

    await state.clear()
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")


@router.callback_query(F.data.startswith("admin:grant_vip_30:"))
async def cb_grant_vip_30(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    new_until = await db.set_user_vip(uid, days=30)
    await call.answer(f"✅ اشتراک ۳۰ روزه VIP برای کاربر {uid} فعال شد!", show_alert=True)
    try:
        await call.bot.send_message(
            chat_id=uid,
            text="🎉 **تبریک! مدیریت ربات به شما ۱ ماه (۳۰ روز) اشتراک طلایی VIP هدیه داد!**\nهم‌اکنون تمامی مدل‌های پرچمدار Claude Opus 5.5، Fable 5.1 و GPT-5.6 Sol برای شما فعال است.",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    card_text, card_markup = await render_user_profile_card(uid)
    if card_text and card_markup:
        try:
            await call.message.edit_text(card_text, reply_markup=card_markup, parse_mode="Markdown")
        except Exception:
            pass


@router.callback_query(F.data.startswith("admin:grant_vip_life:"))
async def cb_grant_vip_life(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await db.set_user_vip(uid, days=-1)
    await call.answer(f"💎 اشتراک دائمی VIP برای کاربر {uid} فعال شد!", show_alert=True)
    try:
        await call.bot.send_message(
            chat_id=uid,
            text="👑 **تبریک ویژه! مدیریت ربات به شما اشتراک دائمی مادام‌العمر VIP هدیه داد!**\nشما دسترسی نامحدود به تمامی امکانات فعلی و آینده ربات دارید.",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    card_text, card_markup = await render_user_profile_card(uid)
    if card_text and card_markup:
        try:
            await call.message.edit_text(card_text, reply_markup=card_markup, parse_mode="Markdown")
        except Exception:
            pass


@router.callback_query(F.data.startswith("admin:revoke_vip:"))
async def cb_revoke_vip(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await db.revoke_user_vip(uid)
    await call.answer(f"اشتراک VIP کاربر {uid} لغو گردید.", show_alert=True)
    card_text, card_markup = await render_user_profile_card(uid)
    if card_text and card_markup:
        try:
            await call.message.edit_text(card_text, reply_markup=card_markup, parse_mode="Markdown")
        except Exception:
            pass


@router.callback_query(F.data.startswith("admin:add_tokens:"))
async def cb_add_tokens(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    uid = int(parts[2])
    amt = int(parts[3])
    await db.add_user_credits(uid, amt)
    await call.answer(f"✅ مقدار {amt} توکن به کاربر {uid} اضافه شد!", show_alert=True)
    card_text, card_markup = await render_user_profile_card(uid)
    if card_text and card_markup:
        try:
            await call.message.edit_text(card_text, reply_markup=card_markup, parse_mode="Markdown")
        except Exception:
            pass


@router.callback_query(F.data.startswith("admin:toggle_ban:"))
async def cb_toggle_ban(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    if uid in ADMIN_IDS or uid in (MAIN_ADMIN_ID, SECOND_ADMIN_ID):
        await call.answer("❌ امکان مسدودسازی مدیران ربات وجود ندارد.", show_alert=True)
        return
    is_banned = await db.is_user_banned(uid)
    if is_banned:
        await db.unban_user(uid)
        await call.answer(f"✅ کاربر {uid} رفع مسدودسازی (آن‌بن) شد.", show_alert=True)
    else:
        await db.ban_user(uid, reason="Admin panel action")
        await call.answer(f"🚫 کاربر {uid} با موفقیت مسدود (بن) شد.", show_alert=True)
    card_text, card_markup = await render_user_profile_card(uid)
    if card_text and card_markup:
        try:
            await call.message.edit_text(card_text, reply_markup=card_markup, parse_mode="Markdown")
        except Exception:
            pass


@router.callback_query(F.data == "admin:admins_list")
async def cb_admin_admins_list(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    
    # Retrieve user info from DB if available
    main_u = await db.get_user_by_id(MAIN_ADMIN_ID)
    sec_u = await db.get_user_by_id(SECOND_ADMIN_ID)
    
    main_name = f"{main_u.get('first_name', '')} (@{main_u.get('username')})" if main_u and main_u.get('username') else f"کاربر {MAIN_ADMIN_ID}"
    sec_name = f"{sec_u.get('first_name', '')} (@{sec_u.get('username')})" if sec_u and sec_u.get('username') else f"کاربر {SECOND_ADMIN_ID}"

    text = (
        "👥 **لیست و وضعیت مدیران ارشد ربات (Admin Management):**\n\n"
        f"👑 **۱. مدیر اصلی و مالک:**\n"
        f"• **نام و یوزرنیم:** {main_name}\n"
        f"• **شناسه عددی:** `{MAIN_ADMIN_ID}`\n"
        "• **سطح دسترسی:** دسترسی تام به تمامی ۳۳ مدل، تنظیم کلیدها، مدیریت کانال، آمار مالی و پیام همگانی.\n\n"
        f"🛡️ **۲. ادمین دوم ربات:**\n"
        f"• **نام و یوزرنیم:** {sec_name}\n"
        f"• **شناسه عددی:** `{SECOND_ADMIN_ID}`\n"
        "• **سطح دسترسی:** دسترسی کامل مدیریتی و دسترسی نامحدود به کلیه ۳۳ مدل (بدون نیاز به خرید استار یا VIP).\n\n"
        "🌟 وضعیت هر دو ادمین در سیستم به صورت **دائمی (Lifetime VIP)** با اعتبار بی‌نهایت فعال است."
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت به پنل ادمین", callback_data="admin:main")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


# =========================================================================
# 4. ارسال همگانی (Broadcast)
# =========================================================================

@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_broadcast_msg)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="admin:cancel")]
    ])
    await call.message.edit_text(
        "✉️ **ارسال پیام همگانی به تمامی کاربران ربات:**\n\n"
        "لطفاً پیام مورد نظر خود را ارسال نمایید (متن، عکس، ویدیو، یا پیام فورواردی از کانال):\n\n"
        "جهت انصراف می‌توانید روی دکمه زیر کلیک کنید یا عبارت /cancel را بفرستید.",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await call.answer()


@router.message(AdminStates.waiting_broadcast_msg)
async def state_do_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("ارسال همگانی لغو شد.")
        return

    await state.clear()
    user_ids = await db.get_all_user_ids()
    total = len(user_ids)

    status_msg = await message.answer(f"📢 ارسال همگانی به {total:,} کاربر آغاز شد...")

    sent_count = 0
    fail_count = 0

    for uid in user_ids:
        try:
            await message.copy_to(chat_id=uid)
            sent_count += 1
            await asyncio.sleep(0.04)  # 25 msgs/sec
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ **ارسال همگانی تکمیل شد!**\n\n"
        f"• موفق: `{sent_count:,}`\n"
        f"• ناموفق (بلاک شده): `{fail_count:,}`",
        parse_mode="Markdown"
    )


# =========================================================================
# 5. مدیریت و تست استخر کلیدهای هوش مصنوعی (Key Pools: CodeCraft, Agnes, Atria)
# =========================================================================

@router.callback_query(F.data.in_({"admin:key_pools", "admin:set_key"}))
async def cb_admin_key_pools(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()

    cc_pool = CodeCraftKeyPool.get_instance().get_status()
    atr_pool = AtriaKeyPool.get_instance().get_status()
    agn_pool = AgnesKeyPool.get_instance().get_status()

    text = (
        "🔐 **مدیریت استخرهای کلید API و بالانس بار (Key Pools)**\n\n"
        "تمامی مدل‌ها مجهز به چرخش کلید هوشمند، تشخیص قطعی (Cooldown) و سوئیچ بدون تاخیر هستند.\n\n"
        "💎 **۱. استخر CodeCraft API (۳۳ مدل نسل جدید):**\n"
        f"• وضعیت: `{cc_pool['healthy']}` از `{cc_pool['total']}` کلید آماده\n"
        f"• در حالت استراحت/خطا: `{cc_pool['cooldown']}` عدد\n"
        f"• پردازش موفق: `{cc_pool['total_successes']}` | خطاها: `{cc_pool['total_errors']}`\n\n"
        "🌅 **۲. استخر Atria ASI (مدل Atria-Dawn-Preview ۲۵۶K):**\n"
        f"• وضعیت: `{atr_pool['healthy']}` از `{atr_pool['total']}` کلید آماده\n"
        f"• در حالت استراحت/خطا: `{atr_pool['cooldown']}` عدد\n"
        f"• پردازش موفق: `{atr_pool['total_successes']}` | خطاها: `{atr_pool['total_errors']}`\n\n"
        "🍌 **۳. استخر Agnes AI (عکس، ویدیو، استدلال نانو):**\n"
        f"• وضعیت: `{agn_pool['healthy']}` از `{agn_pool['total']}` کلید آماده\n"
        f"• در حالت استراحت/خطا: `{agn_pool['cooldown']}` عدد\n"
        f"• پردازش موفق: `{agn_pool['total_successes']}` | خطاها: `{agn_pool['total_errors']}`\n\n"
        "👇 _جهت تست زنده پینگ یا افزودن کلیدهای بیشتر، از دکمه‌های زیر استفاده فرمایید:_"
    )
    markup = get_admin_key_pools_keyboard()
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "admin:test_all_keys")
async def cb_test_all_keys(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.answer("در حال تست و پینگ زنده تمامی کلیدها...")
    wait_msg = await call.message.edit_text("⏳ **در حال پینگ و تست زنده تمامی کلیدهای هوش مصنوعی...**\nلطفاً چند ثانیه شکیبا باشید.")

    cc_pool = CodeCraftKeyPool.get_instance()
    atr_pool = AtriaKeyPool.get_instance()
    agn_pool = AgnesKeyPool.get_instance()

    cc_results = []
    atr_results = []
    agn_results = []

    async with httpx.AsyncClient(timeout=25.0) as client:
        # Ping CC keys
        for n in cc_pool.nodes:
            try:
                r = await client.get("https://codecraftapi.com/v1/models", headers=cc_pool.get_headers(n.key))
                if r.status_code == 200:
                    n.record_success()
                    cc_results.append(f"• `{n.label}`: 🟢 سالم (200 OK)")
                elif r.status_code == 429:
                    n.record_error(429)
                    cc_results.append(f"• `{n.label}`: ⏳ محدودیت موقت (429)")
                else:
                    n.record_error(r.status_code)
                    cc_results.append(f"• `{n.label}`: 🔴 خطا ({r.status_code})")
            except httpx.TimeoutException:
                cc_results.append(f"• `{n.label}`: ⏳ تاخیر پاسخ سرور (تایم‌اوت)")
            except Exception:
                cc_results.append(f"• `{n.label}`: ⚠️ خطای اتصال موقت")
            await asyncio.sleep(0.4)

        # Ping Atria keys
        for n in atr_pool.nodes:
            try:
                r = await client.get("https://api.atria-asi.ai/v1/models", headers=atr_pool.get_headers(n.key))
                if r.status_code == 200:
                    n.record_success()
                    atr_results.append(f"• `{n.label}`: 🟢 سالم (200 OK)")
                elif r.status_code == 429:
                    n.record_error(429)
                    atr_results.append(f"• `{n.label}`: ⏳ محدودیت موقت (429)")
                else:
                    n.record_error(r.status_code)
                    atr_results.append(f"• `{n.label}`: 🔴 خطا ({r.status_code})")
            except httpx.TimeoutException:
                atr_results.append(f"• `{n.label}`: ⏳ تاخیر پاسخ سرور (تایم‌اوت)")
            except Exception:
                atr_results.append(f"• `{n.label}`: ⚠️ خطای اتصال موقت")
            await asyncio.sleep(0.3)

        # Ping Agnes keys
        for n in agn_pool.nodes:
            try:
                r = await client.get("https://apihub.agnes-ai.com/v1/models", headers=agn_pool.get_headers(n.key))
                if r.status_code == 200:
                    n.record_success()
                    agn_results.append(f"• `{n.label}`: 🟢 سالم (200 OK)")
                elif r.status_code == 429:
                    n.record_error(429)
                    agn_results.append(f"• `{n.label}`: ⏳ محدودیت موقت (429)")
                else:
                    n.record_error(r.status_code)
                    agn_results.append(f"• `{n.label}`: 🔴 خطا ({r.status_code})")
            except httpx.TimeoutException:
                agn_results.append(f"• `{n.label}`: ⏳ تاخیر پاسخ سرور (تایم‌اوت)")
            except Exception:
                agn_results.append(f"• `{n.label}`: ⚠️ خطای اتصال موقت")
            await asyncio.sleep(0.3)

    text = (
        "📊 **گزارش تست زنده سلامت کلیدهای هوش مصنوعی:**\n\n"
        "💎 **CodeCraft API:**\n" + "\n".join(cc_results) + "\n\n"
        "🌅 **Atria ASI:**\n" + "\n".join(atr_results) + "\n\n"
        "🍌 **Agnes AI:**\n" + "\n".join(agn_results) + "\n\n"
        "✅ تمامی کلیدهای سبز در استخر توزیع بار فعال هستند."
    )
    markup = get_admin_key_pools_keyboard()
    await wait_msg.edit_text(text, reply_markup=markup, parse_mode="Markdown")


# ---- 1. Add CodeCraft Key ----
@router.callback_query(F.data == "admin:add_key_codecraft")
async def cb_add_key_codecraft(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_add_key_codecraft)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="admin:key_pools")]
    ])
    text = (
        "➕ **افزودن کلید به استخر CodeCraft API:**\n\n"
        "لطفاً کلید جدید را ارسال نمایید (مثال: `cc_...`):\n\n"
        "جهت انصراف می‌توانید روی دکمه زیر کلیک کنید یا /cancel را بفرستید."
    )
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


@router.message(AdminStates.waiting_add_key_codecraft)
async def state_save_add_codecraft_key(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    new_key = message.text.strip()
    if new_key.lower() == "/cancel":
        await state.clear()
        await message.answer("عملیات لغو شد.")
        return

    CodeCraftKeyPool.get_instance().add_key(new_key)
    # Persist in .env
    env_path = BASE_DIR / ".env"
    try:
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            import re
            m = re.search(r"CODECRAFT_API_KEYS=(.*)", content)
            if m:
                existing = m.group(1).strip()
                if new_key not in existing:
                    updated = f"CODECRAFT_API_KEYS={new_key},{existing}"
                    content = re.sub(r"CODECRAFT_API_KEYS=.*", updated, content)
            else:
                content += f"\nCODECRAFT_API_KEYS={new_key}\n"
            env_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Error persisting key to .env: {e}")

    await state.clear()
    await message.answer(f"✅ کلید جدید CodeCraft (`...{new_key[-6:]}`) با موفقیت به استخر اضافه شد.")


# ---- 2. Add Atria Key ----
@router.callback_query(F.data == "admin:add_key_atria")
async def cb_add_key_atria(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_add_key_atria)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="admin:key_pools")]
    ])
    text = (
        "➕ **افزودن کلید به استخر Atria ASI:**\n\n"
        "لطفاً کلید جدید را ارسال نمایید (مثال: `atr_...`):\n\n"
        "جهت انصراف می‌توانید روی دکمه زیر کلیک کنید یا /cancel را بفرستید."
    )
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


@router.message(AdminStates.waiting_add_key_atria)
async def state_save_add_atria_key(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    new_key = message.text.strip()
    if new_key.lower() == "/cancel":
        await state.clear()
        await message.answer("عملیات لغو شد.")
        return

    AtriaKeyPool.get_instance().add_key(new_key)
    env_path = BASE_DIR / ".env"
    try:
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            import re
            m = re.search(r"ATRIA_API_KEYS=(.*)", content)
            if m:
                existing = m.group(1).strip()
                if new_key not in existing:
                    updated = f"ATRIA_API_KEYS={new_key},{existing}"
                    content = re.sub(r"ATRIA_API_KEYS=.*", updated, content)
            else:
                content += f"\nATRIA_API_KEYS={new_key}\n"
            env_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Error persisting Atria key to .env: {e}")

    await state.clear()
    await message.answer(f"✅ کلید جدید Atria (`...{new_key[-6:]}`) با موفقیت به استخر اضافه شد.")


# ---- 3. Add Agnes Key ----
@router.callback_query(F.data == "admin:add_key_agnes")
async def cb_add_key_agnes(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_add_key_agnes)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="admin:key_pools")]
    ])
    text = (
        "➕ **افزودن کلید به استخر Agnes AI:**\n\n"
        "لطفاً کلید جدید را ارسال نمایید (مثال: `sk-...`):\n\n"
        "جهت انصراف می‌توانید روی دکمه زیر کلیک کنید یا /cancel را بفرستید."
    )
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


@router.message(AdminStates.waiting_add_key_agnes)
async def state_save_add_agnes_key(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    new_key = message.text.strip()
    if new_key.lower() == "/cancel":
        await state.clear()
        await message.answer("عملیات لغو شد.")
        return

    AgnesKeyPool.get_instance().add_key(new_key)
    env_path = BASE_DIR / ".env"
    try:
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            import re
            m = re.search(r"AGNES_API_KEYS=(.*)", content)
            if m:
                existing = m.group(1).strip()
                if new_key not in existing:
                    updated = f"AGNES_API_KEYS={new_key},{existing}"
                    content = re.sub(r"AGNES_API_KEYS=.*", updated, content)
            else:
                content += f"\nAGNES_API_KEYS={new_key}\n"
            env_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Error persisting Agnes key to .env: {e}")

    await state.clear()
    await message.answer(f"✅ کلید جدید Agnes (`...{new_key[-6:]}`) با موفقیت به استخر اضافه شد.")


@router.callback_query(F.data == "admin:models")
async def cb_admin_models(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    text = (
        "🤖 **کاتالوگ مدل‌های CodeCraft API و سیستم دسترسی:**\n\n"
        "⭐ **مدل‌های اختصاصی قفل استار (Star VIP):**\n"
        "• `claude-fable-5.1` (Claude Fable 5.1)\n"
        "• `claude-fable-5` (Claude Fable 5)\n"
        "• `claude-opus-5.5` (Claude Opus 5.5 Flagship)\n"
        "• `claude-opus-5` (Claude Opus 5)\n"
        "• `claude-opus-4.8` (Claude Opus 4.8)\n"
        "• `claude-mythos-preview` (Claude Mythos)\n"
        "• `gpt-5.6-sol` (GPT-5.6 Sol)\n"
        "• `gpt-5.5-pro` (GPT-5.5 Pro)\n"
        "• `deepseek-v4-pro-max` (DeepSeek V4 Pro Max)\n\n"
        "🔓 **مدل‌های در دسترس عموم:**\n"
        "• Claude Sonnet 5, GPT-5.6 Terra, GPT-5.6 Luna, GPT-5.5\n"
        "• DeepSeek V4 Pro, Flash, Gemini 3.7 Flash, Grok 4.6\n"
        "• Qwen 3.8 Max, Kimi K3, GLM 5.3, Seed 2.1, Gemma 2B\n\n"
        "👑 *نکته: شما به عنوان مدیر ربات به تمامی این مدل‌ها دسترسی نامحدود و رایگان دارید.*"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت به پنل ادمین", callback_data="admin:main")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "admin:stars")
async def cb_admin_stars(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    from app.bot.handlers.account import STAR_PLANS
    plans_text = ""
    for k, p in STAR_PLANS.items():
        plans_text += f"• **{p['title']}:** `{p['stars']} استار (XTR)`\n  _{p['description']}_\n\n"

    text = (
        "⭐ **تنظیمات پلن‌های فروش با استار تلگرام (Telegram Stars):**\n\n"
        f"{plans_text}"
        "💳 پرداخت‌ها به صورت آنی و خودکار توسط درگاه رسمی تلگرام بدون نیاز به واسطه انجام شده و بلافاصله حساب کاربر را به VIP ارتقا می‌دهد."
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت به پنل ادمین", callback_data="admin:main")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "admin:unlock")
async def cb_admin_unlock(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    from app.bot.middlewares import ConcurrencyManager
    await ConcurrencyManager.finish_user_processing(call.from_user.id)
    await call.answer("🔓 تمامی قفل‌های پردازشی با موفقیت بازنشانی شدند.", show_alert=True)
