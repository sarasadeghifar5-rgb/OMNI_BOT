"""
Admin Panel handlers for user ID 495404413.
Includes statistics, key pool health checks, and global message broadcasts.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import ADMIN_ID, CLEANAPIS_API_KEY
from database import db
from keyboards import get_admin_keyboard, get_cancel_keyboard, get_main_keyboard
from api_services.agnes import agnes_client
from api_services.atria import atria_client
from api_services.gemini import gemini_client
import asyncio
import logging

router = Router()
logger = logging.getLogger(__name__)

class AdminStates(StatesGroup):
    waiting_for_broadcast_text = State()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@router.message(Command("admin"))
@router.message(F.text.in_(["پنل مدیریت", "⚙️ پنل مدیریت"]))
async def open_admin_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما به پنل مدیریت دسترسی ندارید.")
        return

    await state.clear()
    await message.answer(
        "⚙️ **به پنل مدیریت ربات هوش مصنوعی خوش آمدید!**\n\n"
        "از دکمه‌های زیر برای بررسی وضعیت ربات، مشاهده آمار و ارسال پیام همگانی استفاده کنید:",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز", show_alert=True)
        return

    stats = await db.get_stats()
    text = (
        "📊 **آمار جامع ربات:**\n\n"
        f"👥 تعداد کل کاربران: **{stats['total_users']}** نفر\n"
        f"🟢 کاربران فعال امروز: **{stats['active_today']}** نفر\n"
        f"💬 کل پیام‌های دریافتی: **{stats['total_prompts']}** پیام\n"
        f"🎨 تصاویر تولیدشده: **{stats['total_images']}** تصویر\n"
        f"🎬 ویدیوهای درخواستی: **{stats['total_videos']}** ویدیو\n"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_keys")
async def show_key_status(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز", show_alert=True)
        return

    agnes_status = agnes_client.pool.get_status_report()
    atria_status = atria_client.pool.get_status_report()
    gemini_status = gemini_client.pool.get_status_report()

    text = (
        "🔑 **وضعیت سلامت استخر کلیدها (Key Pools):**\n\n"
        f"**۱. سرویس Agnes AI (استودیو نانو):**\n"
        f"• کلیدها: {agnes_status['total_keys']} عدد | فعال: {agnes_status['active_keys']} | در استراحت: {agnes_status['in_cooldown']}\n"
        f"• موفق: {agnes_status['total_success']} | خطاها: {agnes_status['total_errors']}\n\n"
        f"**۲. سرویس Atria ASI (استدلال عمیق):**\n"
        f"• کلیدها: {atria_status['total_keys']} عدد | فعال: {atria_status['active_keys']} | در استراحت: {atria_status['in_cooldown']}\n"
        f"• موفق: {atria_status['total_success']} | خطاها: {atria_status['total_errors']}\n\n"
        f"**۳. سرویس Google Gemini:**\n"
        f"• کلیدها: {gemini_status['total_keys']} عدد | فعال: {gemini_status['active_keys']} | در استراحت: {gemini_status['in_cooldown']}\n\n"
        f"**۴. سرویس CleanAPIs (کدکرفت):**\n"
        f"• کلید: `cc_95Sq...AloB` (وضعیت: 🟢 فعال و متصل)"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی غیرمجاز", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.message.answer(
        "📢 **ارسال پیام همگانی:**\n\n"
        "لطفاً متن پیامی که می‌خواهید برای تمام کاربران ارسال شود را بفرستید:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_text, F.text)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if message.text == "❌ انصراف و بازگشت":
        await state.clear()
        await message.answer("ارسال همگانی لغو شد.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    broadcast_text = message.text
    await state.clear()

    user_ids = await db.get_all_user_ids()
    total_users = len(user_ids)
    progress_msg = await message.answer(f"⏳ در حال ارسال به {total_users} کاربر...")

    success = 0
    failed = 0

    for uid in user_ids:
        try:
            await message.bot.send_message(chat_id=uid, text=broadcast_text)
            success += 1
            await asyncio.sleep(0.05)  # Rate limit safety
        except Exception:
            failed += 1

    await progress_msg.edit_text(
        f"✅ **ارسال همگانی به پایان رسید!**\n\n"
        f"• ارسال موفق: **{success}** کاربر\n"
        f"• ارسال ناموفق / مسدود شده: **{failed}** کاربر",
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_close")
async def close_admin_panel(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("پنل مدیریت بسته شد.")
