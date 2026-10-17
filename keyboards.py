"""
Keyboards for Telegram Bot: Main reply markup, model selection inline markup, photo actions, and admin panels.
Organized, clean, and ergonomic.
"""
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from config import ADMIN_ID, AVAILABLE_MODELS, ANIMATED_EMOJIS

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Returns the main reply keyboard with clean text and animated custom emoji icons."""
    buttons = [
        [
            KeyboardButton(
                text="تغییر مدل هوشمند",
                icon_custom_emoji_id=ANIMATED_EMOJIS["robot"]
            ),
            KeyboardButton(
                text="مدل هوشمند پرو",
                icon_custom_emoji_id=ANIMATED_EMOJIS["brain"]
            )
        ],
        [
            KeyboardButton(
                text="ساخت عکس",
                icon_custom_emoji_id=ANIMATED_EMOJIS["palette"]
            ),
            KeyboardButton(
                text="ادیت عکس",
                icon_custom_emoji_id=ANIMATED_EMOJIS["pencil"]
            )
        ],
        [
            KeyboardButton(
                text="تولید ویدیو",
                icon_custom_emoji_id=ANIMATED_EMOJIS["video"]
            ),
            KeyboardButton(
                text="متحرک‌سازی عکس",
                icon_custom_emoji_id=ANIMATED_EMOJIS["camera"]
            )
        ],
        [
            KeyboardButton(
                text="پاکسازی گفتگو",
                icon_custom_emoji_id=ANIMATED_EMOJIS["trash"]
            ),
            KeyboardButton(
                text="راهنما و وضعیت",
                icon_custom_emoji_id=ANIMATED_EMOJIS["info"]
            )
        ]
    ]

    # If user is admin, add admin panel button
    if user_id == ADMIN_ID:
        buttons.append([
            KeyboardButton(
                text="پنل مدیریت",
                icon_custom_emoji_id=ANIMATED_EMOJIS["gear"]
            )
        ])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="پیام یا دستور دلخواهت رو بفرست..."
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Cancel button when waiting for media prompts or photos."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="انصراف و بازگشت",
                icon_custom_emoji_id=ANIMATED_EMOJIS["cancel"]
            )
        ]],
        resize_keyboard=True
    )

def get_multi_photo_keyboard(count: int = 1) -> ReplyKeyboardMarkup:
    """Keyboard shown when collecting multiple photos for editing."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=f"تایید عکس‌ها - {count} عکس",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["check"]
                )
            ],
            [
                KeyboardButton(
                    text="انصراف و بازگشت",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["cancel"]
                )
            ]
        ],
        resize_keyboard=True
    )

def get_photo_actions_keyboard() -> InlineKeyboardMarkup:
    """Action buttons shown when user sends a photo with animated icons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ادیت تصویر",
                    callback_data="photo:edit",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["pencil"]
                ),
                InlineKeyboardButton(
                    text="متحرک‌سازی به ویدیو",
                    callback_data="photo:animate",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["camera"]
                )
            ],
            [
                InlineKeyboardButton(
                    text="تحلیل تصویر",
                    callback_data="photo:analyze",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["eye"]
                )
            ]
        ]
    )

def get_models_inline_keyboard(current_model: str) -> InlineKeyboardMarkup:
    """Clean, symmetrical 2-column inline keyboard with official animated custom emojis."""
    def btn(mid: str, label: str) -> InlineKeyboardButton:
        text = f"{label} ✅" if mid == current_model else label
        emoji_id = AVAILABLE_MODELS.get(mid, {}).get("custom_emoji_id")
        return InlineKeyboardButton(
            text=text,
            callback_data=f"set_model:{mid}",
            icon_custom_emoji_id=emoji_id
        )

    rows = [
        # Flagship models: Row 1 (OpenAI & Claude)
        [
            btn("gpt-5.6-sol", "GPT-5.6 Sol"),
            btn("claude-sonnet-5", "Claude 5")
        ],
        # Flagship models: Row 2 (DeepSeek & Claude Opus)
        [
            btn("deepseek-v4-pro-max", "DeepSeek V4"),
            btn("claude-opus-5.5", "Claude Opus")
        ],
        # Fast & Multimodal: Row 3 (Gemini & Qwen)
        [
            btn("gemini-3.7-flash", "Gemini 3.7"),
            btn("qwen3.8-max", "Qwen 3.8")
        ],
        # Deep Reasoning & Long Context: Row 4
        [
            btn("Atria-Dawn-Preview", "مدل هوشمند پرو"),
            btn("kimi-k3", "Kimi K3")
        ],
        # Google AI Studio & Pro Flash: Row 5
        [
            btn("gemini-flash-latest", "گوگل استودیو"),
            btn("agnes-3.0-flash", "پرو فلاش")
        ],
        # Close button: Row 6
        [
            InlineKeyboardButton(
                text="بستن منو",
                callback_data="close_models_menu",
                icon_custom_emoji_id=ANIMATED_EMOJIS["cancel"]
            )
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Admin panel control buttons with animated custom emojis."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="آمار ربات",
                    callback_data="admin_stats",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["chart"]
                ),
                InlineKeyboardButton(
                    text="وضعیت استخر کلیدها",
                    callback_data="admin_keys",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["key"]
                )
            ],
            [
                InlineKeyboardButton(
                    text="ارسال پیام همگانی",
                    callback_data="admin_broadcast",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["broadcast"]
                ),
            ],
            [
                InlineKeyboardButton(
                    text="بستن پنل",
                    callback_data="admin_close",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["door"]
                )
            ]
        ]
    )

def get_loading_keyboard(text: str = "در حال پردازش و استدلال هوشمند...") -> InlineKeyboardMarkup:
    """Returns an inline keyboard with an animated loading spinner."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data="loading_notice",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["loading"]
                )
            ]
        ]
    )
