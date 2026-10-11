import os
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load .env file from project root if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "app" / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
SESSIONS_DIR = DATA_DIR / "sessions"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Default Model Catalog
AVAILABLE_MODELS: List[Dict[str, Any]] = [
    # Nano Banana Image Studio
    {
        "id": "agnes-image-2.5-flash",
        "name": "ادیت عکس نانو بنانا 🍌",
        "provider": "agnes",
        "category": "Image",
        "description": "تولید و ادیت فوق‌حرفه‌ای تصویر با هوش مصنوعی نانو بنانا با پشتیبانی از تولید متن به عکس، ویرایش و بازطراحی تصاویر",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 8000,
        "icon": "image",
        "badge": "ادیت عکس نانو بنانا",
        "recommended": True,
    },
    # Nano Video & Synchronized Audio-Video Studio
    {
        "id": "agnes-video-2.5",
        "name": "تولید ویدیو استودیو نانو 🎬",
        "provider": "agnes",
        "category": "Video",
        "description": "تولید ویدیو و انیمیشن با کیفیت بالا با صدا و تصویر هماهنگ (Synchronized Audio-Video) از متن و عکس",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 8000,
        "icon": "video",
        "badge": "تولید ویدیو و صدا",
        "recommended": True,
    },
    # Nano Text Generation, Deep Reasoning & Multimodal
    {
        "id": "agnes-2.5-flash",
        "name": "استدلال عمیق (Deep Reasoning)",
        "provider": "agnes",
        "category": "Reasoning",
        "description": "استدلال منطقی و حل مسائل پیچیده به همراه نمایش زنجیره تفکر عمیق (Thinking) و درک تصویر و متن",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 128000,
        "icon": "brain",
        "badge": "استدلال و بینایی",
        "recommended": True,
    },
    # Google Nano Banana (Puter AI)
    {
        "id": "nano-banana",
        "name": "Google Nano Banana 🍌 (Puter)",
        "provider": "puter",
        "category": "Image",
        "description": "تولید تصویر با کیفیت فوق‌العاده و سرعت بالا با هوش مصنوعی Puter و مدل Google Nano Banana",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 8000,
        "icon": "image",
        "badge": "استودیو عکس رایگان",
        "recommended": True,
    },
    {
        "id": "nano-banana-2",
        "name": "Google Nano Banana 2 🚀",
        "provider": "puter",
        "category": "Image",
        "description": "نسل جدید تولید تصویر گوگل بر پایه هوش مصنوعی قدرتمند Gemini 3.1 Flash Image",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 8000,
        "icon": "zap",
        "badge": "Gemini 3.1 Flash",
    },
    {
        "id": "nano-banana-pro",
        "name": "Google Nano Banana Pro 💎",
        "provider": "puter",
        "category": "Image",
        "description": "استودیوی تولید عکس فوق حرفه‌ای گوگل بر پایه Gemini 3 Pro با خروجی فوق‌العاده باکیفیت 4K",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 8000,
        "icon": "sparkles",
        "badge": "4K Ultra HD",
    },
    # Atria ASI
    {
        "id": "Atria-Dawn-Preview",
        "name": "Atria Dawn Preview 🌅 (استدلال تفکری)",
        "provider": "atria",
        "category": "Reasoning",
        "description": "مدل قدرتمند پژوهشی و استدلالی Atria Dawn Preview با توانایی استدلال پیشرفته، تحلیل کد و زمینه ۲۵۶ هزار توکن",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 256000,
        "icon": "brain",
        "badge": "استدلال / 256K",
        "recommended": True,
    },
    # DeepSeek
    {
        "id": "deepseek-reasoner",
        "name": "DeepSeek R1 (Reasoner)",
        "provider": "deepseek",
        "category": "Reasoning",
        "description": "استدلال منطقی و حل مسائل پیچیده به همراه نمایش زنجیره تفکر (Thinking Process)",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 64000,
        "icon": "brain",
        "badge": "استدلال عمیق",
        "recommended": True,
    },
    {
        "id": "deepseek-chat",
        "name": "DeepSeek V3",
        "provider": "deepseek",
        "category": "General",
        "description": "مدل پرچمدار، سریع، اقتصادی و باهوش برای کدنویسی و نگارش متون",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 64000,
        "icon": "zap",
        "badge": "سریع و دقیق",
    },
    # OpenAI
    {
        "id": "gpt-4o",
        "name": "GPT-4o (Omni)",
        "provider": "openai",
        "category": "Multimodal",
        "description": "مدل پرچمدار OpenAI با درک فوق‌العاده تصویر، نمودار و متن",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 128000,
        "icon": "sparkles",
        "badge": "بینایی ماشین",
        "recommended": True,
    },
    {
        "id": "gpt-4o-mini",
        "name": "GPT-4o Mini",
        "provider": "openai",
        "category": "General",
        "description": "نسخه سبک، اقتصادی و بسیار سریع با پشتیبانی از تحلیل عکس",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 128000,
        "icon": "zap",
        "badge": "اقتصادی",
    },
    {
        "id": "o1",
        "name": "OpenAI o1",
        "provider": "openai",
        "category": "Reasoning",
        "description": "مدل تفکری پیشرفته OpenAI برای حل پیشرفته‌ترین مسائل ریاضی و کدنویسی",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 200000,
        "icon": "brain",
        "badge": "استدلال",
    },
    # xAI Grok
    {
        "id": "grok-2-vision-1212",
        "name": "Grok 2 Vision (xAI)",
        "provider": "grok",
        "category": "Multimodal",
        "description": "مدل پیشرفته هوش مصنوعی ایلان ماسک (xAI) با توانایی تحلیل تصاویر",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 32768,
        "icon": "eye",
        "badge": "xAI Vision",
        "recommended": True,
    },
    {
        "id": "grok-2-1212",
        "name": "Grok 2 (xAI)",
        "provider": "grok",
        "category": "General",
        "description": "نسخه متنی Grok-2 با دانش به‌روز و درک بالا از کد و محتوا",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 131072,
        "icon": "terminal",
        "badge": "xAI",
    },
    # Zhipu AI GLM
    {
        "id": "glm-4v-flash",
        "name": "GLM-4V Flash (رایگان / بینایی ماشین)",
        "provider": "glm",
        "category": "Multimodal",
        "description": "مدل چندرسانه‌ای و بینایی ماشین کاملاً رایگان Zhipu AI با سرعت بالا جهت تحلیل عکس، اسناد و نمودارها",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 128000,
        "icon": "image",
        "badge": "رایگان / Vision",
        "recommended": True,
    },
    {
        "id": "glm-4-flash",
        "name": "GLM-4 Flash (رایگان / فوق سریع)",
        "provider": "glm",
        "category": "Fast",
        "description": "نسخه متنی کاملاً رایگان، سبک و بسیار سریع Zhipu AI با پشتیبانی تا 128K توکن",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 128000,
        "icon": "zap",
        "badge": "رایگان / سریع",
    },
    {
        "id": "glm-4v-plus",
        "name": "GLM-4V Plus (Zhipu Pro)",
        "provider": "glm",
        "category": "Multimodal",
        "description": "پرچمدار بینایی ماشین Zhipu AI برای تحلیل تخصصی و پیشرفته اسناد، فرم‌ها و تصاویر با بالاترین دقت",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 128000,
        "icon": "image",
        "badge": "GLM Vision Pro",
    },
    {
        "id": "glm-4-plus",
        "name": "GLM-4 Plus",
        "provider": "glm",
        "category": "General",
        "description": "مدل متنی قدرتمند GLM-4 با کارایی بالا در زبان‌های چندگانه و کدنویسی",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 128000,
        "icon": "cpu",
        "badge": "GLM",
    },
    # Google Gemini (Unified)
    {
        "id": "gemini",
        "name": "Google Gemini (واحد و پرسرعت)",
        "provider": "gemini",
        "category": "Multimodal",
        "description": "مدل پرچمدار، سریع و چندرسانه‌ای گوگل با پشتیبانی از چت پیشرفته، کدنویسی، پاسخ سریع و تحلیل تصاویر",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 1000000,
        "icon": "zap",
        "badge": "گوگل جمینای",
        "recommended": True,
    },
    # Anthropic Claude
    {
        "id": "claude-3-5-sonnet-20241022",
        "name": "Claude 3.5 Sonnet",
        "provider": "claude",
        "category": "Multimodal",
        "description": "بهترین مدل جهان در کدنویسی، تحلیل نمودار، نگارش ادبی و ساخت آرتیفکت",
        "supports_vision": True,
        "supports_reasoning": False,
        "context_window": 200000,
        "icon": "code",
        "badge": "برترین کدنویس",
    },
    # OpenRouter (مدل‌های فعال و تست‌شده رایگان)
    {
        "id": "nvidia/nemotron-3-super-120b-a12b:free",
        "name": "NVIDIA Nemotron 3 Super (رایگان)",
        "provider": "openrouter",
        "category": "Reasoning",
        "description": "مدل قدرتمند و فوق‌العاده باهوش انویدیا (۱۲۰ میلیارد پارامتر) با استدلال تحلیلی قوی و پاسخ‌دهی سریع در OpenRouter",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 131072,
        "icon": "brain",
        "badge": "رایگان / Nemotron 120B",
        "recommended": True,
    },
    {
        "id": "nex-agi/nex-n2.5-pro:free",
        "name": "Nex N2.5 Pro (رایگان OpenRouter)",
        "provider": "openrouter",
        "category": "General",
        "description": "مدل سریع، مدرن و با کارایی بسیار بالا در زبان فارسی و کدنویسی به صورت کاملاً رایگان در OpenRouter",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 65536,
        "icon": "sparkles",
        "badge": "رایگان / Nex Pro",
    },
    # ==========================================
    # CodeCraft API Flagship & Star Models
    # ==========================================
    {
        "id": "claude-fable-5.1",
        "name": "Claude Fable 5.1 🌟 (استار تلگرام)",
        "provider": "codecraft",
        "category": "Star",
        "description": "پرچمدار بی‌رقیب تفکر و استدلال عمیق با خلاقیت استثنایی و زمینه ۱ میلیون توکن در CodeCraft API",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "sparkles",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "claude-fable-5",
        "name": "Claude Fable 5 🌟 (استار تلگرام)",
        "provider": "codecraft",
        "category": "Star",
        "description": "مدل تحلیلی-خلاقانه پیشرفته نسل ۵ آنتروپیک با درک چندوجهی، کدنویسی و نگارش با ۱ میلیون توکن زمینه",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "sparkles",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "claude-opus-5.5",
        "name": "Claude Opus 5.5 💎 (استار تلگرام)",
        "provider": "codecraft",
        "category": "Star",
        "description": "قوی‌ترین و باهوش‌ترین مدل Claude تا به امروز، رتبه ۱ بنچمارک‌های استدلال ریاضی و مهندسی نرم‌افزار",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "diamond",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "claude-opus-5",
        "name": "Claude Opus 5 💎 (استار تلگرام)",
        "provider": "codecraft",
        "category": "Star",
        "description": "نسخه پرچمدار Opus 5 با قدرت بی‌نظیر در حل مسائل پیچیده، تحلیل اسناد سنگین و بینایی ماشین",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "diamond",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "claude-opus-4.8",
        "name": "Claude Opus 4.8 💎",
        "provider": "codecraft",
        "category": "Star",
        "description": "مدل استدلالی و عمیق Opus 4.8 با پنجره زمینه ۱ میلیون توکن و دقت استثنایی",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "brain",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "claude-opus-4.7",
        "name": "Claude Opus 4.7",
        "provider": "codecraft",
        "category": "Star",
        "description": "نسخه بهینه‌شده تحلیلی Claude Opus 4.7 با استدلال و بینایی ماشین ۱ میلیون توکن",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "brain",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "claude-opus-4.6",
        "name": "Claude Opus 4.6",
        "provider": "codecraft",
        "category": "Star",
        "description": "مدل استدلالی پایدار Opus 4.6 برای تحلیل متون حجیم و استخراج دانش",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "brain",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "claude-mythos-preview",
        "name": "Claude Mythos Preview 🔮",
        "provider": "codecraft",
        "category": "Star",
        "description": "مدل آزمایشی اسرارآمیز و فوق‌العاده باهوش Claude Mythos با توانایی استدلال آینده‌نگرانه",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "sparkles",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol ☀️ (استار تلگرام)",
        "provider": "codecraft",
        "category": "Star",
        "description": "پیشرفته‌ترین غول OpenAI با بالاترین ضریب هوشی، معماری ترکیبی و قدرت حل مسائل سطح دکترا",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1050000,
        "icon": "sun",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "gpt-5.5-pro",
        "name": "GPT-5.5 Pro 🚀 (استار تلگرام)",
        "provider": "codecraft",
        "category": "Star",
        "description": "نسخه حرفه‌ای GPT-5.5 برای مهندسی، معماری نرم‌افزار و تحلیل کلان‌داده با بیش از ۱ میلیون توکن",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1050000,
        "icon": "zap",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    {
        "id": "deepseek-v4-pro-max",
        "name": "DeepSeek V4 Pro Max 🧠 (استار تلگرام)",
        "provider": "codecraft",
        "category": "Star",
        "description": "پرچمدار استدلال ریاضی و کدنویسی دیپ‌سیک نسل ۴ با بیش از ۱.۶ تریلیون پارامتر و ۱ میلیون توکن زمینه",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 1048576,
        "icon": "brain",
        "badge": "⭐ Star VIP",
        "is_star_required": True,
    },
    # ==========================================
    # CodeCraft General & Flagship Models
    # ==========================================
    {
        "id": "claude-sonnet-5",
        "name": "Claude Sonnet 5 🖋️",
        "provider": "codecraft",
        "category": "General",
        "description": "نسل جدید Claude Sonnet 5 با سرعت فوق‌العاده، نگارش عالی و زمینه ۱ میلیون توکن",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "code",
        "badge": "Sonnet 5",
    },
    {
        "id": "gpt-5.6-terra",
        "name": "GPT-5.6 Terra 🌍",
        "provider": "codecraft",
        "category": "General",
        "description": "مدل متوازن و قدرتمند سری GPT-5.6 برای وظایف چندگانه، ترجمه و پردازش اسناد",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1050000,
        "icon": "globe",
        "badge": "GPT-5.6",
    },
    {
        "id": "gpt-5.6-luna",
        "name": "GPT-5.6 Luna 🌙",
        "provider": "codecraft",
        "category": "Fast",
        "description": "مدل پرسرعت و سبک GPT-5.6 با سرعت پاسخگویی ۲۹۰ کاراکتر بر ثانیه و ۱ میلیون زمینه",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1050000,
        "icon": "moon",
        "badge": "فوق سریع",
    },
    {
        "id": "gpt-5.5",
        "name": "GPT-5.5 ⚡",
        "provider": "codecraft",
        "category": "General",
        "description": "نسل جدید مدل پایه GPT-5.5 با هوش زبانی فوق‌العاده و درک بصری",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1050000,
        "icon": "zap",
        "badge": "GPT-5.5",
    },
    {
        "id": "deepseek-v4-pro-0813",
        "name": "DeepSeek V4 Pro 🧠",
        "provider": "codecraft",
        "category": "Reasoning",
        "description": "مدل متن‌باز قدرتمند دیپ‌سیک V4 پرو با استدلال تحلیلی قوی و پنجره ۱ میلیون توکن",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 1048576,
        "icon": "brain",
        "badge": "DeepSeek V4",
    },
    {
        "id": "deepseek-v4-flash-0731",
        "name": "DeepSeek V4 Flash ⚡",
        "provider": "codecraft",
        "category": "Fast",
        "description": "نسخه سبک و سریع DeepSeek V4 با ۳۰۴ میلیارد پارامتر و استدلال سریع",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 1048576,
        "icon": "zap",
        "badge": "سریع",
    },
    {
        "id": "gemini-3.7-flash",
        "name": "Gemini 3.7 Flash ⚡",
        "provider": "codecraft",
        "category": "General",
        "description": "جدیدترین مدل فلش گوگل با استدلال ترکیبی، درک تصویر و پنجره ۱ میلیون توکن",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1048576,
        "icon": "zap",
        "badge": "Google Gemini",
    },
    {
        "id": "gemini-3.6-flash",
        "name": "Gemini 3.6 Flash ⚡",
        "provider": "codecraft",
        "category": "Fast",
        "description": "مدل فوق‌سریع نسل ۳ گوگل با بینایی ماشین و کارایی بالا",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1048576,
        "icon": "zap",
        "badge": "Gemini 3.6",
    },
    {
        "id": "gemini-3.1-pro",
        "name": "Gemini 3.1 Pro 🌐",
        "provider": "codecraft",
        "category": "General",
        "description": "پرچمدار تحلیلی و تخصصی گوگل با زمینه ۱ میلیون توکن و بینایی ماشین دقیق",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1048576,
        "icon": "sparkles",
        "badge": "Gemini Pro",
    },
    {
        "id": "grok-4.6",
        "name": "xAI Grok 4.6 🛸",
        "provider": "codecraft",
        "category": "General",
        "description": "مدل پیشرفته هوش مصنوعی ایلان ماسک نسل ۴.۶ با دانش به‌روز، بینایی ماشین و ۵۰۰K توکن",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 500000,
        "icon": "terminal",
        "badge": "xAI Grok",
    },
    {
        "id": "grok-4.5",
        "name": "xAI Grok 4.5 🛸",
        "provider": "codecraft",
        "category": "General",
        "description": "نسخه ۴.۵ گروک با درک عمیق از شوخ‌طبعی، منطق و تحلیل کد",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 500000,
        "icon": "terminal",
        "badge": "xAI Grok",
    },
    {
        "id": "glm-5.3",
        "name": "GLM 5.3 🇨🇳",
        "provider": "codecraft",
        "category": "General",
        "description": "مدل بنیادین دو زبانه Zhipu AI نسل ۵.۳ با زمینه ۱ میلیون توکن و درک زبان بالا",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "cpu",
        "badge": "GLM 5.3",
    },
    {
        "id": "glm-5.2",
        "name": "GLM 5.2 🇨🇳",
        "provider": "codecraft",
        "category": "General",
        "description": "مدل پایدار سری GLM 5 با کارایی عالی در نگارش و ترجمه",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "cpu",
        "badge": "GLM 5.2",
    },
    {
        "id": "qwen3.8-max",
        "name": "Qwen 3.8 Max 👑",
        "provider": "codecraft",
        "category": "General",
        "description": "پرچمدار هوش مصنوعی علی‌بابا با ۱ میلیون توکن زمینه و رتبه برتر چندزبانه و بینایی",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "crown",
        "badge": "Qwen Max",
    },
    {
        "id": "qwen3.8-27b",
        "name": "Qwen 3.8 27B ⚡",
        "provider": "codecraft",
        "category": "Fast",
        "description": "مدل فشرده و بسیار بهینه ۲۷.۸ میلیارد پارامتری علی‌بابا با سرعت بالا",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 262144,
        "icon": "zap",
        "badge": "Qwen 27B",
    },
    {
        "id": "qwen3.7-max",
        "name": "Qwen 3.7 Max 👑",
        "provider": "codecraft",
        "category": "General",
        "description": "نسخه ۳.۷ مکس علی‌بابا با عملکرد باثبات در مسائل ریاضی و منطقی",
        "supports_vision": True,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "crown",
        "badge": "Qwen 3.7",
    },
    {
        "id": "kimi-k3",
        "name": "Moonshot Kimi K3 🌙",
        "provider": "codecraft",
        "category": "General",
        "description": "مدل استدلالی مون‌شات نسل ۳ با تخصص در زمینه بسیار طولانی ۱ میلیون توکن",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "moon",
        "badge": "Kimi K3",
    },
    {
        "id": "kimi-k2.6",
        "name": "Moonshot Kimi K2.6 🌙",
        "provider": "codecraft",
        "category": "General",
        "description": "نسخه ۲.۶ کیمی برای خلاصه سازی و تحلیل اسناد و رمان‌های بزرگ",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "moon",
        "badge": "Kimi K2.6",
    },
    {
        "id": "seed-2.1-turbo",
        "name": "Seed 2.1 Turbo 🌱",
        "provider": "codecraft",
        "category": "Fast",
        "description": "مدل سبک و توربو برای چت سریع، پاسخ‌های خلاصه و روزمره با ۲۶۲K توکن",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 262144,
        "icon": "zap",
        "badge": "Seed Turbo",
    },
    {
        "id": "seed-2.1-pro",
        "name": "Seed 2.1 Pro 🌱",
        "provider": "codecraft",
        "category": "General",
        "description": "نسخه حرفه‌ای مدل Seed با دقت بیشتر در استدلال و تحلیل متون",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 262144,
        "icon": "sparkles",
        "badge": "Seed Pro",
    },
    {
        "id": "muse-spark-1.1",
        "name": "Muse Spark 1.1 ✨",
        "provider": "codecraft",
        "category": "General",
        "description": "مدل نوآورانه Muse Spark 1.1 با ۱ میلیون توکن زمینه و توانایی حل مسئله",
        "supports_vision": False,
        "supports_reasoning": True,
        "context_window": 1000000,
        "icon": "sparkles",
        "badge": "Muse Spark",
    },
    {
        "id": "gemma-2-2b",
        "name": "Google Gemma 2 2B 🎈",
        "provider": "codecraft",
        "category": "Fast",
        "description": "مدل فوق‌العاده سبک، سریع و باز گوگل برای کارهای سریع روزمره",
        "supports_vision": False,
        "supports_reasoning": False,
        "context_window": 8192,
        "icon": "cpu",
        "badge": "Gemma 2B",
    }
]

# Set of models that require Telegram Stars / VIP subscription for regular users
STAR_LOCKED_MODELS = {
    "claude-fable-5.1",
    "claude-fable-5",
    "claude-opus-5.5",
    "claude-opus-5",
    "claude-opus-4.8",
    "claude-opus-4.7",
    "claude-opus-4.6",
    "claude-mythos-preview",
    "gpt-5.6-sol",
    "gpt-5.5-pro",
    "deepseek-v4-pro-max",
}

CODECRAFT_API_KEY = os.getenv("CODECRAFT_API_KEY", "")
CODECRAFT_API_KEYS = os.getenv("CODECRAFT_API_KEYS", "")
CODECRAFT_BASE_URL = os.getenv("CODECRAFT_BASE_URL", "https://codecraftapi.com/v1")

AGNES_API_KEY = os.getenv("AGNES_API_KEY", "")
AGNES_API_KEYS = os.getenv("AGNES_API_KEYS", "")
AGNES_BASE_URL = os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")

ATRIA_API_KEY = os.getenv("ATRIA_API_KEY", "")
ATRIA_API_KEYS = os.getenv("ATRIA_API_KEYS", "")
ATRIA_BASE_URL = os.getenv("ATRIA_BASE_URL", "https://api.atria-asi.ai/v1")

PROVIDER_ENDPOINTS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "grok": "https://api.x.ai/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "claude": "https://api.anthropic.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "pollinations": "https://gen.pollinations.ai/v1",
    "puter": "https://api.puter.com/drivers/call",
    "atria": ATRIA_BASE_URL,
    "agnes": AGNES_BASE_URL,
    "codecraft": CODECRAFT_BASE_URL,
    "ollama": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
}

