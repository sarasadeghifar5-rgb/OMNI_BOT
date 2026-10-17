"""
AI Model Selector handlers and callbacks.
Features official logos for each AI model.
"""
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from database import db
from keyboards import get_models_inline_keyboard, get_main_keyboard
from config import AVAILABLE_MODELS

router = Router()

@router.message(Command("models"))
@router.message(F.text.in_(["تغییر مدل هوشمند", "تغییر مدل هوش مصنوعی", "🤖 تغییر مدل هوشمند", "🤖 تغییر مدل هوش مصنوعی"]))
async def show_models_menu(message: Message):
    current_model = await db.get_user_model(message.from_user.id)
    model_info = AVAILABLE_MODELS.get(current_model, {})
    logo_path = model_info.get("logo")

    caption = (
        f"🤖 **انتخاب مدل هوش مصنوعی:**\n\n"
        f"🏷 **مدل فعال:** {model_info.get('icon', '⚡')} **{model_info.get('name', current_model)}**\n"
        f"🏢 **سرویس‌دهنده:** `{model_info.get('provider', '')}`\n\n"
        f"برای تغییر مدل، گزینه دلخواه را از منوی زیر لمس کنید:"
    )

    if logo_path and os.path.exists(logo_path):
        await message.answer_photo(
            photo=FSInputFile(logo_path),
            caption=caption,
            reply_markup=get_models_inline_keyboard(current_model),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            caption,
            reply_markup=get_models_inline_keyboard(current_model),
            parse_mode="Markdown"
        )

@router.message(F.text.in_(["مدل هوشمند پرو", "استدلال عمیق (Atria)", "🧠 مدل هوشمند پرو", "🧠 استدلال عمیق (Atria)"]))
async def quick_switch_atria(message: Message):
    atria_model = "Atria-Dawn-Preview"
    await db.set_user_model(message.from_user.id, atria_model)
    model_info = AVAILABLE_MODELS.get(atria_model, {})
    logo_path = model_info.get("logo")
    
    caption = (
        f"🧠 **مدل هوشمند پرو فعال شد!**\n\n"
        f"• **نوع مدل:** استدلال عمیق و تفکر منطقی\n"
        f"• **ظرفیت:** ۲۰۰,۰۰۰ توکن"
    )

    if logo_path and os.path.exists(logo_path):
        await message.answer_photo(
            photo=FSInputFile(logo_path),
            caption=caption,
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            caption,
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )

@router.callback_query(F.data.startswith("set_model:"))
async def callback_set_model(callback: CallbackQuery):
    model_id = callback.data.split(":", 1)[1]
    if model_id not in AVAILABLE_MODELS:
        await callback.answer("مدل نامعتبر است!", show_alert=True)
        return

    await db.set_user_model(callback.from_user.id, model_id)
    model_info = AVAILABLE_MODELS[model_id]
    logo_path = model_info.get("logo")

    await callback.answer(f"{model_info['name']} فعال شد!")

    caption = (
        f"✅ **مدل هوش مصنوعی تغییر کرد!**\n\n"
        f"🏷 **مدل فعال:** {model_info['icon']} **{model_info['name']}**\n"
        f"🏢 **سرویس:** `{model_info['provider']}`"
    )

    try:
        if logo_path and os.path.exists(logo_path):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile(logo_path),
                caption=caption,
                reply_markup=get_models_inline_keyboard(model_id),
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                caption,
                reply_markup=get_models_inline_keyboard(model_id),
                parse_mode="Markdown"
            )
    except Exception:
        pass

@router.callback_query(F.data == "close_models_menu")
async def callback_close_menu(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("منو بسته شد.")
