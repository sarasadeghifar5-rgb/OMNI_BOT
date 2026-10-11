import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token
BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "8389701671:AAFvuEdwWPP01efDB6Zn3N5ZFMWTf-__xnM").strip()

# Admin IDs
MAIN_ADMIN_ID = int(os.getenv("TELEGRAM_MAIN_ADMIN_ID", "495404413").strip() or "495404413")
SECOND_ADMIN_ID = int(os.getenv("TELEGRAM_SECOND_ADMIN_ID", "8108907825").strip() or "8108907825")

_raw_admins = os.getenv("TELEGRAM_ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(x.strip()) for x in _raw_admins if x.strip().isdigit()]
for _aid in [MAIN_ADMIN_ID, SECOND_ADMIN_ID]:
    if _aid and _aid not in ADMIN_IDS:
        ADMIN_IDS.append(_aid)

# Database Path
DB_DIR = BASE_DIR / "app" / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "bot_database.sqlite3"

# Concurrency & Rate Limiting (High Scalability Enterprise Settings)
MAX_CONCURRENT_REQUESTS = int(os.getenv("BOT_MAX_CONCURRENCY", "200"))  # Global concurrent requests to LLM
RATE_LIMIT_SECONDS = float(os.getenv("BOT_RATE_LIMIT", "0.8"))        # Min seconds between messages per user
MAX_HISTORY_TURNS = int(os.getenv("BOT_MAX_HISTORY_TURNS", "12"))      # Sliding window of chat messages per user

# Default settings
DEFAULT_MODEL = "gemini-3.7-flash"
DEFAULT_IMAGE_MODEL = None
DEFAULT_TTS_VOICE = "kore"
CUSTOM_EMOJI_NEW_CHAT = os.getenv("CUSTOM_EMOJI_NEW_CHAT", "5886422218707050358")
CUSTOM_EMOJI_WEB_SEARCH = os.getenv("CUSTOM_EMOJI_WEB_SEARCH", "").strip()
CUSTOM_EMOJI_THINKING = os.getenv("CUSTOM_EMOJI_THINKING", "5334904192622403796").strip()

# Webhook settings (optional for production deployment)
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip()
WEBHOOK_PATH = f"/webhook/telegram/{BOT_TOKEN}" if BOT_TOKEN else "/webhook/telegram"