DEFAULT_SYSTEM_PROMPT = """You are OmniLLM, a world-class, highly knowledgeable, and versatile AI assistant.
- You answer clearly, thoroughly, and objectively.
- When answering in Persian/Farsi, use natural, polite, and fluent Persian.
- Present mathematical calculations and formulas with exceptional elegance, step-by-step clarity, and clean Unicode mathematical symbols (e.g. x², ∂z/∂x, ∫ f(x) dx, √x) in dedicated code blocks or pills for maximum legibility in Telegram.
- If live web search results are provided in your context, synthesize them accurately and cite references using [1], [2], etc.
- If images are provided, analyze them with precise spatial and semantic detail.
- For complex questions, think through steps systematically."""

# ===============================================
# Model Capabilities Classification (CodeCraft & Providers)
# ===============================================

# 1. Models that natively support Web Search (verified from CodeCraft capabilities):
MODELS_WITH_WEB_SEARCH = {
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.1-pro",
    "grok-4.6",
    "grok-4.5",
    "kimi-k3",
    "kimi-k2.6",
    "glm-5.3",
    "glm-5.2",
    "qwen3.8-max",
    "qwen3.7-max",
}

# 2. Models that natively support Vision (Image Comprehension):
MODELS_WITH_VISION = {
    "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.1-pro", "gemini",
    "claude-opus-5.5", "claude-fable-5.1", "claude-opus-5", "claude-fable-5",
    "claude-opus-4.8", "claude-opus-4.7", "claude-opus-4.6", "claude-mythos-preview",
    "claude-sonnet-5", "claude-3-5-sonnet-20241022",
    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5-pro", "gpt-5.5",
    "gpt-4o", "gpt-4o-mini",
    "grok-4.6", "grok-4.5", "grok-2-vision-1212",
    "kimi-k3", "kimi-k2.6",
    "glm-5.3", "glm-5.2", "glm-4v-flash", "glm-4v-plus",
    "qwen3.8-max", "qwen3.7-max",
    "seed-2.1-pro", "seed-2.1-turbo", "muse-spark-1.1",
    "agnes-image-2.5-flash", "agnes-video-2.5", "agnes-2.5-flash"
}

