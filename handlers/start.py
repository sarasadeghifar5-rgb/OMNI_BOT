"""
Start, Help, Clear history, and navigation handlers.
Uses 'مدل هوشمند پرو' branding.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from database import db
from keyboards import get_main_keyboard
from config import AVAILABLE_MODELS

router = Router()

START_TEXT = (
    "سلام {name} عزیز! 👋 خوش آمدید به **سوپر ربات هوش مصنوعی** 🚀\n\n"
    "این ربات مجهز به پیشرفته‌ترین موتورها و سرویس‌های جهانی هوش مصنوعی است:\n\n"
    "✨ **امکانات ویژه چندرسانه‌ای مدل هوشمند پرو:**\n"
    "• 🎨 **ساخت عکس:** تولید تصاویر هنری و باکیفیت بالا با نوار شارژ زنده\n"
    "• ✏️ **ادیت عکس:** تغییر و روتوش هوشمند تصاویر بر اساس دستور متنی\n"
    "• 🎬 **تولید ویدیو:** تبدیل ایده و سناریو به ویدیوی متحرک\n"
    "• 🎞 **متحرک‌سازی عکس:** تبدیل عکس‌های ثابت به کلیپ متحرک زنده\n\n"
    "🧠 **موتورهای متنی و استدلال:**\n"
    "• 🌟 **CleanAPIs:** پرچمداران Claude 5, GPT-5.6 Sol, DeepSeek V4, Gemini 3.7\n"
    "• 🧠 **مدل هوشمند پرو:** تفکر و استدلال عمیق با پنجره ۲۰۰ هزار توکن\n"
    "• 🌐 **Google AI Studio:** هوش مصنوعی جمینای و بینایی تصویر (Vision)\n"
    "• 📄 **تحلیل فایل و اسناد:** پشتیبانی کامل از PDF، ورد، کدها و عکس‌ها با مدل فعال\n\n"
    "🎯 **مدل فعال فعلی شما:** `{model_name}`\n\n"
    "از منوی زیر برای دسترسی سریع به امکانات استفاده کنید:"
)

HELP_TEXT = (
    "📖 **راهنمای استفاده از ربات هوش مصنوعی:**\n\n"
    "💬 **چت و پاسخ‌دهی هوشمند:**\n"
    "هر سؤالی داری بپرس! ربات حین تفکر وضعیت را به صورت زنده نمایش می‌دهد و کامل‌ترین پاسخ را تحویل می‌دهد.\n\n"
    "📄 **تحلیل فایل و اسناد (PDF، ورد، کد):**\n"
    "هر فایلی اعم از PDF، Word (.docx)، کدهای برنامه‌نویسی یا متن بفرستید، مدل هوشمند فعال شما آن را دقیق مطالعه و تحلیل می‌کند.\n\n"
    "👁 **تحلیل تصاویر و عکس‌ها:**\n"
    "عکس ارسال کنید تا توسط مدل هوشمند شما با جزئیات کامل تحلیل و تشریح شود.\n\n"
    "🎨 **ساخت عکس:**\n"
    "با دکمه «🎨 ساخت عکس» یا دستور `/image <متن>` تصاویر باکیفیت تولید کنید.\n\n"
    "✏️ **ادیت عکس:**\n"
    "با دکمه «✏️ ادیت عکس» یا دستور `/edit`، عکس بفرستید و دستور ادیت را بنویسید.\n\n"
    "🎞 **متحرک‌سازی عکس:**\n"
    "با دکمه «🎞 متحرک‌سازی عکس» یا دستور `/animate`، عکس‌های خود را به ویدیوی زنده تبدیل کنید.\n\n"
    "🎬 **تولید ویدیو:**\n"
    "با دکمه «🎬 تولید ویدیو» یا دستور `/video <متن>` سناریوی خود را به ویدیو تبدیل کنید.\n\n"
    "🤖 **تغییر مدل هوش مصنوعی:**\n"
    "امکان جابه‌جایی بین Claude, GPT-5.6, DeepSeek, مدل هوشمند پرو و Gemini.\n\n"
    "🧠 **مدل هوشمند پرو:**\n"
    "دکمه میانبر برای فعال‌سازی فوری مدل تفکر عمیق با حافظه ۲۰۰K توکن.\n\n"
    "🗑 **پاکسازی حافظه:**\n"
    "با دکمه «🗑 پاکسازی گفتگو» یا دستور `/clear` حافظه گفتگو ریست می‌شود."
)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    current_model = user["selected_model"]
    model_title = AVAILABLE_MODELS.get(current_model, {}).get("name", current_model)

    await message.answer(
        START_TEXT.format(
            name=message.from_user.first_name or "کاربر",
            model_name=model_title
        ),
        reply_markup=get_main_keyboard(message.from_user.id),
        parse_mode="Markdown"
    )

@router.message(Command("help"))
@router.message(F.text.in_(["راهنما و وضعیت", "ℹ️ راهنما و وضعیت"]))
async def cmd_help(message: Message):
    user_model = await db.get_user_model(message.from_user.id)
    model_info = AVAILABLE_MODELS.get(user_model, {})
    model_name = model_info.get("name", user_model)
    provider = model_info.get("provider", "نامشخص")

    status_text = (
        f"{HELP_TEXT}\n\n"
        f"──────────────\n"
        f"📊 **وضعیت حساب شما:**\n"
        f"• شناسه کاربری: `{message.from_user.id}`\n"
        f"• مدل فعال: **{model_name}** ({provider})\n"
        f"• وضعیت سیستم: 🟢 کلیه سرویس‌ها آنلاین"
    )

    await message.answer(status_text, parse_mode="Markdown")

@router.message(Command("clear"))
@router.message(F.text.in_(["پاکسازی گفتگو", "🗑 پاکسازی گفتگو"]))
async def cmd_clear(message: Message, state: FSMContext):
    await state.clear()
    await db.clear_history(message.from_user.id)
    await message.answer(
        "🧹 حافظه و تاریخچه مکالمات شما با موفقیت پاکسازی شد!\n"
        "حالا می‌توانید یک گفتگوی جدید را آغاز فرمایید.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )

@router.message(F.text.in_(["انصراف و بازگشت", "❌ انصراف و بازگشت"]))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "عملیات لغو شد و به منوی اصلی بازگشتید.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )
