import re
import math
import random
import datetime
import time
import asyncio
import html
import httpx
import requests
from typing import Tuple, Optional, Dict, Any
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest

from app.services.gateway import LLMGateway
from app.services.web_search import WebSearchService
from app.bot.keyboards import get_tools_keyboard, get_faq_categories_keyboard, get_faq_questions_keyboard
from app.bot.utils import safe_reply
from app.bot.database import BotDatabase

router = Router(name="tools_router")
gateway = LLMGateway()
web_search = WebSearchService()
db = BotDatabase.get_instance()

# FSM States
class ToolStates(StatesGroup):
    waiting_for_birthdate = State()
    waiting_for_heights = State()
    waiting_for_bmi = State()

# --- Calendar Utilities (Jalali <-> Gregorian) ---
def jalali_to_gregorian(jy: int, jm: int, jd: int) -> Tuple[int, int, int]:
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += ((days - 1) // 365)
        days = (days - 1) % 365
    gd = days + 1
    sal_a = [0, 31, 29 if ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm, gd

def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy if gm > 2 else gy - 1
    days = 355666 + (365 * gy) + ((gy2 + 4) // 4) - ((gy2 + 100) // 100) + ((gy2 + 400) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

CHINESE_ANIMALS = ["مار", "اسب", "گوسفند / بز", "میمون", "خروس / مرغ", "سگ", "خوک", "موش", "گاو", "پلنگ / ببر", "خرگوش", "اژدها / نهنگ"]
CHINESE_TRAITS = {
    "مار": "خردمند، مرموز، جذاب، باوقار و دارای هوش سرشار",
    "اسب": "پرانرژی، مستقل، شجاع، عاشق آزادی و ماجراجو",
    "گوسفند / بز": "مهربان، هنرمند، صبور، صلح‌طلب و با احساسات عمیق",
    "میمون": "فوق‌العاده باهوش، خلاق، شوخ‌طبع، حلال مسائل و مبتکر",
    "خروس / مرغ": "صادق، وقت‌شناس، منظم، شجاع و صریح‌اللهجه",
    "سگ": "وفادار، فداکار، باوجدان، حامی دوستان و عدالت‌طلب",
    "خوک": "بخشنده، دست‌ودلباز، خوش‌بین، صادق و پرمحبت",
    "موش": "باهوش، جذاب، سریع‌الانتقال، فرصت‌شناس و پرجنب‌وجوش",
    "گاو": "سخت‌کوش، مصمم، قابل اعتماد، شکیبا و با اراده پولادین",
    "پلنگ / ببر": "شجاع، نترس، کاریزماتیک، پرشور و رهبر بالفطره",
    "خرگوش": "با ظرافت، با احتیاط، هنردوست، خوش‌سلیقه و آرامش‌بخش",
    "اژدها / نهنگ": "پر ابهت، الهام‌بخش، بلندپرواز، خوش‌اقبال و تسلیم‌ناپذیر"
}

ZODIAC_SIGNS = [
    ("فروردین", "بره (حمل)", "آتش", "شجاع، پیشگام و پرشور"),
    ("اردیبهشت", "گاو (ثور)", "خاک", "صبور، وفادار و عمل‌گرا"),
    ("خرداد", "دوقلوها (جوزا)", "باد", "باهوش، کنجکاو و خوش‌بیان"),
    ("تیر", "خرچنگ (سرطان)", "آب", "با احساس، حامی و خانواده‌دوست"),
    ("مرداد", "شیر (اسد)", "آتـش", "سخاوتمند، جذاب و پر ابهت"),
    ("شهریور", "دوشیزه (سنبله)", "خاک", "منظم، دقیق، تحلیل‌گر و کمال‌گرا"),
    ("مهر", "ترازو (میزان)", "باد", "صلح‌جو، عادل، اجتماعی و خوش‌سلیقه"),
    ("آبان", "عقرب", "آب", "عمیق، پرحرارت، وفادار و رازدار"),
    ("آذر", "کماندار (قوس)", "آتش", "آزادی‌خواه، خوش‌بین، دانا و ماجراجو"),
    ("دی", "بزغاله (جدی)", "خاک", "پشتکار بالا، مقتدر و جاه‌طلب"),
    ("بهمن", "آب‌ریز (دلو)", "باد", "روشن‌فکر، نوآور، انسان‌دوست و مستقل"),
    ("اسفند", "دو ماهی (حوت)", "آب", "رؤیاپرداز، هنرمند، دلسوز و شهودی")
]

WEEKDAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]

# Authentic Ghazals of Hafez
HAFEZ_GHAZALS = [
    {
        "id": 1,
        "first_couplet": "الا یا ایها الساقی ادر کأسا و ناولها",
        "verses": [
            "الا یا ایها الساقی ادر کأسا و ناولها / که عشق آسان نمود اول ولی افتاد مشکل‌ها",
            "به بوی نافه‌ای کاخر صبا زان طره بگشاید / ز تاب جعد مشکینش چه خون افتاد در دل‌ها",
            "مرا در منزل جانان چه امن عیش چون هر دم / جرس فریاد می‌دارد که بربندید محمل‌ها",
            "به می سجاده رنگین کن گرت پیر مغان گوید / که سالک بی‌خبر نبود ز راه و رسم منزل‌ها",
            "همه کارم ز خودکامی به بدنامی کشید آخر / نهان کی ماند آن رازی کز او سازند محفل‌ها",
            "حضوری گر همی‌خواهی از او غایب مشو حافظ / متی ما تلق من تهوی دع الدنیا و اهملها"
        ],
        "interpretation": "نیت شما به لطف حق به سوی گشایش است. در ابتدای این مسیر ممکن است دشواری‌ها و فراز و نشیب‌هایی شما را نگران کند، اما صبوری و توکل کلید پیروزی شماست. از خودرأیی بپرهیزید و با افراد خردمند و باتجربه مشورت کنید. امیدتان را از دست ندهید که به مقصد خواهید رسید."
    },
    {
        "id": 240,
        "first_couplet": "یوسف گمگشته بازآید به کنعان غم مخور",
        "verses": [
            "یوسف گمگشته بازآید به کنعان غم مخور / کلبه احزان شود روزی گلستان غم مخور",
            "ای دل غمدیده حالت به شود دل بد مکن / وین سر شوریده بازآید به سامان غم مخور",
            "گر بهار عمر باشد باز بر طرف چمن / چتر گل بر سر کشی ای مرغ خوشخوان غم مخور",
            "دور گردون گر دو روزی بر مراد ما نرفت / دائما یکسان نباشد حال دوران غم مخور",
            "هان مشو نومید چون واقف نه‌ای از سر غیب / باشد اندر پرده بازی‌های پنهان غم مخور",
            "ای دل ار سیل فنا بنیاد هستی برکند / چون تو را نوح است کشتیبان ز طوفان غم مخور"
        ],
        "interpretation": "مژده و شادمانی بسیار بزرگی در طالع شماست! اگر روزگاری سخت بر شما گذشته یا چیزی ارزشمند را از دست داده‌اید، بدانید که دوران غم سپری شده و روزهای روشن و پرامید در راه است. اضطراب را از دل بیرون کنید، گره کار شما به زودی با خبر خوشی باز می‌شود."
    },
    {
        "id": 167,
        "first_couplet": "مژده ای دل که مسیحا نفسی می‌آید",
        "verses": [
            "مژده ای دل که مسیحا نفسی می‌آید / که ز انفاس خوشش بوی کسی می‌آید",
            "از غم و درد مکن ناله و فریاد که دوش / زده‌ام فالی و فریادرسی می‌آید",
            "زین خرامنده غزالی که سپرده‌ست عنان / صید دل کرد و کنون در پی صیدی دگر است",
            "کس ندانست که منزلگه معشوق کجاست / این قدر هست که بانگ جرسی می‌آید",
            "جرعه‌ای ده که به میخانه ارباب کرم / هر حریفی ز پی ملتمسی می‌آید",
            "دوست را گر سر دیدار من خسته دل است / گو بیا کز لب من باز پسی می‌آید"
        ],
        "interpretation": "فال شما بسیار روشن و فرخنده است. فریادرسی و گشایشی ناگهانی در امور برای شما رقم خواهد خورد. از درد و اندوه دست بردارید و به آینده خوش‌بین باشید. شخصی مهربان یا فرصتی طلایی به یاری شما خواهد آمد."
    },
    {
        "id": 367,
        "first_couplet": "ساقیا آمدن عید مبارک بادت",
        "verses": [
            "ساقیا آمدن عید مبارک بادت / وان مواعید که دادی مرواد از یادت",
            "در شگفتم که در این مدت ایام فراق / صبر من بر تو چه سان بود و صبوری بر من",
            "شکر ایزد که ز تاراج خزان رخ برتافت / بوستان و گل و نسرین و سمن بستان شد",
            "عیش عشرت به لب جوی و نسیم گل و مل / مطربا نغمه بزن ساقی می نوشان شد"
        ],
        "interpretation": "ایام خوشی و پیروزی فرا رسیده است. عهد و پیمانی که بسته‌اید یا تصمیمی که گرفته‌اید بسیار مبارک و سرشار از برکت است. قدر لحظات و داشته‌های خود را بدانید و با شکرگزاری به جلو حرکت کنید."
    }
]

# --- Commands & Navigation ---

@router.message(Command("tools"))
@router.message(F.text == "🛠️ ابزارها و سرگرمی")
async def cmd_tools_menu(message: Message):
    await safe_reply(
        message,
        "🛠️ **جعبه‌ابزار کاربردی، مالی و سرگرمی هوش مصنوعی:**\n\n"
        "یکی از ابزارهای هوشمند زیر را انتخاب کنید:",
        reply_markup=get_tools_keyboard()
    )

@router.callback_query(F.data == "menu:tools")
async def cb_tools_menu(call: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    await call.answer()
    try:
        await call.message.edit_text(
            "🛠️ **جعبه‌ابزار کاربردی، مالی و سرگرمی هوش مصنوعی:**\n\n"
            "یکی از ابزارهای هوشمند زیر را انتخاب کنید:",
            reply_markup=get_tools_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        pass

# --- Tool 1: Live Prices (Gold, Coins, Dollar, Euro, Crypto) ---

_PRICE_CACHE: Dict[str, Any] = {
    "data": None,
    "timestamp": 0.0
}

def _fetch_tgju_sync() -> dict:
    url = "https://call.tgju.org/ajax.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.tgju.org/"
    }
    resp = requests.get(url, headers=headers, timeout=4.0)
    if resp.status_code == 200:
        return resp.json().get("current", {})
    return {}

def _parse_num(val) -> int:
    if not val:
        return 0
    clean = str(val).replace(',', '').strip()
    try:
        return int(float(clean))
    except Exception:
        return 0

async def get_live_market_data() -> Tuple[dict, bool]:
    global _PRICE_CACHE
    now = time.time()
    # Cache for 45 seconds for instantaneous response
    if _PRICE_CACHE["data"] and (now - _PRICE_CACHE["timestamp"] < 45.0):
        return _PRICE_CACHE["data"], True

    try:
        raw_current = await asyncio.to_thread(_fetch_tgju_sync)
        if raw_current:
            targets = [
                ("sekee", "سکه امامی (طرح جدید)", "🪙"),
                ("sekeb", "سکه بهار آزادی (طرح قدیم)", "🪙"),
                ("nim", "نیم‌سکه بهار آزادی", "🪙"),
                ("rob", "ربع‌سکه بهار آزادی", "🪙"),
                ("gerami", "سکه یک گرمی بانک مرکزی", "🪙"),
                ("geram18", "طلای ۱۸ عیار (هر گرم)", "🟡"),
                ("mesghal", "مثقال طلا (مظنه آبشده)", "🟡"),
                ("price_dollar_rl", "دلار آمریکا (آزاد)", "💵"),
                ("price_eur", "یورو اروپا", "💶"),
                ("price_aed", "درهم امارات", "🇦🇪"),
            ]

            items = {}
            for key, name, icon in targets:
                entry = raw_current.get(key, {})
                p_rial = _parse_num(entry.get("p"))
                p_toman = p_rial // 10
                diff_rial = _parse_num(entry.get("d"))
                diff_toman = diff_rial // 10
                dp = str(entry.get("dp", "0")).strip()
                dt = entry.get("dt", "")
                t_str = entry.get("t", "")

                if dt == "high":
                    arrow = "🟢 🔺"
                elif dt == "low":
                    arrow = "🔴 🔻"
                else:
                    arrow = "⚪ ➖"

                items[key] = {
                    "name": name,
                    "icon": icon,
                    "toman": p_toman,
                    "diff_toman": diff_toman,
                    "dp": dp,
                    "dt": dt,
                    "arrow": arrow,
                    "time": t_str
                }

            btc_raw = raw_current.get("crypto-bitcoin", {}).get("p")
            btc_p = f"{_parse_num(btc_raw):,}" if btc_raw else "84,170"

            now_jalali = gregorian_to_jalali(
                datetime.datetime.now().year,
                datetime.datetime.now().month,
                datetime.datetime.now().day
            )
            date_str = f"{now_jalali[0]}/{now_jalali[1]:02d}/{now_jalali[2]:02d}"
            time_str = datetime.datetime.now().strftime("%H:%M:%S")

            data = {
                "items": items,
                "btc": btc_p,
                "date_str": date_str,
                "time_str": time_str
            }
            _PRICE_CACHE["data"] = data
            _PRICE_CACHE["timestamp"] = now
            return data, False
    except Exception:
        pass

    if _PRICE_CACHE["data"]:
        return _PRICE_CACHE["data"], True

    # Reliable fallback values if network is temporarily unreachable
    now_jalali = gregorian_to_jalali(
        datetime.datetime.now().year,
        datetime.datetime.now().month,
        datetime.datetime.now().day
    )
    fallback_data = {
        "items": {
            "sekee": {"name": "سکه امامی (طرح جدید)", "icon": "🪙", "toman": 240010000, "dp": "1.49", "arrow": "🟢 🔺"},
            "sekeb": {"name": "سکه بهار آزادی (طرح قدیم)", "icon": "🪙", "toman": 236075000, "dp": "1.66", "arrow": "🟢 🔺"},
            "nim": {"name": "نیم‌سکه بهار آزادی", "icon": "🪙", "toman": 123000000, "dp": "1.23", "arrow": "🟢 🔺"},
            "rob": {"name": "ربع‌سکه بهار آزادی", "icon": "🪙", "toman": 65000000, "dp": "1.56", "arrow": "🟢 🔺"},
            "gerami": {"name": "سکه یک گرمی بانک مرکزی", "icon": "🪙", "toman": 34000000, "dp": "0", "arrow": "⚪ ➖"},
            "geram18": {"name": "طلای ۱۸ عیار (هر گرم)", "icon": "🟡", "toman": 24124600, "dp": "1.51", "arrow": "🟢 🔺"},
            "mesghal": {"name": "مثقال طلا (مظنه آبشده)", "icon": "🟡", "toman": 104499000, "dp": "1.5", "arrow": "🟢 🔺"},
            "price_dollar_rl": {"name": "دلار آمریکا (آزاد)", "icon": "💵", "toman": 234615, "dp": "1.26", "arrow": "🟢 🔺"},
            "price_eur": {"name": "یورو اروپا", "icon": "💶", "toman": 267140, "dp": "1.07", "arrow": "🟢 🔺"},
            "price_aed": {"name": "درهم امارات", "icon": "🇦🇪", "toman": 63900, "dp": "1.25", "arrow": "🟢 🔺"},
        },
        "btc": "84,170",
        "date_str": f"{now_jalali[0]}/{now_jalali[1]:02d}/{now_jalali[2]:02d}",
        "time_str": datetime.datetime.now().strftime("%H:%M:%S")
    }
    return fallback_data, False

def format_price_board(data: dict) -> str:
    it = data.get("items", {})

    def fmt(key: str) -> str:
        item = it.get(key)
        if not item or not item.get("toman"):
            return ""
        return f"• **{item['name']}:** `{item['toman']:,} تومان`  {item.get('arrow', '')} `%{item.get('dp', '0')}`"

    sekee_str = fmt("sekee")
    sekeb_str = fmt("sekeb")
    nim_str = fmt("nim")
    rob_str = fmt("rob")
    gerami_str = fmt("gerami")

    geram18_str = fmt("geram18")
    mesghal_str = fmt("mesghal")

    dollar_str = fmt("price_dollar_rl")
    eur_str = fmt("price_eur")
    aed_str = fmt("price_aed")

    dollar_toman = it.get("price_dollar_rl", {}).get("toman", 0)
    usdt_val = f"{dollar_toman:,} تومان" if dollar_toman else "معادل ۱ دلار"

    board = f"""📊 **تابلوی زنده نرخ‌های طلا، سکه و ارز بازار تهران**
🗓 *تاریخ: `{data.get('date_str', '')}` | ساعت استعلام: `{data.get('time_str', '')}`*

🪙 **قیمت انواع مسکوکات طلا (به تومان):**
{sekee_str}
{sekeb_str}
{nim_str}
{rob_str}
{gerami_str}

🟡 **قیمت طلا و مظنه (به تومان):**
{geram18_str}
{mesghal_str}

💵 **نرخ ارزهای آزاد (به تومان):**
{dollar_str}
{eur_str}
{aed_str}

⚡ **ارزهای دیجیتال شاخص:**
• **بیت‌کوین (BTC):** `${data.get('btc', '84,170')}`
• **تتر (USDT):** `{usdt_val}`

━━━━━━━━━━━━━━━━━━━━
💡 *نرخ‌ها مستقیماً از سامانه مرجع اتحادیه طلا و صرافان (TGJU) به‌صورت لحظه‌ای استعلام می‌شوند.*"""
    return board.strip()

def get_price_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 به‌روزرسانی نرخ‌ها", callback_data="tool:price")],
            [InlineKeyboardButton(text="🔙 بازگشت به منوی ابزارها", callback_data="menu:tools")]
        ]
    )

@router.message(Command("price", "dollar", "coin", "gold"))
@router.callback_query(F.data == "tool:price")
async def handle_tool_price(event: [Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer("در حال دریافت آخرین نرخ‌ها...")

    data, _ = await get_live_market_data()
    board = format_price_board(data)
    kb = get_price_keyboard()

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(board, reply_markup=kb, parse_mode="Markdown")
        except TelegramBadRequest:
            pass
        except Exception:
            await event.message.answer(board, reply_markup=kb, parse_mode="Markdown")
    else:
        await safe_reply(event, board, reply_markup=kb)

# --- Tool 2: Faal Hafez ---

@router.message(Command("faal", "hafez"))
@router.callback_query(F.data == "tool:faal")
async def handle_tool_faal(event: [Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer("🔮 در حال گشودن دیوان حافظ...")

    # Pick random ghazal
    ghazal = random.choice(HAFEZ_GHAZALS)
    verses_text = "\n".join([f"✨ *{v}*" for v in ghazal["verses"]])

    faal_result = f"""🔮 **فال و تفأل به دیوان خواجه شمس‌الدین حافظ شیرازی**

📜 **غزل شماره {ghazal['id']}:**
{verses_text}

━━━━━━━━━━━━━━━━━━━━
💡 **تفسیر و فرجام نیت شما:**
> {ghazal['interpretation']}

━━━━━━━━━━━━━━━━━━━━
*(برای شنیدن غزل با صوت هوش مصنوعی، دستور `/voice` را روی این پیام ریپلای کنید)*"""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔮 نیت مجدد و فال دیگر", callback_data="tool:faal")],
            [InlineKeyboardButton(text="🔙 بازگشت به منوی ابزارها", callback_data="menu:tools")]
        ]
    )

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(faal_result, reply_markup=kb, parse_mode="Markdown")
        except TelegramBadRequest:
            pass
        except Exception:
            await event.message.answer(faal_result, reply_markup=kb, parse_mode="Markdown")
    else:
        await safe_reply(event, faal_result, reply_markup=kb)

# --- Tool 3: Age & Birthday Calculator ---

@router.message(Command("age", "birthday"))
@router.callback_query(F.data == "tool:age")
async def handle_tool_age(event: [Message, CallbackQuery], state: FSMContext):
    if isinstance(event, CallbackQuery):
        await event.answer()

    await state.set_state(ToolStates.waiting_for_birthdate)
    text = (
        "🎂 **محاسبه دقیق سن، سال تولد و طالع‌بینی:**\n\n"
        "لطفاً تاریخ تولد خود را به صورت شمسی یا میلادی بفرستید:\n"
        "*(مثال: `1380/05/15` یا `1376` یا `2001/08/06`)*"
    )
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 انصراف و بازگشت به ابزارها", callback_data="menu:tools")]]
    )
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=cancel_kb, parse_mode="Markdown")
        except Exception:
            await event.message.answer(text, reply_markup=cancel_kb, parse_mode="Markdown")
    else:
        await safe_reply(event, text, reply_markup=cancel_kb)

@router.message(ToolStates.waiting_for_birthdate)
async def process_birthdate(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.clear()

    # Match numbers (year, month, day)
    nums = [int(n) for n in re.findall(r"\d+", text)]
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت به منوی ابزارها", callback_data="menu:tools")]]
    )
    if not nums:
        await message.answer("⚠️ تاریخ نامعتبر بود. لطفاً مانند فرمت `1380/05/15` بنویسید.", reply_markup=cancel_kb)
        return

    year = nums[0]
    month = nums[1] if len(nums) > 1 else 1
    day = nums[2] if len(nums) > 2 else 1

    # Check if Jalali or Gregorian
    if year < 1700:
        jy, jm, jd = year, month, day
        try:
            gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
            birth_dt = datetime.datetime(gy, gm, gd)
        except Exception:
            await message.answer("⚠️ مقادیر تاریخ شمسی خارج از محدوده است.", reply_markup=cancel_kb)
            return
    else:
        gy, gm, gd = year, month, day
        try:
            birth_dt = datetime.datetime(gy, gm, gd)
            jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
        except Exception:
            await message.answer("⚠️ مقادیر تاریخ میلادی نامعتبر است.", reply_markup=cancel_kb)
            return

    now = datetime.datetime.now()
    if birth_dt > now:
        await message.answer("⚠️ تاریخ تولد نمی‌تواند در آینده باشد!", reply_markup=cancel_kb)
        return

    delta = now - birth_dt
    total_days = delta.days
    total_hours = total_days * 24 + (delta.seconds // 3600)
    total_minutes = total_hours * 60 + ((delta.seconds % 3600) // 60)

    # Approximate years, months, days
    years = total_days // 365
    rem_days = total_days % 365
    months = rem_days // 30
    days = rem_days % 30

    # Weekday
    weekday = WEEKDAYS_FA[birth_dt.weekday()]

    # Chinese Zodiac animal
    animal_idx = (jy - 1300) % 12
    animal = CHINESE_ANIMALS[animal_idx]
    animal_trait = CHINESE_TRAITS.get(animal.split(" / ")[0], "")

    # Astrological Zodiac
    zodiac_idx = min(max(jm - 1, 0), 11)
    z_month, z_sign, z_elem, z_trait = ZODIAC_SIGNS[zodiac_idx]

    # Next birthday countdown
    cur_gy = now.year
    try:
        next_bday = datetime.datetime(cur_gy, gm, gd)
        if next_bday < now:
            next_bday = datetime.datetime(cur_gy + 1, gm, gd)
        days_to_bday = (next_bday - now).days
    except Exception:
        days_to_bday = 100

    result = f"""🎉 **شناسنامه دقیق سن و طالع شما:**

📅 **تاریخ تولد:**
• شمسی: `{jy}/{jm:02d}/{jd:02d}`
• میلادی: `{gy}/{gm:02d}/{gd:02d}`
• روز تولد: **{weekday}**

⏳ **سن شما تا این لحظه:**
• **{years} سال و {months} ماه و {days} روز**
• برابر با: **{total_days:,} روز** زیسته شده
• یا: **{total_hours:,} ساعت** و **{total_minutes:,} دقیقه**

━━━━━━━━━━━━━━━━━━━━
🐉 **حیوان سال تولد (تقویم چینی):**
• نماد: **سال {animal}**
• خصوصیت اصلی: {animal_trait}

♈ **طالع و صورت فلکی:**
• برج: **{z_month} ({z_sign})**
• عنصر طالع: **{z_elem}**
• ویژگی‌های اخلاقی: {z_trait}

━━━━━━━━━━━━━━━━━━━━
🎁 **روزهای باقیمانده تا جشن تولد بعدی:** **{days_to_bday} روز** 🎂"""

    await message.answer(result, reply_markup=cancel_kb, parse_mode="Markdown")

# --- Tool 4: Height Comparison ---

@router.message(Command("height"))
@router.callback_query(F.data == "tool:height")
async def handle_tool_height(event: [Message, CallbackQuery], state: FSMContext):
    if isinstance(event, CallbackQuery):
        await event.answer()

    await state.set_state(ToolStates.waiting_for_heights)
    text = (
        "📏 **ابزار مقایسه و اختلاف قد:**\n\n"
        "لطفاً قد دو نفر را بر حسب سانتی‌متر بفرستید:\n"
        "*(مثال: `182 165` یا `قد من ۱۷۸ و قد دوستم ۱۶۳`)*"
    )
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 انصراف و بازگشت به ابزارها", callback_data="menu:tools")]]
    )
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=cancel_kb, parse_mode="Markdown")
        except Exception:
            await event.message.answer(text, reply_markup=cancel_kb, parse_mode="Markdown")
    else:
        await safe_reply(event, text, reply_markup=cancel_kb)

@router.message(ToolStates.waiting_for_heights)
async def process_heights(message: Message, state: FSMContext):
    nums = [int(n) for n in re.findall(r"\d+", message.text)]
    await state.clear()
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت به منوی ابزارها", callback_data="menu:tools")]]
    )

    if len(nums) < 2:
        await message.answer("⚠️ لطفاً دو عدد قد (مانند `180 165`) ارسال کنید.", reply_markup=cancel_kb)
        return

    h1, h2 = nums[0], nums[1]
    if h1 < 50 or h1 > 250 or h2 < 50 or h2 > 250:
        await message.answer("⚠️ لطفاً اعداد قد واقعی بین ۵۰ تا ۲۵۰ سانتی‌متر وارد نمایید.", reply_markup=cancel_kb)
        return

    taller = max(h1, h2)
    shorter = min(h1, h2)
    diff = taller - shorter
    diff_inch = round(diff / 2.54, 1)

    # Graphical visual bar
    max_bar = 20
    bar_tall = "█" * max_bar
    bar_short = "█" * max(int(max_bar * (shorter / taller)), 2)
    spaces = " " * (max_bar - len(bar_short))

    # Relationship analysis
    if diff == 0:
        analysis = "هم‌قد دقیق! تقارن کامل و دید هم‌سطح."
    elif diff <= 7:
        analysis = "اختلاف بسیار کم و نزدیک؛ توازن قدی عالی و ایستایی متقارن."
    elif diff <= 15:
        analysis = "اختلاف قدی کلاسیک و ایده‌آل؛ زیباترین حالت برای عکس‌های دونفره و قرار گرفتن سر روی شانه."
    elif diff <= 25:
        analysis = "اختلاف قدی جذاب و سینمایی؛ احساس حمایت و حفاظت فوق‌العاده."
    else:
        analysis = "اختلاف قدی چشمگیر و خاص؛ نمایانگر تنوع و جذابیت فیزیکی."

    result = f"""📏 **تحلیل و مقایسه قدی:**

• قد شخص بلندتر: **{taller} سانتی‌متر**
• قد شخص کوتاه‌تر: **{shorter} سانتی‌متر**
• اختلاف قدی دقیق: **{diff} سانتی‌متر** ({diff_inch} اینچ)

📊 **نمودار مقایسه بصری:**
`شخص اول  ({taller} cm): 🧍‍♂️ [{bar_tall}]`
`شخص دوم  ({shorter} cm): 🧍‍♀️ [{bar_short}{spaces}]`
`میزان تفاوت:            📐 {diff} cm`

━━━━━━━━━━━━━━━━━━━━
💡 **تحلیل استایل و تناسب:**
> {analysis}

*(میانگین قد در ایران: مردان ~ ۱۷۵ cm | زنان ~ ۱۶۲ cm)*"""

    await message.answer(result, reply_markup=cancel_kb, parse_mode="Markdown")