# 3. Models that natively support Deep Reasoning (Thinking Process):
MODELS_WITH_REASONING = {
    "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.1-pro",
    "claude-opus-5.5", "claude-fable-5.1", "claude-opus-5", "claude-fable-5",
    "claude-opus-4.8", "claude-opus-4.7", "claude-opus-4.6", "claude-mythos-preview", "claude-sonnet-5",
    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5-pro", "gpt-5.5",
    "deepseek-v4-pro-max", "deepseek-v4-pro-0813", "deepseek-v4-flash-0731",
    "deepseek-reasoner", "Atria-Dawn-Preview",
    "grok-4.6", "grok-4.5",
    "kimi-k3", "kimi-k2.6",
    "glm-5.3", "glm-5.2",
    "qwen3.8-max", "qwen3.7-max", "qwen3.8-27b",
    "seed-2.1-pro", "seed-2.1-turbo", "muse-spark-1.1",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "agnes-2.5-flash"
}

IMAGE_STUDIO_MODELS = {
    "agnes-image-2.5-flash", "nano-banana", "nano-banana-2", "nano-banana-pro"
}

VIDEO_STUDIO_MODELS = {
    "agnes-video-2.5"
}

def get_model_capabilities(model_id: str) -> Dict[str, Any]:
    """
    Returns exact real-world capabilities and metadata for any model.
    """
    m = next((x for x in AVAILABLE_MODELS if x["id"] == model_id), None)
    if not m:
        m = {
            "id": model_id,
            "name": model_id,
            "provider": "codecraft",
            "context_window": 128000,
        }

    is_img = model_id in IMAGE_STUDIO_MODELS
    is_vid = model_id in VIDEO_STUDIO_MODELS
    sup_search = (model_id in MODELS_WITH_WEB_SEARCH) and not (is_img or is_vid)
    sup_vision = (model_id in MODELS_WITH_VISION)
    sup_reasoning = (model_id in MODELS_WITH_REASONING) and not (is_img or is_vid)

    return {
        "id": model_id,
        "name": m.get("name", model_id),
        "provider": m.get("provider", "codecraft"),
        "supports_web_search": sup_search,
        "supports_vision": sup_vision,
        "supports_reasoning": sup_reasoning,
        "is_image_studio": is_img,
        "is_video_studio": is_vid,
        "context_window": m.get("context_window", 128000),
        "is_star_required": model_id in STAR_LOCKED_MODELS,
    }

