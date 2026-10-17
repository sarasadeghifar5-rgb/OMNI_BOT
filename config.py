"""
Configuration file for Telegram AI Bot.
Contains all API keys, endpoints, bot tokens, admin IDs, and model definitions with official logos.
"""
import os
from typing import Dict, List, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================= Telegram Settings =================
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8389701671:AAFvuEdwWPP01efDB6Zn3N5ZFMWTf-__xnM")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "495404413"))

# ================= Service 1: CleanAPIs (کدکرفت سابق) =================
CLEANAPIS_BASE_URL: str = os.getenv("CLEANAPIS_BASE_URL", "https://cleanapis.com/v1")
CLEANAPIS_API_KEY: str = os.getenv("CLEANAPIS_API_KEY", "cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB")

# ================= Service 2: Google Gemini (Google AI Studio) =================
GEMINI_BASE_URL: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
_gemini_raw = os.getenv("GEMINI_API_KEYS", "")
if _gemini_raw:
    GEMINI_API_KEYS: List[str] = [k.strip() for k in _gemini_raw.split(",") if k.strip()]
else:
    GEMINI_API_KEYS: List[str] = []

# ================= Service 3: استودیو چندرسانه‌ای مدل هوشمند پرو =================
AGNES_BASE_URL: str = os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
_agnes_raw = os.getenv("AGNES_API_KEYS", "")
if _agnes_raw:
    AGNES_API_KEYS: List[str] = [k.strip() for k in _agnes_raw.split(",") if k.strip()]
else:
    AGNES_API_KEYS: List[str] = []

# ================= Service 4: استدلال عمیق مدل هوشمند پرو =================
ATRIA_BASE_URL: str = os.getenv("ATRIA_BASE_URL", "https://api.atria-asi.ai/v1")
_atria_raw = os.getenv("ATRIA_API_KEYS", "")
if _atria_raw:
    ATRIA_API_KEYS: List[str] = [k.strip() for k in _atria_raw.split(",") if k.strip()]
else:
    ATRIA_API_KEYS: List[str] = []

# ================= Supported AI Models Catalog with Official Logos =================
DEFAULT_MODEL: str = "gpt-5.6-sol"

# ================= Animated Telegram Emojis for Keyboards & Models =================
# High quality official animated Telegram custom emojis (Lottie/TGS)
ANIMATED_EMOJIS: Dict[str, str] = {
    # AI Models (Replacing static logos with lively animated emojis)
    "openai": "5445388803223091254",          # ⚡️ High-voltage electric neon pulse (GPT-5.6 Sol)
    "claude": "5458799228719472718",          # 🌟 Radiant golden star (Claude 5 Sonnet)
    "claude_opus": "5260681660189408650",     # 💎 Pristine crystal diamond (Claude 5.5 Opus)
    "deepseek": "5431376038628171216",        # 💻 Animated terminal / code machine (DeepSeek V4)
    "gemini": "5472164874886846699",          # ✨ Google multi-star sparkle (Gemini 3.7 & Studio)
    "qwen": "5361837567463399422",            # 🔮 Mystic violet cyber sphere (Qwen 3.8 Max)
    "kimi": "5413606255686071808",            # 🌜 Glowing neon crescent moon (Moonshot Kimi K3)
    "smart_pro": "5237799019329105246",       # 🧠 Neural synapse thinking brain (Atria Deep Reasoning)
    "smart_pro_flash": "5445388803223091254", # ⚡️ Agile lightning flash (Agnes Flash)
    "smart_pro_adv": "5260681660189408650",   # 💎 Deep precision diamond (Agnes Pro)

    # Keyboards & Functional Buttons
    "robot": "5372981976804366741",           # 🤖 Animated Robot (Model switch)
    "brain": "5237799019329105246",           # 🧠 Animated Brain (Smart Pro)
    "palette": "5447642819239903347",         # 🎨 Animated Palette (Image generation)
    "pencil": "5334673106202010226",          # ✏️ Animated Pencil (Image edit)
    "video": "5375464961822695044",           # 🎬 Animated Clapperboard (Video generation)
    "camera": "5445344161333015312",          # 🎞 Animated Video Camera (Photo to video)
    "trash": "5445005936953424165",           # 🗑 Animated Trash Can (Clear chat)
    "info": "5247236071795754971",            # ℹ️ Animated Information (Help & Status)
    "gear": "5444869180899752137",            # ⚙️ Animated Gear (Admin panel)
    "cancel": "5445092669522996408",          # ❌ Animated Red Cross (Cancel / Close)
    "check": "5444987348334965906",           # ✅ Animated Green Checkmark (Confirm)
    "eye": "5424892643760937442",             # 👁 Animated Eye (Vision analysis)
    "chart": "5445146408153806223",           # 📊 Animated Analytics (Admin stats)
    "key": "5445373775132522312",             # 🔑 Animated Golden Key (API Key pool)
    "broadcast": "5469903029144657419",       # 📢 Animated Megaphone (Broadcast)
    "door": "5447434637880098257",            # 🚪 Animated Exit Door (Close panel)

    # Loading Spinners
    "loading": "5051120958752949074",         # 🌀 Futuristic circular loader spinner
    "hourglass": "5451732530048802485",       # ⏳ Classic animated hourglass
}

CUSTOM_EMOJIS: Dict[str, str] = ANIMATED_EMOJIS

