from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from app.bot.database import BotDatabase
from app.bot.config import ADMIN_IDS, MAIN_ADMIN_ID, SECOND_ADMIN_ID
from app.config import STAR_LOCKED_MODELS, AVAILABLE_MODELS, get_model_capabilities, format_model_card
from app.bot.keyboards import (
    get_main_menu_keyboard,
    get_models_keyboard,
    get_model_categories_keyboard,
    get_category_models_keyboard,
    get_persistent_reply_keyboard,
    get_newchat_keyboard,
    get_model_features_keyboard,
    MODEL_CATEGORIES
)
from app.bot.utils import safe_reply

router = Router(name="start_router")
db = BotDatabase.get_instance()

WELCOME_TEXT = """✨ به دستیار هوشمند هوش مصنوعی خوش آمدید!

دسترسی سریع به قدرتمندترین مدلها و ابزارهای هوش مصنوعی:

🧠 مدلهای پیشرفته و استدلالی
Claude • GPT • Gemini • DeepSeek • GLM • Grok • Kimi • Qwen

🍌 تولید و ادیت تصویر
Nano Banana • Seedance AI

🎬 تولید ویدیو
Seedance AI • Nano Banana

👁 تحلیل فایل + وبسرچ
تحلیل تصویر، اسناد و جستجوی آنلاین

💬 پیام یا سؤال خود را ارسال کنید.
برای انتخاب مدل و ابزارها از منوی پایین استفاده کنید."""

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext = None):
    if state:
        await state.clear()
    # Check if user joined via referral link: /start ref_12345
    if message.text:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].startswith("ref_"):
            try:
                inviter_id = int(parts[1].replace("ref_", ""))
                await db.add_referral(inviter_id=inviter_id, new_user_id=message.from_user.id)
            except Exception:
                pass

    user = await db.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    is_admin = (message.from_user.id in ADMIN_IDS)
    
    # Send clean, single welcome message with persistent keyboard attached (no inline buttons)
    await safe_reply(
        message,
        WELCOME_TEXT,
        reply_markup=get_persistent_reply_keyboard(is_admin=is_admin)
    )

@router.message(Command("help", "menu"))
@router.message(F.text.in_({"⚙️ منو", "منو"}))
async def cmd_help(message: Message, state: FSMContext = None):
    if state:
        await state.clear()
    user = await db.get_or_create_user(message.from_user.id)
    current_model = user.get("selected_model", "gemini")
    # Refresh persistent keyboard
    await message.answer(
        "👋 پنل دسترسی سریع به‌روزرسانی شد.",
        reply_markup=get_persistent_reply_keyboard(is_admin=(message.from_user.id in ADMIN_IDS))
    )
    await safe_reply(
        message,
        "📋 **منوی مدیریت و تنظیمات ربات:**",
        reply_markup=get_main_menu_keyboard(web_search_enabled=bool(user.get("web_search_enabled", 0)), current_model=current_model, is_admin=(message.from_user.id in ADMIN_IDS))
    )