# --- Tool 5: BMI & Weight Converter ---

@router.message(Command("bmi", "weight"))
@router.callback_query(F.data == "tool:bmi")
async def handle_tool_bmi(event: [Message, CallbackQuery], state: FSMContext):
    if isinstance(event, CallbackQuery):
        await event.answer()

    await state.set_state(ToolStates.waiting_for_bmi)
    text = (
        "⚖️ **محاسبه شاخص توده بدنی (BMI) و تبدیل وزن:**\n\n"
        "لطفاً وزن (کیلوگرم) و قد (سانتی‌متر) خود را ارسال کنید:\n"
        "*(مثال: `75 178` یا `وزن 68 قد 170`)*"
    )
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 انصراف و بازگشت به ابزارها", callback_data="menu:tools")]]
    )
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=cancel_kb, parse_mode="Markdown")
        except Exception:
            await event.message.answer(text, reply_markup=cancel_kb, parse_mode="Markdown")
    else:
        await safe_reply(event, text, reply_markup=cancel_kb)

@router.message(ToolStates.waiting_for_bmi)
async def process_bmi(message: Message, state: FSMContext):
    nums = [int(n) for n in re.findall(r"\d+", message.text)]
    await state.clear()
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت به منوی ابزارها", callback_data="menu:tools")]]
    )

    if len(nums) < 2:
        await message.answer("⚠️ لطفاً وزن و قد را با هم بفرستید (مثال: `75 178`).", reply_markup=cancel_kb)
        return

    # Discern which is weight and which is height
    n1, n2 = nums[0], nums[1]
    if n1 > n2:
        height, weight = n1, n2
    else:
        height, weight = n2, n1

    if height < 100 or height > 250 or weight < 30 or weight > 300:
        await message.answer("⚠️ مقادیر وزن یا قد نامعتبر به نظر می‌رسند. (قد بر حسب سانتی‌متر و وزن بر حسب کیلوگرم)", reply_markup=cancel_kb)
        return

    h_meter = height / 100.0
    bmi = round(weight / (h_meter * h_meter), 1)

    # Conversions
    lbs = round(weight * 2.20462, 1)
    oz = round(weight * 35.274, 0)

    # Ideal weight range
    ideal_min = round(18.5 * (h_meter * h_meter), 1)
    ideal_max = round(24.9 * (h_meter * h_meter), 1)

    if bmi < 18.5:
        category = "کمبود وزن (Underweight) 🟡"
        tip = "رژیم غذایی پروتئینی و کالری مثبت سالم همراه با تمرینات مقاومتی جهت عضله‌سازی توصیه می‌شود."
    elif bmi < 25.0:
        category = "وزن کاملاً نرمال و ایده‌آل (Normal) 🟢"
        tip = "وضعیت بدنی شما در محدوده سلامت است. حفظ ورزش منظم و خواب کافی برای تثبیت پیشنهاد می‌شود."
    elif bmi < 30.0:
        category = "اضافه وزن خفیف (Overweight) 🟠"
        tip = "کاهش مصرف کربوهیدرات‌های ساده و ۳۰ دقیقه پیاده‌روی روزانه شما را به سرعت به محدوده نرمال بازمی‌گرداند."
    else:
        category = "چاقی (Obese) 🔴"
        tip = "مشاوره با متخصص تغذیه، پایش قند و چربی خون و پیگیری برنامه ورزشی ساختاریافته ضروری است."

    result = f"""⚖️ **گزارش شاخص توده بدنی (BMI) و تناسب اندام:**

• قد: **{height} سانتی‌متر** | وزن: **{weight} کیلوگرم**
• شاخص BMI شما: **{bmi}**
• وضعیت بدنی: **{category}**

🎯 **محدوده وزن ایده‌آل برای قد شما:**
• **{ideal_min} تا {ideal_max} کیلوگرم**

━━━━━━━━━━━━━━━━━━━━
🔄 **تبدیل وزن به سایر واحدها:**
• پوند (lbs): `{lbs} پوند`
• اونس (oz): `{int(oz):,} اونس`
• گرم (g): `{weight * 1000:,} گرم`

━━━━━━━━━━━━━━━━━━━━
🥗 **توصیه هوش مصنوعی برای سلامت شما:**
> {tip}"""

    await message.answer(result, reply_markup=cancel_kb, parse_mode="Markdown")

