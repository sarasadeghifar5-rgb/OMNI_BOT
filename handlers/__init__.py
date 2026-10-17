"""
Handlers package router setup.
"""
from aiogram import Dispatcher
from handlers.start import router as start_router
from handlers.models import router as models_router
from handlers.agnes_media import router as media_router
from handlers.admin import router as admin_router
from handlers.chat import router as chat_router

def register_routers(dp: Dispatcher):
    """Register all routers in order of priority."""
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(models_router)
    dp.include_router(media_router)
    dp.include_router(chat_router)  # Chat router should be last to catch general text
