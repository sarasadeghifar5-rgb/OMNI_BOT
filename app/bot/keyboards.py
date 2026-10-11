from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from app.config import AVAILABLE_MODELS, STAR_LOCKED_MODELS, get_model_capabilities, format_model_card
from app.bot.config import CUSTOM_EMOJI_NEW_CHAT, CUSTOM_EMOJI_WEB_SEARCH

def get_main_menu_keyboard(web_search_enabled: bool = False, current_model: str = "gemini", is_admin: bool = False) -> InlineKeyboardMarkup:
    """Main dashboard inline keyboard adapting dynamically to current model."""
    caps = get_model_capabilities(current_model)
    if caps["supports_web_search"]:
        search_icon = "✅" if web_search_enabled else "❌"
    else:
        search_icon = "❌"

    search_btn_text = f"🌐 وب سرچ: {search_icon}"
    search_btn_kwargs = {"text": search_btn_text, "callback_data": "action:toggle_search"}

    buttons = []
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="👑 ورود به پنل مدیریت ادمین", callback_data="admin:main")
        ])

    buttons.extend([
        [
            InlineKeyboardButton(text="🍌 ادیت عکس نانو بنانا", callback_data="menu:gpt_image"),
            InlineKeyboardButton(text="🎬 استودیو ویدیو نانو", callback_data="video_menu"),
        ],
        [
            InlineKeyboardButton(text="🤖 انتخاب مدل هوش مصنوعی", callback_data="menu:models"),
        ],
        [
            InlineKeyboardButton(text="👤 حساب کاربری و اشتراک", callback_data="act:profile"),
            InlineKeyboardButton(text="🛒 خرید سرویس و پلن‌ها", callback_data="act:buy_service"),
        ],
        [
            InlineKeyboardButton(text="🎁 گردونه هدیه روزانه", callback_data="act:daily_gift"),
            InlineKeyboardButton(text="🔗 لینک دعوت و پاداش", callback_data="act:my_invite"),
        ],
        [
            InlineKeyboardButton(text="🛠️ ابزارهای کاربردی و سرگرمی", callback_data="menu:tools"),
            InlineKeyboardButton(text="🎙️ تبدیل صدا (TTS)", callback_data="menu:tts"),
        ],
        [
            InlineKeyboardButton(**search_btn_kwargs),
            InlineKeyboardButton(text="🌍 تغییر منطقه سرور", callback_data="act:change_region"),
        ],
        [
            InlineKeyboardButton(text="💬 گفتگوی جدید", callback_data="action:clear_chat"),
            InlineKeyboardButton(text="❓ راهنما و سوالات متداول", callback_data="menu:faq"),
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


from app.config import AVAILABLE_MODELS, STAR_LOCKED_MODELS

# Categorized Model Definitions
MODEL_CATEGORIES = {
    "star": {
        "title": "🌟 مدل‌های اختصاصی استار تلگرام (Star VIP)",
        "icon": "🌟",
        "models": [
            ("claude-fable-5.1", "🌟 Claude Fable 5.1", False),
            ("claude-fable-5", "🌟 Claude Fable 5", False),
            ("claude-opus-5.5", "💎 Claude Opus 5.5", False),
            ("claude-opus-5", "💎 Claude Opus 5", False),
            ("claude-opus-4.8", "💎 Claude Opus 4.8", False),
            ("claude-mythos-preview", "🔮 Claude Mythos Preview", False),
            ("gpt-5.6-sol", "☀️ GPT-5.6 Sol", False),
            ("gpt-5.5-pro", "🚀 GPT-5.5 Pro", False),
            ("deepseek-v4-pro-max", "🧠 DeepSeek V4 Pro Max", False),
        ]
    },
    "claude": {
        "title": "🖋️ خانواده Claude Anthropic",
        "icon": "🖋️",
        "models": [
            ("claude-fable-5.1", "🌟 Claude Fable 5.1", False),
            ("claude-fable-5", "🌟 Claude Fable 5", False),
            ("claude-opus-5.5", "💎 Claude Opus 5.5", False),
            ("claude-opus-5", "💎 Claude Opus 5", False),
            ("claude-opus-4.8", "💎 Claude Opus 4.8", False),
            ("claude-opus-4.7", "Claude Opus 4.7", False),
            ("claude-opus-4.6", "Claude Opus 4.6", False),
            ("claude-mythos-preview", "🔮 Claude Mythos Preview", False),
            ("claude-sonnet-5", "🖋️ Claude Sonnet 5", False),
            ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", False),
        ]
    },
    "openai": {
        "title": "⚡ خانواده OpenAI و GPT",
        "icon": "⚡",
        "models": [
            ("gpt-5.6-sol", "☀️ GPT-5.6 Sol", False),
            ("gpt-5.6-terra", "🌍 GPT-5.6 Terra", False),
            ("gpt-5.6-luna", "🌙 GPT-5.6 Luna", False),
            ("gpt-5.5-pro", "🚀 GPT-5.5 Pro", False),
            ("gpt-5.5", "⚡ GPT-5.5", False),
            ("gpt-4o", "✨ GPT-4o (Omni)", False),
            ("gpt-4o-mini", "GPT-4o Mini", False),
            ("o1", "🧠 OpenAI o1", False),
        ]
    },
    "deepseek": {
        "title": "🧠 خانواده DeepSeek و استدلال",
        "icon": "🧠",
        "models": [
            ("deepseek-v4-pro-max", "🧠 DeepSeek V4 Pro Max", False),
            ("deepseek-v4-pro-0813", "🧠 DeepSeek V4 Pro", False),
            ("deepseek-v4-flash-0731", "⚡ DeepSeek V4 Flash", False),
            ("deepseek-reasoner", "DeepSeek R1 (Reasoner)", False),
            ("deepseek-chat", "DeepSeek V3", False),
        ]
    },
    "gemini": {
        "title": "🌐 خانواده Google Gemini",
        "icon": "🌐",
        "models": [
            ("gemini-3.7-flash", "⚡ Gemini 3.7 Flash", False),
            ("gemini-3.6-flash", "⚡ Gemini 3.6 Flash", False),
            ("gemini-3.1-pro", "🌐 Gemini 3.1 Pro", False),
            ("gemini", "Google Gemini (پیش‌فرض)", False),
        ]
    },
    "other": {
        "title": "🛸 گروک، کیو‌ون، کیمی، جی‌ال‌ام و سید",
        "icon": "🛸",
        "models": [
            ("grok-4.6", "🛸 xAI Grok 4.6", False),
            ("grok-4.5", "🛸 xAI Grok 4.5", False),
            ("grok-2-vision-1212", "Grok 2 Vision", False),
            ("qwen3.8-max", "👑 Qwen 3.8 Max", False),
            ("qwen3.8-27b", "⚡ Qwen 3.8 27B", False),
            ("qwen3.7-max", "👑 Qwen 3.7 Max", False),
            ("kimi-k3", "🌙 Moonshot Kimi K3", False),
            ("kimi-k2.6", "🌙 Moonshot Kimi K2.6", False),
            ("glm-5.3", "🇨🇳 GLM 5.3", False),
            ("glm-5.2", "🇨🇳 GLM 5.2", False),
            ("seed-2.1-turbo", "🌱 Seed 2.1 Turbo", False),
            ("seed-2.1-pro", "🌱 Seed 2.1 Pro", False),
            ("muse-spark-1.1", "✨ Muse Spark 1.1", False),
            ("Atria-Dawn-Preview", "🌅 Atria Dawn (256K)", False),
        ]
    },
    "nano": {
        "title": "🍌 استودیو عکس و ویدیوی نانو بنانا",
        "icon": "🍌",
        "models": [
            ("agnes-image-2.5-flash", "🍌 ادیت عکس نانو بنانا", False),
            ("agnes-video-2.5", "🎬 استودیو ویدیو نانو", False),
            ("agnes-2.5-flash", "🧠 استدلال عمیق نانو", False),
        ]
    },
    "free": {
        "title": "🆓 مدل‌های کاملاً رایگان و سبک",
        "icon": "🆓",
        "models": [
            ("nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 120B (رایگان)", False),
            ("nex-agi/nex-n2.5-pro:free", "Nex Pro (رایگان)", False),
            ("gemma-2-2b", "🎈 Google Gemma 2 2B", False),
            ("glm-4v-flash", "👁️ GLM-4V Flash (رایگان)", False),
            ("glm-4-flash", "⚡ GLM-4 Flash (رایگان)", False),
        ]
    }
}


def get_model_categories_keyboard(current_model: str = "gemini") -> InlineKeyboardMarkup:
    """Clean, spacious, uncrowded category picker (1 full-width button per row)."""
    buttons = [
        [InlineKeyboardButton(text="⭐ مدل‌های پرچمدار استار (Star VIP)", callback_data="mod_cat:star")],
        [InlineKeyboardButton(text="🖋️ خانواده کلاود (Claude Anthropic)", callback_data="mod_cat:claude")],
        [InlineKeyboardButton(text="⚡ خانواده اوپن‌ای‌آی (OpenAI GPT)", callback_data="mod_cat:openai")],
        [InlineKeyboardButton(text="🌐 خانواده گوگل جمینای (Google Gemini)", callback_data="mod_cat:gemini")],
        [InlineKeyboardButton(text="🧠 خانواده دیپ‌سیک و استدلال (DeepSeek)", callback_data="mod_cat:deepseek")],
        [InlineKeyboardButton(text="🛸 سایر مدل‌ها (Grok, Qwen, Kimi, GLM)", callback_data="mod_cat:other")],
        [InlineKeyboardButton(text="🍌 استودیو عکس و ویدیو (Nano Banana)", callback_data="mod_cat:nano")],
        [InlineKeyboardButton(text="🆓 مدل‌های کاملاً رایگان (Free Tier)", callback_data="mod_cat:free")],
        [
            InlineKeyboardButton(text="🤖 مدل‌های برگزیده", callback_data="menu:models"),
            InlineKeyboardButton(text="💬 گفتگوی جدید", callback_data="action:clear_chat")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_category_models_keyboard(category: str, current_model: str = "gemini", is_vip_or_admin: bool = False) -> InlineKeyboardMarkup:
    """List of models inside a specific category (clean 1-column layout without truncation)."""
    cat_data = MODEL_CATEGORIES.get(category, MODEL_CATEGORIES["star"])
    models = cat_data["models"]

    buttons = []
    for model_id, label, is_star_req in models:
        is_selected = (current_model == model_id)
        prefix = "✅ " if is_selected else "▫️ "
        btn_text = f"{prefix}{label}"
        cb_data = f"set_model:{model_id}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])

    buttons.append([
        InlineKeyboardButton(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="menu:model_categories"),
        InlineKeyboardButton(text="🤖 مدل‌های برگزیده", callback_data="menu:models")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_models_keyboard(current_model: str = "gemini-3.7-flash", is_vip_or_admin: bool = False) -> InlineKeyboardMarkup:
    """Prominently displays the top flagship models directly, plus category navigation."""
    featured_models = [
        ("gemini-3.7-flash", "⚡ Gemini 3.7 Flash", False),
        ("claude-sonnet-5", "🖋️ Claude Sonnet 5", False),
        ("claude-opus-5.5", "💎 Claude Opus 5.5", False),
        ("gpt-5.5", "⚡ GPT-5.5 (Flagship)", False),
        ("gpt-5.6-sol", "☀️ GPT-5.6 Sol", False),
        ("deepseek-v4-pro-max", "🧠 DeepSeek V4 Pro Max", False),
        ("deepseek-v4-flash-0731", "⚡ DeepSeek Flash", False),
        ("Atria-Dawn-Preview", "🌅 Atria Dawn (256K)", False),
        ("agnes-2.5-flash", "🧠 Nano Reasoner", False),
        ("grok-4.6", "🛸 xAI Grok 4.6", False),
    ]

    buttons = []
    row = []
    for model_id, label, is_star_req in featured_models:
        is_selected = (current_model == model_id)
        prefix = "✅ " if is_selected else ""
        btn_text = f"{prefix}{label}"
        cb_data = f"set_model:{model_id}"

        row.append(InlineKeyboardButton(text=btn_text, callback_data=cb_data))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="📂 دسته‌بندی و لیست کامل تمام مدل‌ها (۳۳ مدل جدید)", callback_data="menu:model_categories")
    ])
    buttons.append([
        InlineKeyboardButton(text="⭐ خرید اشتراک استار تلگرام (VIP)", callback_data="act:buy_service")
    ])
    buttons.append([
        InlineKeyboardButton(text="💬 گفتگوی جدید", callback_data="action:clear_chat"),
        InlineKeyboardButton(text="🔙 منوی اصلی", callback_data="menu:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_star_paywall_keyboard(model_id: str) -> InlineKeyboardMarkup:
    """Paywall prompt when attempting to use a Star-locked model."""
    buttons = [
        [
            InlineKeyboardButton(text="⭐ خرید اشتراک ۱ روزه (۲۵ استار)", callback_data="buy_stars:vip_1d"),
        ],
        [
            InlineKeyboardButton(text="🌟 خرید اشتراک ۳۰ روزه VIP (۱۲۰ استار)", callback_data="buy_stars:vip_30d"),
        ],
        [
            InlineKeyboardButton(text="👑 خرید اشتراک دائمی VIP (۳۹۰ استار)", callback_data="buy_stars:vip_life"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به انتخاب مدل", callback_data="menu:models"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_stars_payment_keyboard() -> InlineKeyboardMarkup:
    """Stars package selection in the shop."""
    buttons = [
        [
            InlineKeyboardButton(text="⭐ اشتراک ۱ روزه VIP (۲۵ استار)", callback_data="buy_stars:vip_1d"),
        ],
        [
            InlineKeyboardButton(text="🌟 اشتراک ۳۰ روزه طلایی (۱۲۰ استار)", callback_data="buy_stars:vip_30d"),
        ],
        [
            InlineKeyboardButton(text="👑 اشتراک مادام‌العمر الماس (۳۹۰ استار)", callback_data="buy_stars:vip_life"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به حساب کاربری", callback_data="act:profile"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_channel_force_join_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    """Channel lock prompt keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="📢 عضویت در کانال رسمی", url=channel_link),
        ],
        [
            InlineKeyboardButton(text="🔄 بررسی عضویت و ورود به ربات", callback_data="check_channel_join"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================================================================
# Admin Panel Keyboards
# =========================================================================

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Main administrative dashboard keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="📢 مدیریت قفل کانال", callback_data="admin:channel"),
            InlineKeyboardButton(text="📊 آمار تفصیلی و مالی", callback_data="admin:stats"),
        ],
        [
            InlineKeyboardButton(text="👤 مدیریت و جستجوی کاربر", callback_data="admin:users"),
            InlineKeyboardButton(text="✉️ ارسال پیام همگانی", callback_data="admin:broadcast"),
        ],
        [
            InlineKeyboardButton(text="🤖 مدل‌ها و CodeCraft API", callback_data="admin:models"),
            InlineKeyboardButton(text="⭐ تنظیمات و قیمت استار", callback_data="admin:stars"),
        ],
        [
            InlineKeyboardButton(text="🔑 مدیریت استخر کلیدها (Key Pools)", callback_data="admin:key_pools"),
            InlineKeyboardButton(text="🔄 آزادسازی قفل سرور", callback_data="admin:unlock"),
        ],
        [
            InlineKeyboardButton(text="👥 مدیریت و لیست مدیران ربات (Admins)", callback_data="admin:admins_list"),
        ],
        [
            InlineKeyboardButton(text="🔙 خروج به منوی اصلی ربات", callback_data="menu:main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_key_pools_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for managing API Key Pools (CodeCraft, Agnes, Atria)."""
    buttons = [
        [
            InlineKeyboardButton(text="🔄 تست و پینگ زنده تمامی کلیدها", callback_data="admin:test_all_keys"),
        ],
        [
            InlineKeyboardButton(text="➕ افزودن کلید به CodeCraft", callback_data="admin:add_key_codecraft"),
            InlineKeyboardButton(text="➕ افزودن کلید به Atria", callback_data="admin:add_key_atria"),
        ],
        [
            InlineKeyboardButton(text="➕ افزودن کلید به Agnes", callback_data="admin:add_key_agnes"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به پنل ادمین", callback_data="admin:main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_channel_keyboard(enabled: bool, channel_id: str, channel_link: str) -> InlineKeyboardMarkup:
    """Channel lock settings keyboard."""
    toggle_text = "🔴 خاموش کردن قفل کانال" if enabled else "🟢 روشن کردن قفل کانال"
    buttons = [
        [
            InlineKeyboardButton(text=toggle_text, callback_data="admin:toggle_channel"),
        ],
        [
            InlineKeyboardButton(text="✏️ تنظیم آیدی/یوزرنیم کانال", callback_data="admin:set_channel_id"),
        ],
        [
            InlineKeyboardButton(text="🔗 تنظیم لینک جوین کانال", callback_data="admin:set_channel_link"),
        ],
        [
            InlineKeyboardButton(text="🔍 بررسی دسترسی ادمین ربات در کانال", callback_data="admin:test_channel"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به پنل ادمین", callback_data="admin:main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_user_keyboard(target_user_id: int, is_vip: bool, is_banned: bool) -> InlineKeyboardMarkup:
    """Actions on a specific user."""
    ban_text = "✅ رفع مسدودسازی (آن‌بن)" if is_banned else "🚫 مسدودسازی کاربر (بن)"
    vip_btn = [
        InlineKeyboardButton(text="🌟 اعطای VIP (۳۰ روزه)", callback_data=f"admin:grant_vip_30:{target_user_id}"),
        InlineKeyboardButton(text="💎 اعطای VIP دائمی", callback_data=f"admin:grant_vip_life:{target_user_id}")
    ]
    revoke_btn = [
        InlineKeyboardButton(text="❌ لغو اشتراک VIP", callback_data=f"admin:revoke_vip:{target_user_id}")
    ] if is_vip else []

    buttons = [
        vip_btn,
    ]
    if revoke_btn:
        buttons.append(revoke_btn)

    buttons.append([
        InlineKeyboardButton(text="➕ شارژ ۵۰ توکن هدیه", callback_data=f"admin:add_tokens:{target_user_id}:50"),
        InlineKeyboardButton(text=ban_text, callback_data=f"admin:toggle_ban:{target_user_id}"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 بازگشت به مدیریت کاربران", callback_data="admin:users"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_image_studio_keyboard(ratio: str = "1:1", size: str = "1K") -> InlineKeyboardMarkup:
    """Redirect to GPT image studio keyboard."""
    return get_gpt_image_menu_keyboard(ratio=ratio, size=size)


def get_gpt_image_menu_keyboard(ratio: str = "1:1", size: str = "1K") -> InlineKeyboardMarkup:
    """Dedicated menu for GPT Image Generation & Editing Studio (Agnes AI)."""
    ratio_labels = {
        "1:1": "⏹️ 1:1 مربعی",
        "16:9": "🖥️ 16:9 عریض",
        "9:16": "📱 9:16 استوری",
        "4:3": "🖼️ 4:3 افقی",
        "3:4": "📱 3:4 عمودی",
        "2:3": "📸 2:3 پرتره",
        "3:2": "🌄 3:2 لندسکیپ",
        "21:9": "🎬 21:9 سینمایی",
    }
    ratio_display = ratio_labels.get(ratio, f"📐 {ratio}")
    buttons = [
        [
            InlineKeyboardButton(text="🎨 تولید عکس جدید با متن (Text-to-Image)", callback_data="gpt_img:new_text"),
        ],
        [
            InlineKeyboardButton(text="🖌️ ادیت و تغییر عکس ارسالی (Image-to-Image)", callback_data="gpt_img:new_edit"),
        ],
        [
            InlineKeyboardButton(text=f"📐 نسبت ابعاد: {ratio_display}", callback_data="gpt_img:select_ratio"),
            InlineKeyboardButton(text=f"📏 کیفیت: {size}", callback_data="gpt_img:select_size"),
        ],
        [
            InlineKeyboardButton(text="💬 گفتگوی جدید (ورود به چت هوش مصنوعی)", callback_data="action:clear_chat"),
        ],
        [
            InlineKeyboardButton(text="🔙 منوی اصلی", callback_data="cb_main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_aspect_ratio_keyboard(current_ratio: str = "1:1") -> InlineKeyboardMarkup:
    """Aspect ratio selection keyboard."""
    ratios = [
        ("1:1", "⏹️ 1:1 (مربعی / پست اینستاگرام)"),
        ("16:9", "🖥️ 16:9 (عریض / یوتیوب و دسکتاپ)"),
        ("9:16", "📱 9:16 (عمودی / استوری و ریلز)"),
        ("4:3", "🖼️ 4:3 (افقی استاندارد)"),
        ("3:4", "📱 3:4 (عمودی استاندارد)"),
        ("3:2", "🌄 3:2 (افقی عکاسی کلاسیک)"),
        ("2:3", "📸 2:3 (پرتره عکاسی)"),
        ("21:9", "🎬 21:9 (فوق عریض سینمایی)"),
    ]
    buttons = []
    for r_val, r_label in ratios:
        mark = "✅ " if r_val == current_ratio else ""
        buttons.append([InlineKeyboardButton(text=f"{mark}{r_label}", callback_data=f"gpt_img:set_ratio:{r_val}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به استودیو عکس", callback_data="menu:gpt_image")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_resolution_keyboard(current_size: str = "1K", is_vip: bool = False) -> InlineKeyboardMarkup:
    """Resolution tier selection keyboard (2K, 3K, 4K unlocked only via Telegram Stars)."""
    sizes = [
        ("1K", "⚡ 1K (کیفیت استاندارد - رایگان)", False),
        ("2K", "💎 2K (کیفیت بالا - استار تلگرام ⭐)", True),
        ("3K", "✨ 3K (فوق‌العاده با کیفیت - استار تلگرام ⭐)", True),
        ("4K", "🌟 4K (حداکثر اولترا HD - استار تلگرام ⭐)", True),
    ]
    buttons = []
    for s_val, s_label, req_vip in sizes:
        mark = "✅ " if s_val == current_size else ""
        if req_vip and not is_vip:
            label = f"🔒 {s_val} (نیازمند استار تلگرام ⭐)"
        else:
            label = f"{mark}{s_label}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"gpt_img:set_size:{s_val}")])

    if not is_vip:
        buttons.append([
            InlineKeyboardButton(text="⭐ خرید اشتراک با استار تلگرام (VIP)", callback_data="act:buy_service")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به استودیو عکس", callback_data="menu:gpt_image")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_image_action_keyboard(can_edit: bool = True, can_regen: bool = True) -> InlineKeyboardMarkup:
    """Action buttons shown under generated/edited images."""
    buttons = []
    row1 = []
    if can_edit:
        row1.append(InlineKeyboardButton(text="🖌️ ادیت همین تصویر", callback_data="gpt_img:edit_last"))
    if can_regen:
        row1.append(InlineKeyboardButton(text="🔄 تولید مجدد", callback_data="gpt_img:regen_last"))
    if row1:
        buttons.append(row1)
    buttons.append([
        InlineKeyboardButton(text="📁 فایل باکیفیت اصلی (Document)", callback_data="gpt_img:send_doc")
    ])
    buttons.append([
        InlineKeyboardButton(text="🎨 عکس متنی جدید", callback_data="gpt_img:new_text"),
        InlineKeyboardButton(text="⚙️ منوی استودیو", callback_data="menu:gpt_image")
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 منوی اصلی ربات", callback_data="menu:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tools_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for everyday utility & lifestyle tools."""
    buttons = [
        [
            InlineKeyboardButton(text="🍌 ادیت عکس نانو بنانا", callback_data="menu:gpt_image"),
        ],
        [
            InlineKeyboardButton(text="💰 قیمت زنده طلا، سکه، دلار و ارز دیجیتال", callback_data="tool:price"),
        ],
        [
            InlineKeyboardButton(text="🔮 فال حافظ با تفسیر هوش مصنوعی", callback_data="tool:faal"),
        ],
        [
            InlineKeyboardButton(text="🎂 محاسبه سن، سال تولد و طالع", callback_data="tool:age"),
        ],
        [
            InlineKeyboardButton(text="📏 محاسبه و مقایسه اختلاف قد", callback_data="tool:height"),
        ],
        [
            InlineKeyboardButton(text="⚖️ تبدیل وزن و شاخص توده بدنی (BMI)", callback_data="tool:bmi"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="menu:main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_faq_categories_keyboard() -> InlineKeyboardMarkup:
    """FAQ category picker."""
    buttons = [
        [
            InlineKeyboardButton(text="💻 برنامه‌نویسی و وب", callback_data="faq_cat:coding"),
            InlineKeyboardButton(text="📝 نگارش، مقاله و رزومه", callback_data="faq_cat:writing"),
        ],
        [
            InlineKeyboardButton(text="💡 کسب‌وکار و درآمدزایی", callback_data="faq_cat:business"),
            InlineKeyboardButton(text="🇬🇧 یادگیری زبان انگلیسی", callback_data="faq_cat:english"),
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="menu:main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_faq_questions_keyboard(category: str) -> InlineKeyboardMarkup:
    """List of popular ready prompts per category."""
    questions = {
        "coding": [
            ("یک اسکریپت کاربردی پایتون برای خودکارسازی بنویس", "faq_q:py_script"),
            ("چگونه خطاهای کدهایم را دیباگ و بهینه‌سازی کنم؟", "faq_q:debug_tips"),
            ("بهترین نقشه راه یادگیری هوش مصنوعی در سال جدید", "faq_q:ai_roadmap"),
        ],
        "writing": [
            ("یک ایمیل کاری و اداری بسیار شیک و رسمی بنویس", "faq_q:formal_email"),
            ("ساختار استاندارد یک رزومه انگلیسی بین‌المللی", "faq_q:resume_guide"),
            ("چگونه مقدمه و چکیده یک مقاله علمی را بنویسم؟", "faq_q:essay_intro"),
        ],
        "business": [
            ("۳ ایده پولساز واقعی با هوش مصنوعی بدون سرمایه", "faq_q:ai_biz_ideas"),
            ("یک متن تبلیغاتی فوق‌العاده جذاب برای اینستاگرام", "faq_q:insta_caption"),
            ("استراتژی قیمت‌گذاری خدمات و افزایش مشتریان", "faq_q:pricing_strat"),
        ],
        "english": [
            ("۲۰ اصطلاح کاربردی روزمره در مکالمه انگلیسی", "faq_q:english_idioms"),
            ("روش سریع تقویت مهارت اسپیکینگ (Speaking)", "faq_q:speaking_tips"),
            ("اصلاح گرامر و بازنویسی جملات انگلیسی با لحن بومی", "faq_q:grammar_fix"),
        ]
    }

    q_list = questions.get(category, [])
    buttons = []
    for text, cb in q_list:
        buttons.append([InlineKeyboardButton(text=f"▫️ {text}", callback_data=cb)])

    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به دسته‌بندی سوالات", callback_data="menu:faq")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_model_features_keyboard(
    model_id: str = "gemini",
    web_search_enabled: bool = False,
    is_reasoning: bool = False
) -> InlineKeyboardMarkup:
    """
    Dynamic keyboard showing strictly the REAL capabilities of the selected model.
    """
    caps = get_model_capabilities(model_id)
    buttons = []

    # 1. Image Studio Models (Banana / Agnes Image)
    if caps["is_image_studio"]:
        buttons.append([
            InlineKeyboardButton(text="📐 نسبت ابعاد (Aspect Ratio)", callback_data="gpt_img:ratio_picker"),
            InlineKeyboardButton(text="💎 کیفیت و رزولوشن", callback_data="gpt_img:res_picker")
        ])
        buttons.append([
            InlineKeyboardButton(text="🎨 سبک‌ها و پرامپت‌های عکس", callback_data="menu:gpt_image")
        ])
    # 2. Video Studio Models (Agnes Video)
    elif caps["is_video_studio"]:
        buttons.append([
            InlineKeyboardButton(text="🎬 تنظیمات تولید ویدیو", callback_data="video_menu"),
            InlineKeyboardButton(text="🎵 تولید صدای هماهنگ", callback_data="video_menu")
        ])
    # 3. Chat / Reasoning / Multimodal Models
    else:
        search_icon = "✅" if (caps["supports_web_search"] and web_search_enabled) else "❌"
        vision_icon = "✅" if caps["supports_vision"] else "❌"
        reasoning_icon = "✅" if caps["supports_reasoning"] else "❌"

        buttons.append([
            InlineKeyboardButton(text=f"🌐 وب سرچ: {search_icon}", callback_data="newchat:toggle_search")
        ])
        buttons.append([
            InlineKeyboardButton(text=f"👁️ تحلیل تصویر: {vision_icon}", callback_data="feat:info_vision"),
            InlineKeyboardButton(text=f"🧠 حل مسائل: {reasoning_icon}", callback_data="feat:info_reasoning")
        ])

    # Universal navigation
    buttons.append([
        InlineKeyboardButton(text="🤖 تغییر مدل هوش مصنوعی", callback_data="menu:models")
    ])
    buttons.append([
        InlineKeyboardButton(text="💬 گفتگوی جدید", callback_data="action:clear_chat")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_newchat_keyboard(
    web_search_enabled: bool = False,
    is_reasoning: bool = False,
    model_id: str = "gemini"
) -> InlineKeyboardMarkup:
    """Delegates to dynamic model-specific capability keyboard."""
    return get_model_features_keyboard(
        model_id=model_id,
        web_search_enabled=web_search_enabled,
        is_reasoning=is_reasoning
    )


def get_persistent_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Bottom persistent menu bar."""
    keyboard = [
        [
            KeyboardButton(text="💬 گفتگوی جدید"),
            KeyboardButton(text="🤖 انتخاب مدل")
        ],
        [
            KeyboardButton(text="🍌 ادیت عکس نانو بنانا"),
            KeyboardButton(text="🎬 استودیو تولید ویدیو")
        ],
        [
            KeyboardButton(text="👤 حساب کاربری"),
            KeyboardButton(text="🛒 خرید سرویس")
        ],
        [
            KeyboardButton(text="🎁 سرویس هدیه"),
            KeyboardButton(text="🎤 تبدیل متن به گفتار")
        ]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="👑 پنل مدیریت ادمین")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
