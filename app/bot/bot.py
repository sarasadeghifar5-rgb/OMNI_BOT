import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from app.bot.config import BOT_TOKEN
from app.bot.config import BOT_TOKEN
from app.bot.database import BotDatabase
from app.bot.middlewares import ThrottlingMiddleware, UserBusyMiddleware, ChannelLockMiddleware, ActivityTrackingMiddleware
from app.bot.handlers import admin, start, tools, image, video, vision, voice, chat, account

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("OmniLLMBot")

async def setup_bot_commands(bot: Bot):
    """Set up Telegram bot commands menu."""
    commands = [
        BotCommand(command="start", description="شروع مجدد و منوی اصلی"),
        BotCommand(command="account", description="حساب کاربری و اشتراک 👤"),
        BotCommand(command="buy", description="خرید اشتراک با استار تلگرام ⭐"),
        BotCommand(command="model", description="لیست و انتخاب مدل هوش مصنوعی"),
        BotCommand(command="image", description="ادیت عکس نانو بنانا 🍌"),
        BotCommand(command="video", description="استودیو تولید ویدیو و انیمیشن 🎬"),
        BotCommand(command="reasoner", description="استدلال عمیق 🧠"),
        BotCommand(command="clear", description="گفتگو جدید و پاکسازی حافظه 💬"),
        BotCommand(command="admin", description="پنل مدیریت پیشرفته ادمین 👑"),
        BotCommand(command="help", description="راهنمای جامع ربات"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")

def create_bot() -> Bot:
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured in .env file!")
    session = AiohttpSession(limit=300, timeout=120.0)
    return Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )

def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    # 📊 سپر ردیابی بلادرنگ فعالیت و آمار دقیق کاربران (Real-Time User & Analytics Tracker)
    activity_guard = ActivityTrackingMiddleware()
    dp.message.outer_middleware(activity_guard)
    dp.callback_query.outer_middleware(activity_guard)

    # 🛡️ سپر اول: مسدودسازی ارسال پیام همزمان تا زمان دریافت پاسخ پیام قبلی (در تمامی سرویس‌ها)
    busy_guard = UserBusyMiddleware()
    dp.message.outer_middleware(busy_guard)
    dp.callback_query.outer_middleware(busy_guard)

    # 🛡️ سپر دوم: مدیریت نرخ درخواست‌ها و ضد اسپم (Rate Limiting & Anti-DoS)
    throttling = ThrottlingMiddleware()
    dp.message.middleware(throttling)
    dp.callback_query.middleware(throttling)

    # 🛡️ سپر سوم: قفل اجباری عضویت در کانال (Channel Force-Join Guard)
    channel_guard = ChannelLockMiddleware()
    dp.message.middleware(channel_guard)
    dp.callback_query.middleware(channel_guard)

    # Register handlers (Order matters: chat is last as fallback)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(account.router)
    dp.include_router(tools.router)
    dp.include_router(image.router)
    dp.include_router(video.router)
    dp.include_router(vision.router)
    dp.include_router(voice.router)
    dp.include_router(chat.router)

    # 🛡️ Global Error Handler: Catches all unhandled exceptions to prevent bot crash
    @dp.error()
    async def global_error_handler(event):
        logger.error(f"[OmniBot] Handled global exception ({type(event.exception).__name__}): {event.exception}")
        try:
            if event.update.message:
                await event.update.message.answer("⚠️ متاسفانه خطایی در پردازش رخ داد. لطفاً چند لحظه بعد تلاش فرمایید.")
            elif event.update.callback_query:
                await event.update.callback_query.answer("⚠️ خطایی رخ داد.", show_alert=False)
        except Exception:
            pass
        return True

    return dp

async def run_bot_polling():
    """Main entrypoint for running the bot in polling mode with 24/7 auto-recovery."""
    if not BOT_TOKEN:
        print("\n" + "=" * 60)
        print("⚠️ [خطا] توکن ربات تلگرام تنظیم نشده است!")
        print("لطفاً فایل .env را باز کنید و کلید زیر را تنظیم نمایید:")
        print("TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz")
        print("=" * 60 + "\n")
        return

    db = BotDatabase.get_instance()
    await db.init_db()

    # Load stored custom emoji for web search and thinking if present in database
    from app.bot import config as bcfg
    from app.bot import keyboards as bkb
    saved_search_emoji = await db.get_setting("custom_emoji_web_search", "")
    if saved_search_emoji:
        bcfg.CUSTOM_EMOJI_WEB_SEARCH = saved_search_emoji
        bkb.CUSTOM_EMOJI_WEB_SEARCH = saved_search_emoji
    saved_thinking_emoji = await db.get_setting("custom_emoji_thinking", "")
    if saved_thinking_emoji:
        bcfg.CUSTOM_EMOJI_THINKING = saved_thinking_emoji

    print("\n" + "=" * 60)
    print("🚀 ربات تلگرام OmniLLM با قابلیت اتصال پایدار ۲۴/۷ فعال شد!")
    print("🤖 آماده پاسخگویی به کاربران با بازیابی خودکار اتصال در صورت قطعی اینترنت.")
    print("=" * 60 + "\n")

    # Create dispatcher ONCE so routers are attached exactly once
    dp = create_dispatcher()

    while True:
        bot = None
        try:
            bot = create_bot()
            await bot.delete_webhook(drop_pending_updates=True)
            await setup_bot_commands(bot)
            await dp.start_polling(bot, handle_signals=False, close_bot_session=True)
        except (KeyboardInterrupt, SystemExit):
            print("\n🛑 ربات به صورت دستی متوقف شد.")
            break
        except BaseException as e:
            logger.error(f"[OmniLLMBot] Polling interrupted/error ({type(e).__name__}): {e}. Reconnecting in 5 seconds...")
            try:
                await dp.stop_polling()
            except Exception:
                pass
            await asyncio.sleep(5)
        finally:
            if bot and bot.session:
                try:
                    await bot.session.close()
                except Exception:
                    pass

if __name__ == "__main__":
    asyncio.run(run_bot_polling())