@router.message(Command("clear", "newchat", "reset"))
@router.message(F.text.in_({"💬 گفتگوی جدید", "گفتگوی جدید", "💬 گفتگو جدید", "گفتگو جدید", "🗑️ گفتگو جدید", "🗨️ گفتگو جدید", "🗑️ چت جدید", "چت جدید"}))
async def cmd_new_conversation(message: Message, state: FSMContext = None):
    user_id = message.from_user.id
    if state:
        await state.clear()
    await db.clear_chat_history(user_id)
    user = await db.get_or_create_user(user_id)
    current_model = user.get("selected_model", "gemini")
    caps = get_model_capabilities(current_model)

    # If user was in an image or video studio, switch back to conversational LLM
    if caps.get("is_image_studio") or caps.get("is_video_studio"):
        chat_model = await db.get_user_chat_model(user_id)
        await db.update_user_model(user_id, chat_model)
        current_model = chat_model
        user["selected_model"] = chat_model

    web_search = bool(user.get("web_search_enabled", 0))

    # If user used an older button text, update their persistent keyboard
    if message.text in {"💬 گفتگوی جدید", "گفتگوی جدید", "🗑️ چت جدید", "چت جدید", "💬 گفتگو جدید", "گفتگو جدید 💬", "🗑️ گفتگو جدید"}:
        await message.answer(
            "🔄 کیبورد ربات با موفقیت به‌روزرسانی شد.",
            reply_markup=get_persistent_reply_keyboard(is_admin=(message.from_user.id in ADMIN_IDS))
        )

    model_name = MODEL_NAMES.get(current_model, current_model)
    text = (
        f"💬 **گفتگوی جدید آغاز شد!**\n\n"
        f"🤖 **مدل فعال: {model_name}**\n\n"
        "پیام متنی، پرسش، عکس یا فایل مورد نظر خود را جهت گفتگو و تحلیل هوشمند ارسال فرمایید."
    )
    await message.answer(
        text,
        reply_markup=get_model_features_keyboard(model_id=current_model, web_search_enabled=web_search),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "newchat:toggle_search")