def format_model_card(model_id: str, web_search_enabled: bool = False) -> str:
    """Formats an authentic capability summary card for the current model."""
    caps = get_model_capabilities(model_id)
    name = caps["name"]
    ctx = f"{caps['context_window']:,} توکن" if caps.get("context_window") else "۱۲۸,۰۰۰ توکن"

    if caps["is_image_studio"]:
        return (
            f"🍌 **استودیو تولید و ادیت فوق‌حرفه‌ای تصویر ({name})**\n\n"
            "• 🎨 **قابلیت اصلی:** تبدیل متن به عکس با کیفیت بالا و ویرایش تصاویر ارسالی\n"
            "• 📐 **امکانات:** تنظیم نسبت تصویر (مربعی، استوری، پست) و کیفیت تا 4K\n"
            "• 💡 **روش استفاده:** هر متن، ایده یا عکسی ارسال فرمایید، پردازش تصویری می‌شود."
        )
    elif caps["is_video_studio"]:
        return (
            f"🎬 **استودیو پیشرفته انیمیشن و ویدیو ({name})**\n\n"
            "• 🎥 **قابلیت اصلی:** تولید ویدیو از متن و متحرک‌سازی تصاویر\n"
            "• 🎵 **صدا:** تولید صدای هماهنگ و منطبق با تصویر (Audio-Video Sync)\n"
            "• 💡 **روش استفاده:** پرامپت یا عکس خود را برای شروع ساخت ویدیو ارسال کنید."
        )

    # Standard / Flagship AI Chat Models
    search_str = "✅ فعال (اتصال مستقیم)" if web_search_enabled else "⚪ غیرفعال (قابل فعالسازی)"
    if not caps["supports_web_search"]:
        search_line = "• **وب‌سرچ زنده:** ❌ پشتیبانی نمی‌شود (پاسخ بر اساس پایگاه دانش درونی)"
    else:
        search_line = f"• **وب‌سرچ زنده:** {search_str}"

    if caps["supports_reasoning"]:
        reas_line = "🧠 **استدلال عمیق:** ✅ فعال (تفکر گام‌به‌گام و نمایش زنجیره تفکر Thinking)"
    else:
        reas_line = "⚡ **پردازش:** پاسخ‌دهی مستقیم و فوق‌سریع (بدون تاخیر استدلال)"

    if caps["supports_vision"]:
        vis_line = "👁️ **بینایی ماشین (Vision):** ✅ فعال (آماده دریافت و تحلیل تصاویر و اسناد)"
    else:
        vis_line = "📝 **بینایی ماشین (Vision):** ❌ فقط متنی (تصاویر پشتیبانی نمی‌شود)"

    star_line = "\n⭐ *این مدل اختصاصی اشتراک VIP استار تلگرام است.*" if caps["is_star_required"] else ""

    return (
        f"🤖 **مدل فعال هوش مصنوعی:** `{name}`\n\n"
        f"{search_line}\n"
        f"{reas_line}\n"
        f"{vis_line}\n"
        f"⚡ **ظرفیت حافظه و زمینه:** {ctx}"
        f"{star_line}\n\n"
        "💬 پیام یا سوال خود را ارسال فرمایید:"
    )
