import os
import sys
import threading
import asyncio
import uvicorn
from dotenv import load_dotenv

load_dotenv()

def run_bot_background():
    """Run Telegram bot polling inside its own isolated asyncio event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    from app.bot.bot import run_bot_polling
    try:
        loop.run_until_complete(run_bot_polling())
    except Exception as e:
        print(f"🛑 [Bot Background Error]: {e}", flush=True)

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN") or "8389701671:AAFvuEdwWPP01efDB6Zn3N5ZFMWTf-__xnM"
    if telegram_token:
        print("🚀 Starting OmniLLM Telegram Bot in background thread...", flush=True)
        bot_thread = threading.Thread(target=run_bot_background, daemon=True)
        bot_thread.start()

    print(f"🌐 Starting Web Server on port {port} (Render Keep-Alive Ready)...", flush=True)
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")