AVAILABLE_MODELS: Dict[str, Dict[str, Any]] = {
    # OpenAI Flagship
    "gpt-5.6-sol": {
        "name": "GPT-5.6 Sol",
        "provider": "OpenAI",
        "icon": "⚡️",
        "custom_emoji_id": ANIMATED_EMOJIS["openai"],
        "desc": "جدیدترین پرچمدار OpenAI با نهایت سرعت و هوش تحلیلی",
        "service": "cleanapis",
        "logo": os.path.join(BASE_DIR, "data", "logos", "openai.png")
    },
    # Anthropic Flagships
    "claude-sonnet-5": {
        "name": "Claude 5 Sonnet",
        "provider": "Anthropic",
        "icon": "🌟",
        "custom_emoji_id": ANIMATED_EMOJIS["claude"],
        "desc": "مدل پرچمدار و خلاق آنتروپیک، مناسب برای کدنویسی و نگارش",
        "service": "cleanapis",
        "logo": os.path.join(BASE_DIR, "data", "logos", "claude.png")
    },
    "claude-opus-5.5": {
        "name": "Claude 5.5 Opus",
        "provider": "Anthropic",
        "icon": "💎",
        "custom_emoji_id": ANIMATED_EMOJIS["claude_opus"],
        "desc": "قوی‌ترین مدل استدلال عمیق و منطقی آنتروپیک",
        "service": "cleanapis",
        "logo": os.path.join(BASE_DIR, "data", "logos", "claude.png")
    },
    # DeepSeek Flagship
    "deepseek-v4-pro-max": {
        "name": "DeepSeek V4 Pro Max",
        "provider": "DeepSeek",
        "icon": "💻",
        "custom_emoji_id": ANIMATED_EMOJIS["deepseek"],
        "desc": "غول هوش مصنوعی برای برنامه‌نویسی تخصصی و ریاضیات",
        "service": "cleanapis",
        "logo": os.path.join(BASE_DIR, "data", "logos", "deepseek.png")
    },
    # Google Gemini
    "gemini-3.7-flash": {
        "name": "Gemini 3.7 Flash",
        "provider": "Google",
        "icon": "✨",
        "custom_emoji_id": ANIMATED_EMOJIS["gemini"],
        "desc": "نسخه ۳.۷ جمینای، پاسخ‌دهی رعدآسا و هوشمندانه",
        "service": "cleanapis",
        "logo": os.path.join(BASE_DIR, "data", "logos", "gemini.png")
    },
    # Alibaba Qwen
    "qwen3.8-max": {
        "name": "Qwen 3.8 Max",
        "provider": "Alibaba Cloud",
        "icon": "🔮",
        "custom_emoji_id": ANIMATED_EMOJIS["qwen"],
        "desc": "مدل قدرتمند علی‌بابا با درک فوق‌العاده متون و داده‌ها",
        "service": "cleanapis",
        "logo": os.path.join(BASE_DIR, "data", "logos", "qwen.png")
    },
    # Moonshot Kimi
    "kimi-k3": {
        "name": "Kimi K3",
        "provider": "Moonshot AI",
        "icon": "🌜",
        "custom_emoji_id": ANIMATED_EMOJIS["kimi"],
        "desc": "متخصص تحلیل متون فوق طولانی و مقالات حجیم",
        "service": "cleanapis",
        "logo": os.path.join(BASE_DIR, "data", "logos", "kimi.png")
    },

    # Deep Reasoning Model
    "Atria-Dawn-Preview": {
        "name": "مدل هوشمند پرو (استدلال عمیق)",
        "provider": "مدل هوشمند پرو",
        "icon": "🧠",
        "custom_emoji_id": ANIMATED_EMOJIS["smart_pro"],
        "desc": "مدل تفکر عمیق و استنتاج پیشرفته با پنجره ۲۰۰،۰۰۰ توکن",
        "service": "atria",
        "logo": os.path.join(BASE_DIR, "data", "logos", "smart_pro.png")
    },

    # Intelligent Pro Nano Models
    "agnes-3.0-flash": {
        "name": "مدل هوشمند پرو (فلاش)",
        "provider": "مدل هوشمند پرو",
        "icon": "⚡️",
        "custom_emoji_id": ANIMATED_EMOJIS["smart_pro_flash"],
        "desc": "مدل چابک و هوشمند برای مکالمات سریع و تخصصی",
        "service": "agnes",
        "logo": os.path.join(BASE_DIR, "data", "logos", "smart_pro.png")
    },
    "agnes-2.5-pro": {
        "name": "مدل هوشمند پرو (پیشرفته)",
        "provider": "مدل هوشمند پرو",
        "icon": "💎",
        "custom_emoji_id": ANIMATED_EMOJIS["smart_pro_adv"],
        "desc": "نسخه حرفه‌ای مدل هوشمند پرو با دقت مضاعف",
        "service": "agnes",
        "logo": os.path.join(BASE_DIR, "data", "logos", "smart_pro.png")
    },

    # Google Gemini Studio
    "gemini-flash-latest": {
        "name": "Gemini Flash Google",
        "provider": "Google AI Studio",
        "icon": "✨",
        "custom_emoji_id": ANIMATED_EMOJIS["gemini"],
        "desc": "هوش مصنوعی رسمی گوگل از استودیو AI",
        "service": "gemini",
        "logo": os.path.join(BASE_DIR, "data", "logos", "gemini.png")
    }
}

# Image & Video Models
AGNES_IMAGE_MODEL: str = "agnes-image-2.5-flash"
AGNES_VIDEO_MODEL: str = "agnes-video-2.5-flash"

# Database path
DB_PATH: str = os.path.join(BASE_DIR, "data", "bot_database.sqlite")