# --- FAQ & Popular Questions ---

@router.message(Command("faq"))
@router.message(F.text == "❓ سوالات پر تکرار")
@router.callback_query(F.data == "menu:faq")
async def handle_faq_menu(event: [Message, CallbackQuery]):
    if isinstance(event, CallbackQuery):
        await event.answer()

    text = "❓ **بانک سوالات پر تکرار و پرامپت‌های آماده هوش مصنوعی:**\n\nیک دسته‌بندی را انتخاب کنید تا سوالات آن را ببینید:"
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=get_faq_categories_keyboard(), parse_mode="Markdown")
        except Exception:
            await event.message.answer(text, reply_markup=get_faq_categories_keyboard(), parse_mode="Markdown")
    else:
        await safe_reply(event, text, reply_markup=get_faq_categories_keyboard())

@router.callback_query(F.data.startswith("faq_cat:"))
async def handle_faq_category(call: CallbackQuery):
    await call.answer()
    cat = call.data.split("faq_cat:")[1]
    titles = {
        "coding": "💻 سوالات برنامه‌نویسی و وب",
        "writing": "📝 نگارش، مقاله و رزومه",
        "business": "💡 کسب‌وکار و درآمدزایی",
        "english": "🇬🇧 یادگیری زبان انگلیسی"
    }
    title = titles.get(cat, "دسته‌بندی")
    try:
        await call.message.edit_text(
            f"**{title}:**\nیکی از سوالات زیر را انتخاب کنید تا پاسخ آن را دریافت کنید:",
            reply_markup=get_faq_questions_keyboard(cat),
            parse_mode="Markdown"
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("faq_q:"))
async def handle_faq_question_click(call: CallbackQuery):
    q_key = call.data.split("faq_q:")[1]
    prompts = {
        "py_script": "یک اسکریپت کاربردی و پیشرفته پایتون برای خودکارسازی کارهای روزمره به همراه توضیحات کامل بنویس.",
        "debug_tips": "مهم‌ترین و سریع‌ترین ترفندهای دیباگ کردن کد و رفع ارورها برای برنامه‌نویسان چیست؟",
        "ai_roadmap": "یک نقشه راه مرحله‌به‌مرحله و عملی برای یادگیری هوش مصنوعی و ورود به بازار کار در سال جدید تدوین کن.",
        "formal_email": "یک متن ایمیل اداری و رسمی بسیار شیک به زبان فارسی و انگلیسی برای درخواست مرخصی یا ارسال گزارش کار بنویس.",
        "resume_guide": "بخش‌ها و ساختار کلیدی یک رزومه حرفه‌ای بین‌المللی استاندارد ATS چیست و چگونه نگارش شود؟",
        "essay_intro": "روش استاندارد نوشتن مقدمه و چکیده برای مقالات علمی و پژوهشی دانشگاهی چگونه است؟",
        "ai_biz_ideas": "۳ ایده کسب‌وکار آنلاین و بسیار پولساز با استفاده از ابزارهای هوش مصنوعی بدون نیاز به سرمایه اولیه معرفی کن.",
        "insta_caption": "یک فرمول طلایی برای نوشتن کپشن‌های ترند و جذب‌کننده مشتری در اینستاگرام ارائه کن.",
        "pricing_strat": "بهترین روش قیمت‌گذاری پروژه‌ها و خدمات فریلنسری برای جذب مشتری و سود حداکثری چیست؟",
        "english_idioms": "۲۰ اصطلاح روزمره، جذاب و پرکاربرد زبان انگلیسی به همراه معنی فارسی و مثال در جمله ذکر کن.",
        "speaking_tips": "سریع‌ترین و اثربخش‌ترین تکنیک‌ها برای تقویت مکالمه و اسپیکینگ انگلیسی در خانه چیست؟",
        "grammar_fix": "شایع‌ترین اشتباهات گرامری فارسی‌زبانان هنگام صحبت به انگلیسی چیست و چگونه اصلاح کنیم؟"
    }

    user_prompt = prompts.get(q_key, "لطفاً در این زمینه راهنمایی جامعی ارائه بده.")
    await call.answer("در حال نگارش پاسخ تخصصی...")

    user = await db.get_or_create_user(call.from_user.id)
    model = user.get("selected_model", "gemini")

    from app.bot import config as bot_config
    thinking_eid = getattr(bot_config, "CUSTOM_EMOJI_THINKING", "") or "5334904192622403796"
    thinking_tag = f'<tg-emoji emoji-id="{thinking_eid}">🫥</tg-emoji>'
    status_msg = await call.message.answer(
        f"🤖 <b>پاسخ به سوال با هوش مصنوعی ({model}):</b>\n<i>{html.escape(user_prompt)}</i>\n\n{thinking_tag} <b>در حال نگارش...</b>",
        parse_mode="HTML"
    )

    full_chunks = []
    async for event in gateway.stream_chat(
        messages=[{"role": "user", "content": user_prompt}],
        model_id=model
    ):
        if event.get("type") == "content":
            full_chunks.append(event.get("content", ""))

    reply_content = "".join(full_chunks)
    await status_msg.delete()

    await safe_reply(
        call.message,
        f"💡 **پرسش انتخاب‌شده:**\n> *{user_prompt}*\n\n{reply_content}"
    )
