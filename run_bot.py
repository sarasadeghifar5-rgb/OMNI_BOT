"""
===========================================================
🚀 OmniLLM Telegram Bot Runner
===========================================================
Run this script to start the high-concurrency Telegram Bot.
Usage:
    python run_bot.py
"""

import sys
import asyncio

import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.bot.bot import run_bot_polling

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(run_bot_polling())
        except (KeyboardInterrupt, SystemExit):
            print("\n🛑 ربات تلگرام متوقف شد.")
            break
        except BaseException as e:
            print(f"\n⚠️ [OmniLLM Supervisor] Process caught {type(e).__name__}: {e}. Restarting bot in 5 seconds...")
            time.sleep(5)
