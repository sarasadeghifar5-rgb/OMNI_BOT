"""
Progress and charging-bar helper for media generation and editing tasks.
No brackets or parentheses in the loading display.
"""
import asyncio
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import get_loading_keyboard
from config import ANIMATED_EMOJIS

def format_charging_bar(percent: int) -> str:
    """Creates a visual battery/charging progress bar with percentage without brackets or parentheses."""
    filled = max(0, min(10, int(percent / 10)))
    unfilled = 10 - filled
    bar = "■" * filled + "□" * unfilled

    if percent < 25:
        icon = "🪫"
        status_text = "آماده‌سازی و شروع پردازش"
    elif percent < 55:
        icon = "🔋"
        status_text = "شارژ و محاسبه فریم‌ها"
    elif percent < 85:
        icon = "⚡️🔋"
        status_text = "رندر و ارتقای کیفیت"
    elif percent < 100:
        icon = "⚡️"
        status_text = "ذخیره‌سازی و نهایی‌سازی فایل"
    else:
        icon = "✅"
        status_text = "پردازش ۱۰۰٪ تکمیل شد"

    # Clean display with no parentheses or brackets
    return f"{icon} **شارژ پردازش:** {percent}%\n{bar}\n_{status_text}_"

async def run_charging_progress(
    message: Message,
    title: str,
    stop_event: asyncio.Event,
    start_percent: int = 12,
    target_percent: int = 96,
    step_delay: float = 2.0
):
    """
    Gradually advances percentage and edits the Telegram message
    with an animated loading keyboard to give a live battery charging sensation until stop_event is set.
    """
    percent = start_percent
    while not stop_event.is_set():
        charging_text = f"{title}\n\n{format_charging_bar(percent)}"
        loading_markup = get_loading_keyboard(f"پردازش زنده: {percent}%")
        try:
            await message.edit_text(charging_text, parse_mode="Markdown", reply_markup=loading_markup)
        except Exception:
            pass

        # Advance percentage realistically
        if percent < 40:
            percent += 9
        elif percent < 70:
            percent += 7
        elif percent < 88:
            percent += 4
        elif percent < target_percent:
            percent += 2
        percent = min(target_percent, percent)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=step_delay)
            break
        except asyncio.TimeoutError:
            pass

    # Show 100% on complete
    try:
        final_text = f"{title}\n\n{format_charging_bar(100)}"
        complete_markup = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="پردازش ۱۰۰٪ تکمیل شد",
                    callback_data="loading_notice",
                    icon_custom_emoji_id=ANIMATED_EMOJIS["check"]
                )
            ]]
        )
        await message.edit_text(final_text, parse_mode="Markdown", reply_markup=complete_markup)
        await asyncio.sleep(0.6)
    except Exception:
        pass
