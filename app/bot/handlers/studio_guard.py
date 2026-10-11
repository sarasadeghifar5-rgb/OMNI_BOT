from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.bot.database import BotDatabase
from app.config import get_model_capabilities

router = Router(name="studio_guard_router")
db = BotDatabase.get_instance()


# Helper utilities for studio model detection
async def is_studio_model_active(user_id: int) -> bool:
    """True when the user's selected model is an image or video generation studio."""
    user = await db.get_or_create_user(user_id)
    caps = get_model_capabilities(user.get("selected_model", "gemini"))
    return bool(caps.get("is_image_studio") or caps.get("is_video_studio"))


def studio_kind(model_id: str) -> str:
    """Returns 'image', 'video' or '' for the given model id."""
    caps = get_model_capabilities(model_id)
    if caps.get("is_image_studio"):
        return "image"
    if caps.get("is_video_studio"):
        return "video"
    return ""