async def cb_newchat_toggle_search(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    current_model = user.get("selected_model", "gemini")
    caps = get_model_capabilities(current_model)
    if not caps["supports_web_search"]:
        await call.answer(
            f"⚠️ مدل «{caps['name']}» از وب سرچ پشتیبانی نمی‌کند.\nبرای استفاده از وب سرچ، مدلی مانند Gemini 3.7 Flash یا GPT-5.6 را انتخاب نمایید.",
            show_alert=True
        )
        return

    new_state = await db.toggle_web_search(call.from_user.id)
    await call.message.edit_reply_markup(
        reply_markup=get_model_features_keyboard(model_id=current_model, web_search_enabled=new_state)
    )
    status_msg = "وب سرچ فعال شد ✅" if new_state else "وب سرچ غیرفعال شد ❌"
    await call.answer(status_msg, show_alert=False)


@router.callback_query(F.data.in_({"newchat:toggle_reasoning", "feat:info_reasoning"}))
async def cb_feat_info_reasoning(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    current_model = user.get("selected_model", "gemini")
    caps = get_model_capabilities(current_model)
    if caps["supports_reasoning"]:
        await call.answer(
            f"🧠 حل مسائل ({caps['name']}):\nاین مدل مجهز به تفکر تحلیلی و حل مسائل گام‌به‌گام است.",
            show_alert=True
        )
    else:
        await call.answer(
            f"❌ حل مسائل ({caps['name']}):\nاین مدل فاقد قابلیت حل مسائل گام‌به‌گام است.",
            show_alert=True
        )


@router.callback_query(F.data == "feat:info_vision")
async def cb_feat_info_vision(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    current_model = user.get("selected_model", "gemini")
    caps = get_model_capabilities(current_model)
    if caps["supports_vision"]:
        await call.answer(
            f"👁️ تحلیل تصویر ({caps['name']}):\nاین مدل از تحلیل تصویر پشتیبانی می‌کند. می‌توانید هر عکسی را جهت تحلیل ارسال فرمایید.",
            show_alert=True
        )
    else:
        await call.answer(
            f"❌ تحلیل تصویر ({caps['name']}):\nاین مدل فقط متنی است و از تحلیل عکس پشتیبانی نمی‌کند.",
            show_alert=True
        )


@router.message(Command("model", "models"))
@router.message(F.text.in_({"انتخاب مدل 🤖", "🤖 انتخاب مدل", "انتخاب مدل", "مدل ها", "مدل‌ها"}))
async def cmd_model(message: Message):
    user = await db.get_or_create_user(message.from_user.id)
    current_model = user.get("selected_model", "Atria-Dawn-Preview")
    is_vip_or_admin = (message.from_user.id in ADMIN_IDS) or await db.is_user_vip(message.from_user.id)
    model_name = MODEL_NAMES.get(current_model, current_model)
    user_status = "کاربر ویژه (VIP) ⭐" if is_vip_or_admin else "کاربر عادی ⚪"

    text = (
        "🤖 <b>مرکز انتخاب مدل‌های هوش مصنوعی</b>\n\n"
        f"📍 <b>مدل فعال شما:</b> <code>{model_name}</code>\n"
        f"💎 <b>وضعیت اشتراک:</b> <code>{user_status}</code>\n\n"
        "🌟 <b>مدل‌های برتر و پیشنهادی:</b>\n"
        "برای تغییر مدل، یکی از گزینه‌های زیر را انتخاب نمایید. جهت مرور تمامی ۳۳ مدل، دکمهٔ <b>دسته‌بندی جامع</b> را لمس کنید.\n\n"
        "📌 <b>راهنما:</b>\n"
        "▫️ علامت 🔒 مخصوص کاربران دارای اشتراک Star VIP است.\n"
        "▫️ تیک سبز ✅ مدل فعال فعلی شما را مشخص می‌کند."
    )
    await safe_reply(
        message,
        text,
        reply_markup=get_models_keyboard(current_model, is_vip_or_admin=is_vip_or_admin),
        parse_mode="HTML"
    )


async def _switch_model_cmd(message: Message, model_id: str, display_name: str):
    user_id = message.from_user.id
    is_admin = (user_id in ADMIN_IDS)
    is_vip = await db.is_user_vip(user_id)

    if model_id in STAR_LOCKED_MODELS and not (is_admin or is_vip):
        from app.bot.keyboards import get_star_paywall_keyboard
        await message.answer(
            f"🔒 <b>دسترسی محدود · مدل اختصاصی</b>\n\n"
            f"مدل <b>{display_name}</b> مخصوص کاربران دارای اشتراک استار تلگرام (Star VIP) است.\n\n"
            f"⭐ <b>برای دسترسی به این مدل پرچمدار، لطفاً اشتراک VIP تهیه فرمایید:</b>",
            reply_markup=get_star_paywall_keyboard(model_id),
            parse_mode="HTML"
        )
        return

    await db.update_user_model(user_id, model_id)
    user = await db.get_or_create_user(user_id)
    web_search = bool(user.get("web_search_enabled", 0))
    model_name = MODEL_NAMES.get(model_id, display_name)
    text = (
        "🤖 <b>مدل هوش مصنوعی با موفقیت تنظیم شد</b>\n\n"
        f"✅ <b>مدل فعال جدید:</b> <code>{model_name}</code>\n\n"
        "💬 <b>وضعیت:</b> آماده پاسخگویی به پیام‌ها، پرسش‌ها یا تحلیل اسناد شما.\n"
        "پیام یا سوال خود را ارسال فرمایید."
    )
    await message.answer(
        text,
        reply_markup=get_model_features_keyboard(model_id, web_search_enabled=web_search),
        parse_mode="HTML"
    )


@router.message(Command("opus", "opus55"))
async def cmd_set_opus55(message: Message):
    await _switch_model_cmd(message, "claude-opus-5.5", "Claude Opus 5.5 💎")


@router.message(Command("opus5"))
async def cmd_set_opus5(message: Message):
    await _switch_model_cmd(message, "claude-opus-5", "Claude Opus 5 💎")


@router.message(Command("fable", "fable51"))
async def cmd_set_fable51(message: Message):
    await _switch_model_cmd(message, "claude-fable-5.1", "Claude Fable 5.1 🌟")


@router.message(Command("fable5"))
async def cmd_set_fable5(message: Message):
    await _switch_model_cmd(message, "claude-fable-5", "Claude Fable 5 🌟")


@router.message(Command("gpt5", "sol"))
async def cmd_set_gpt5(message: Message):
    await _switch_model_cmd(message, "gpt-5.6-sol", "GPT-5.6 Sol ☀️")


@router.message(Command("deepseek4", "v4"))
async def cmd_set_deepseek4(message: Message):
    await _switch_model_cmd(message, "deepseek-v4-pro-max", "DeepSeek V4 Pro Max 🧠")


@router.message(Command("sonnet5"))
async def cmd_set_sonnet5(message: Message):
    await _switch_model_cmd(message, "claude-sonnet-5", "Claude Sonnet 5 🖋️")


@router.message(Command("atria"))
@router.message(Command("dawn"))
async def cmd_set_atria(message: Message):
    await db.update_user_model(message.from_user.id, "Atria-Dawn-Preview")
    await message.answer(
        "🌅 <b>مدل Atria Dawn Preview فعال شد</b>\n\n"
        "▫️ <b>سازنده:</b> Atria ASI\n"
        "▫️ <b>حافظه زمینه:</b> ۲۵۶,۰۰۰ توکن\n"
        "▫️ <b>قابلیت ویژه:</b> استدلال منطقی عمیق و نمایش فرایند تفکر (Thinking Process)\n\n"
        "💬 <b>وضعیت:</b> هم‌اکنون هر پیام، پرسش یا سندی ارسال کنید، با مدل Atria Dawn پردازش خواهد شد.",
        parse_mode="HTML"
    )


@router.message(Command("reasoner", "think"))
@router.message(F.text.in_({"🧠 استدلال عمیق", "استدلال عمیق", "🧠 استدلال عمیق نانو", "استدلال عمیق نانو", "استدلال عمیق نانو ۲.۵"}))
async def cmd_set_deep_reasoner(message: Message):
    await db.update_user_model(message.from_user.id, "agnes-2.5-flash")
    await message.answer(
        "🧠 <b>مدل استدلال عمیق نانو ۲.۵ فعال شد</b>\n\n"
        "▫️ <b>قابلیت ویژه:</b> استدلال تحلیلی، حل مسائل و نمایش فرایند تفکر عمیق\n"
        "▫️ <b>بینایی هوشمند (Vision):</b> پشتیبانی از تحلیل عکس، نمودارها و اسناد ارسالی\n\n"
        "💬 <b>وضعیت:</b> هم‌اکنون هر پیام یا تصویری ارسال کنید، با تفکر عمیق و استدلال تحلیلی پاسخ داده می‌شود.",
        parse_mode="HTML"
    )

@router.message(Command("search"))
@router.message(F.text.in_({"🌏 وب‌سرچ زنده", "🌐 وب‌سرچ زنده", "وب‌سرچ زنده", "وب سرچ"}))
async def cmd_toggle_search(message: Message):
    new_state = await db.toggle_web_search(message.from_user.id)
    status_text = "🟢 **روشن**" if new_state else "⚪ **خاموش**"
    await message.answer(
        f"وضعیت وب‌سرچ زنده تغییر یافت: {status_text}\n"
        f"{'از این پس پاسخ‌ها با جستجوی منابع معتبر وب تقویت می‌شوند.' if new_state else 'پاسخ‌ها بدون وب‌سرچ و صرفاً با دانش درونی مدل داده می‌شوند.'}"
    )

# --- Callbacks ---

@router.callback_query(F.data == "menu:main")
async def cb_main_menu(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    current_model = user.get("selected_model", "gemini")
    keyboard = get_main_menu_keyboard(web_search_enabled=bool(user.get("web_search_enabled", 0)), current_model=current_model, is_admin=(call.from_user.id in ADMIN_IDS))
    try:
        if call.message.text:
            await call.message.edit_text(
                WELCOME_TEXT,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await call.message.answer(
                WELCOME_TEXT,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
    except Exception:
        await call.message.answer(
            WELCOME_TEXT,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    await call.answer()

MODEL_NAMES = {m["id"]: m.get("name", m["id"]) for m in AVAILABLE_MODELS}
MODEL_NAMES.update({
    "claude-fable-5.1": "🌟 Claude Fable 5.1",
    "claude-fable-5": "🌟 Claude Fable 5",
    "claude-opus-5.5": "💎 Claude Opus 5.5",
    "claude-opus-5": "💎 Claude Opus 5",
    "claude-opus-4.8": "💎 Claude Opus 4.8",
    "claude-opus-4.7": "💎 Claude Opus 4.7",
    "claude-opus-4.6": "💎 Claude Opus 4.6",
    "claude-mythos-preview": "🔮 Claude Mythos Preview",
    "gpt-5.6-sol": "☀️ GPT-5.6 Sol",
    "gpt-5.6-terra": "🌍 GPT-5.6 Terra",
    "gpt-5.6-luna": "🌙 GPT-5.6 Luna",
    "gpt-5.5-pro": "🚀 GPT-5.5 Pro",
    "deepseek-v4-pro-max": "🧠 DeepSeek V4 Pro Max",
    "claude-sonnet-5": "🖋️ Claude Sonnet 5",
    "gemini-3.7-flash": "⚡ Gemini 3.7 Flash",
    "Atria-Dawn-Preview": "🌅 Atria Dawn (256K)",
    "deepseek-reasoner": "🧠 DeepSeek R1",
})

@router.callback_query(F.data == "menu:models")
async def cb_models_menu(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    current_model = user.get("selected_model", "gemini")
    is_vip_or_admin = (call.from_user.id in ADMIN_IDS) or await db.is_user_vip(call.from_user.id)
    model_name = MODEL_NAMES.get(current_model, current_model)
    user_status = "کاربر ویژه (VIP) ⭐" if is_vip_or_admin else "کاربر عادی ⚪"
    text = (
        "🤖 <b>مرکز انتخاب مدل‌های هوش مصنوعی</b>\n\n"
        f"📍 <b>مدل فعال شما:</b> <code>{model_name}</code>\n"
        f"💎 <b>وضعیت اشتراک:</b> <code>{user_status}</code>\n\n"
        "🌟 <b>مدل‌های برتر و پیشنهادی:</b>\n"
        "برای تغییر مدل، یکی از گزینه‌های زیر را انتخاب نمایید. جهت مرور تمامی ۳۳ مدل، دکمهٔ <b>دسته‌بندی جامع</b> را لمس کنید.\n\n"
        "📌 <b>راهنما:</b>\n"
        "▫️ علامت 🔒 مخصوص کاربران دارای اشتراک Star VIP است.\n"
        "▫️ تیک سبز ✅ مدل فعال فعلی شما را مشخص می‌کند."
    )
    markup = get_models_keyboard(current_model, is_vip_or_admin=is_vip_or_admin)
    try:
        if call.message.text:
            await call.message.edit_text(
                text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            await call.message.answer(
                text,
                reply_markup=markup,
                parse_mode="HTML"
            )
    except Exception:
        try:
            await call.message.edit_text(text, reply_markup=markup, parse_mode=None)
        except Exception:
            await call.message.answer(text, reply_markup=markup, parse_mode=None)
    await call.answer()


@router.callback_query(F.data == "menu:model_categories")
async def cb_model_categories(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    current_model = user.get("selected_model", "gemini")
    model_name = MODEL_NAMES.get(current_model, current_model)
    text = (
        "🗂 <b>دسته‌بندی جامع مدل‌های هوش مصنوعی</b>\n\n"
        f"📍 <b>مدل فعال فعلی:</b> <code>{model_name}</code>\n\n"
        "📑 <b>انتخاب شاخه تخصصی:</b>\n"
        "جهت مشاهده و انتخاب مدل‌ها، یکی از دسته‌بندی‌های زیر را لمس نمایید:"
    )
    markup = get_model_categories_keyboard(current_model)
    try:
        if call.message.text:
            await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            await call.message.answer(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        try:
            await call.message.edit_text(text, reply_markup=markup, parse_mode=None)
        except Exception:
            await call.message.answer(text, reply_markup=markup, parse_mode=None)
    await call.answer()


@router.callback_query(F.data.startswith("mod_cat:"))
async def cb_model_category(call: CallbackQuery):
    category = call.data.split("mod_cat:")[1]
    user = await db.get_or_create_user(call.from_user.id)
    current_model = user.get("selected_model", "gemini")
    user_id = call.from_user.id
    is_vip_or_admin = (user_id in ADMIN_IDS) or await db.is_user_vip(user_id)

    cat_info = MODEL_CATEGORIES.get(category, MODEL_CATEGORIES["star"])
    model_name = MODEL_NAMES.get(current_model, current_model)
    text = (
        f"📂 <b>{cat_info['title']}</b>\n\n"
        f"📍 <b>مدل فعال فعلی:</b> <code>{model_name}</code>\n\n"
        "📋 <b>فهرست مدل‌ها:</b>\n"
        "مدل مورد نظر خود را از لیست زیر انتخاب فرمایید:\n\n"
        "💡 <b>راهنما:</b> علامت 🔒 نشان‌دهنده مدل‌های اختصاصی اشتراک Star VIP است."
    )
    markup = get_category_models_keyboard(category, current_model, is_vip_or_admin)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        try:
            await call.message.edit_text(text, reply_markup=markup, parse_mode=None)
        except Exception:
            await call.message.answer(text, reply_markup=markup, parse_mode=None)
    await call.answer()


@router.callback_query(F.data.startswith("set_model:"))
async def cb_set_model(call: CallbackQuery):
    model_id = call.data.split("set_model:")[1]
    user_id = call.from_user.id
    is_admin = (user_id in ADMIN_IDS)
    is_vip = await db.is_user_vip(user_id)

    # Check Telegram Stars requirement
    if model_id in STAR_LOCKED_MODELS and not (is_admin or is_vip):
        # Redirect to paywall
        from app.bot.handlers.account import cb_req_star_paywall
        await cb_req_star_paywall(call)
        return

    await db.update_user_model(user_id, model_id)
    user = await db.get_or_create_user(user_id)
    web_search = bool(user.get("web_search_enabled", 0))
    model_name = MODEL_NAMES.get(model_id, model_id)
    caps = get_model_capabilities(model_id)

    if caps.get("is_image_studio"):
        text = (
            "🍌 <b>استودیوی ادیت و ساخت عکس فعال شد</b>\n\n"
            f"✅ <b>مدل فعال:</b> <code>{model_name}</code>\n\n"
            "🎨 <b>راهنما:</b> پرامپت متنی برای ساخت عکس، یا تصویر خود را برای ادیت بفرستید.\n"
            "💬 برای چت با هوش مصنوعی، دکمه <b>«💬 گفتگوی جدید»</b> را بزنید."
        )
    elif caps.get("is_video_studio"):
        text = (
            "🎬 <b>استودیوی تولید ویدیو فعال شد</b>\n\n"
            f"✅ <b>مدل فعال:</b> <code>{model_name}</code>\n\n"
            "🎥 <b>راهنما:</b> پرامپت متنی یا عکس خود را جهت ساخت ویدیو بفرستید.\n"
            "💬 برای چت با هوش مصنوعی، دکمه <b>«💬 گفتگوی جدید»</b> را بزنید."
        )
    else:
        text = (
            "🤖 <b>مدل هوش مصنوعی با موفقیت تنظیم شد</b>\n\n"
            f"✅ <b>مدل فعال جدید:</b> <code>{model_name}</code>\n\n"
            "💬 <b>وضعیت:</b> آماده پاسخگویی به پیام‌ها، پرسش‌ها یا تحلیل اسناد و عکس‌ها.\n"
            "پیام یا فایل/عکس خود را ارسال فرمایید."
        )

    try:
        await call.message.edit_text(
            text,
            reply_markup=get_model_features_keyboard(model_id, web_search_enabled=web_search),
            parse_mode="HTML"
        )
    except Exception:
        await call.message.answer(
            text,
            reply_markup=get_model_features_keyboard(model_id, web_search_enabled=web_search),
            parse_mode="HTML"
        )
    await call.answer(f"مدل به {model_name} تنظیم شد ✅", show_alert=False)


@router.callback_query(F.data == "action:toggle_search")
async def cb_toggle_search(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    current_model = user.get("selected_model", "gemini")
    caps = get_model_capabilities(current_model)
    if not caps["supports_web_search"]:
        await call.answer(
            f"⚠️ مدل «{caps['name']}» از وب سرچ پشتیبانی نمی‌کند.\nبرای استفاده از وب سرچ مدلی مانند Gemini 3.7 Flash یا GPT-5.6 را انتخاب نمایید.",
            show_alert=True
        )
        return

    new_state = await db.toggle_web_search(call.from_user.id)
    await call.message.edit_reply_markup(
        reply_markup=get_main_menu_keyboard(web_search_enabled=new_state, current_model=current_model, is_admin=(call.from_user.id in ADMIN_IDS))
    )
    status_label = "فعال شد ✅" if new_state else "غیرفعال شد ❌"
    await call.answer(f"وب سرچ {status_label}", show_alert=False)


@router.callback_query(F.data == "action:clear_chat")
async def cb_clear_chat(call: CallbackQuery, state: FSMContext = None):
    user_id = call.from_user.id
    if state:
        await state.clear()
    await db.clear_chat_history(user_id)
    user = await db.get_or_create_user(user_id)
    current_model = user.get("selected_model", "gemini")
    caps = get_model_capabilities(current_model)

    # If user was in an image or video studio, switch back to conversational LLM
    if caps.get("is_image_studio") or caps.get("is_video_studio"):
        chat_model = await db.get_user_chat_model(user_id)
        await db.update_user_model(user_id, chat_model)
        current_model = chat_model
        user["selected_model"] = chat_model

    web_search = bool(user.get("web_search_enabled", 0))
    model_name = MODEL_NAMES.get(current_model, current_model)
    text = (
        f"💬 **گفتگوی جدید آغاز شد!**\n\n"
        f"🤖 **مدل فعال: {model_name}**\n\n"
        "پیام متنی، پرسش، عکس یا فایل مورد نظر خود را جهت گفتگو و تحلیل هوشمند ارسال فرمایید."
    )
    await call.message.answer(
        text,
        reply_markup=get_model_features_keyboard(current_model, web_search_enabled=web_search),
        parse_mode="Markdown"
    )
    await call.answer("💬 گفتگوی جدید آغاز شد!", show_alert=False)

@router.callback_query(F.data == "menu:help")
async def cb_help(call: CallbackQuery):
    user = await db.get_or_create_user(call.from_user.id)
    help_text = """📖 **راهنمای استفاده از قابلیت‌های ربات:**

1️⃣ **گفتگو با هوش مصنوعی:**
هر سوال متنی، ریاضی، برنامه‌نویسی یا ترجمه دارید بفرستید.

2️⃣ **استدلال عمیق (Atria Dawn & DeepSeek R1):**
اگر مدل‌های استدلالی مانند Atria Dawn Preview یا DeepSeek R1 را انتخاب کنید، فرآیند گام‌به‌گام فکر کردن مدل (`Thinking Process`) نمایش داده می‌شود.

3️⃣ **تحلیل تصاویر و اسناد (Vision):**
هر عکسی را مستقیماً برای ربات بفرستید (با یا بدون کپشن) تا مدل‌های بینایی ماشین آن را تحلیل، استخراج متن و تشریح کنند.

4️⃣ **وب‌سرچ زنده:**
با روشن کردن وب‌سرچ، هوش مصنوعی قبل از پاسخ، وب را برای اخبار و اطلاعات تازه جستجو می‌کند."""
    await call.message.edit_text(
        help_text,
        reply_markup=get_main_menu_keyboard(web_search_enabled=bool(user.get("web_search_enabled", 0)), is_admin=(call.from_user.id in ADMIN_IDS)),
        parse_mode="Markdown"
    )
    await call.answer()
