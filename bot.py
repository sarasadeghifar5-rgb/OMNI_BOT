"""
Main entry point for the Telegram AI Bot.
Runs the polling loop with aiogram 3.x.
"""
import os
import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from config import BOT_TOKEN, ADMIN_ID
from database import db
from handlers import register_routers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("TelegramAIBot")

async def setup_bot_commands(bot: Bot):
    """Sets the Telegram bot menu commands."""
    commands = [
        BotCommand(command="start", description="🚀 شروع و منوی اصلی"),
        BotCommand(command="models", description="🤖 انتخاب مدل هوش مصنوعی"),
        BotCommand(command="image", description="🎨 ساخت عکس با مدل هوشمند پرو"),
        BotCommand(command="edit", description="✏️ ادیت عکس با مدل هوشمند پرو"),
        BotCommand(command="animate", description="🎞 متحرک‌سازی عکس به ویدیو"),
        BotCommand(command="video", description="🎬 ساخت ویدیو با مدل هوشمند پرو"),
        BotCommand(command="clear", description="🗑 پاکسازی حافظه گفتگو"),
        BotCommand(command="help", description="ℹ️ راهنما و وضعیت"),
    ]
    await bot.set_my_commands(commands)

async def start_health_check_server(port: int):
    """Starts a minimal aiohttp web server for Render health checks and keep-alive."""
    async def handle_health(request):
        return web.Response(text="OK - AI Bot is running 24/7!", status=200)

    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Health-check web server started on port {port} (Render ready)")

async def main():
    logger.info("Initializing Database...")
    await db.init()

    # Start health-check web server if PORT is provided (Render / Cloud environment)
    port_env = os.environ.get("PORT")
    if port_env:
        try:
            port = int(port_env)
            await start_health_check_server(port)
        except Exception as e:
            logger.warning(f"Could not start health check web server on port {port_env}: {e}")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Register handlers
    register_routers(dp)

    # Set commands
    await setup_bot_commands(bot)

    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot connected successfully: @{bot_info.username} (ID: {bot_info.id})")
    logger.info(f"Admin ID configured: {ADMIN_ID}")
    logger.info("AI Bot is running and waiting for messages...")

    # Notify Admin on startup
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "🟢 **ربات هوش مصنوعی با موفقیت روشن شد و آنلاین است!**\n\n"
                "• کلیه سرویس‌ها (CleanAPIs, Agnes, Atria, Gemini) متصل هستند.\n"
                "• برای دسترسی به پنل مدیریت روی /admin بزنید."
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Could not send startup notice to admin: {e}")

    try:
        # Delete any pending webhooks before starting polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
