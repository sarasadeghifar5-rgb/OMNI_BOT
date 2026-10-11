import time
import asyncio
import collections
import logging
from typing import Dict, Any, Callable, Awaitable, Optional, Set
from contextlib import asynccontextmanager

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from app.bot.config import RATE_LIMIT_SECONDS, MAX_CONCURRENT_REQUESTS, ADMIN_IDS

logger = logging.getLogger("OmniShield")

# =========================================================================
# 🛡️ Multi-Tier Security Limits (لحظه، دقیقه، ساعت، روز و ماه)
# =========================================================================
BURST_MIN_INTERVAL = float(RATE_LIMIT_SECONDS or 0.8)  # حداقل فاصله بین ۲ پیام متوالی (ثانیه)
MAX_PER_MINUTE = 30                                    # سقف پیام در دقیقه
MAX_PER_HOUR = 180                                     # سقف پیام در ساعت
MAX_PER_DAY = 1000                                     # سقف پیام در روز (~۳۰,۰۰۰ در ماه)

# محدودیت‌های اختصاصی عملیات سنگین هوش مصنوعی
MIN_VIDEO_INTERVAL = 120.0                            # حداقل ۲ دقیقه فاصله بین ۲ ویدیو
MAX_VIDEOS_PER_DAY = 10                                # حداکثر ۱۰ ویدیو در روز
MIN_IMAGE_INTERVAL = 8.0                               # حداقل ۸ ثانیه فاصله بین ۲ عکس
MAX_IMAGES_PER_HOUR = 60                               # حداکثر ۶۰ عکس در ساعت

# سدهای امنیتی محتوا و ضد داس (Anti-DoS / Payload Bombs)
MAX_TEXT_LENGTH = 4000                                 # حداکثر طول مجاز متن پیام
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024                 # حداکثر حجم فایل/مدیا (۲۰ مگابایت)
MAX_QUEUE_WAITERS = 300                                # حداکثر ظرفیت مجاز صف انتظار سرور (افزایش‌یافته برای ترافیک سازمانی)


class UserRateTracker:
    """
    نگهداری تاریخچه درخواست‌های هر کاربر در پنجره‌های لغزان زمانی (Sliding Windows)
    """
    def __init__(self):
        self.last_instant: float = 0.0
        self.last_video: float = 0.0
        self.last_image: float = 0.0
        self.minute_window: collections.deque = collections.deque()
        self.hour_window: collections.deque = collections.deque()
        self.day_window: collections.deque = collections.deque()
        self.video_window: collections.deque = collections.deque()
        self.image_window: collections.deque = collections.deque()

    def prune(self, now: float):
        """حذف تمپ‌استمپ‌های قدیمی برای سبک نگه‌داشتن حافظه RAM"""
        while self.minute_window and now - self.minute_window[0] >= 60.0:
            self.minute_window.popleft()
        while self.hour_window and now - self.hour_window[0] >= 3600.0:
            self.hour_window.popleft()
        while self.day_window and now - self.day_window[0] >= 86400.0:
            self.day_window.popleft()
        while self.video_window and now - self.video_window[0] >= 86400.0:
            self.video_window.popleft()
        while self.image_window and now - self.image_window[0] >= 3600.0:
            self.image_window.popleft()

    def is_inactive(self, now: float) -> bool:
        """بررسی عدم فعالیت کاربر در ۲۴ ساعت گذشته جهت Garbage Collection"""
        return (now - self.last_instant) > 86400.0


BUSY_WAIT_MESSAGE = "⏳ **لطفاً منتظر بمانید تا پاسخ پیام قبلی داده شود.**"


class ConcurrencyManager:
    """
    مدیریت همزمانی سراسری سرور و حفاظت در برابر Overload و Starvation.
    همچنین مدیریت وضعیت پردازش فعال هر کاربر برای جلوگیری از ارسال پیام همزمان.
    """
    _global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    _user_locks: Dict[int, asyncio.Lock] = {}
    _meta_lock = asyncio.Lock()
    _active_count: int = 0
    _waiting_count: int = 0

    # ردیابی پیام‌های در حال پردازش کاربران
    _busy_users: Dict[int, float] = {}       # user_id -> timestamp when processing started
    _last_busy_warn: Dict[int, float] = {}   # user_id -> timestamp of last warning sent
    MAX_PROCESSING_TIMEOUT: float = 300.0    # سقف ۵ دقیقه برای جلوگیری از بن‌بست یا قفل ماندن ابدی

    @classmethod
    async def is_user_busy(cls, user_id: int) -> bool:
        """بررسی اینکه آیا کاربر در حال حاضر منتظر دریافت پاسخ است یا خیر"""
        async with cls._meta_lock:
            if user_id not in cls._busy_users:
                return False
            start_time = cls._busy_users[user_id]
            now = time.time()
            if now - start_time < cls.MAX_PROCESSING_TIMEOUT:
                return True
            # در صورت گذشت بیش از ۵ دقیقه، قفل به طور خودکار آزاد می‌شود
            logger.warning(f"[ConcurrencyManager] User {user_id} processing timed out after {now - start_time:.1f}s. Auto-releasing lock.")
            cls._busy_users.pop(user_id, None)
            return False

    @classmethod
    async def try_start_user_processing(cls, user_id: int) -> bool:
        """
        تلاش برای ثبت شروع پردازش پیام کاربر به صورت اتمیک.
        اگر کاربر از قبل درخواست در حال اجرا داشته باشد، False برمی‌گرداند.
        """
        async with cls._meta_lock:
            now = time.time()
            if user_id in cls._busy_users:
                start_time = cls._busy_users[user_id]
                if now - start_time < cls.MAX_PROCESSING_TIMEOUT:
                    return False
                logger.warning(f"[ConcurrencyManager] User {user_id} previous task timed out after {now - start_time:.1f}s. Auto-recovering.")
            cls._busy_users[user_id] = now
            return True

    @classmethod
    async def finish_user_processing(cls, user_id: int):
        """آزادسازی وضعیت کاربر پس از ارسال پاسخ یا برخورد با خطا"""
        async with cls._meta_lock:
            cls._busy_users.pop(user_id, None)

    @classmethod
    async def should_send_busy_warning(cls, user_id: int) -> bool:
        """کنترل نرخ ارسال پیام هشدار برای جلوگیری از اسپم و فلوود تلگرام"""
        async with cls._meta_lock:
            now = time.time()
            last_warn = cls._last_busy_warn.get(user_id, 0.0)
            if now - last_warn >= 1.5:
                cls._last_busy_warn[user_id] = now
                return True
            return False

    @classmethod
    async def get_user_lock(cls, user_id: int) -> asyncio.Lock:
        async with cls._meta_lock:
            if user_id not in cls._user_locks:
                cls._user_locks[user_id] = asyncio.Lock()
            return cls._user_locks[user_id]

    @classmethod
    def global_semaphore(cls) -> asyncio.Semaphore:
        return cls._global_semaphore

    @classmethod
    def is_overloaded(cls) -> bool:
        """تشخیص وضعیت بحرانی ترافیک سرور جهت جلوگیری از کرش"""
        return cls._waiting_count >= MAX_QUEUE_WAITERS

    @classmethod
    @asynccontextmanager
    async def acquire_slot(cls):
        """مدیریت شمارنده وظایف در صف و در حال اجرا"""
        cls._waiting_count += 1
        try:
            async with cls._global_semaphore:
                cls._waiting_count = max(0, cls._waiting_count - 1)
                cls._active_count += 1
                try:
                    yield
                finally:
                    cls._active_count = max(0, cls._active_count - 1)
        except Exception:
            cls._waiting_count = max(0, cls._waiting_count - 1)
            raise


class UserBusyMiddleware(BaseMiddleware):
    """
    🛡️ سپر هوشمند تک‌درخواستی کاربر (Single In-Flight Request Guard).
    تضمین می‌کند که اگر کاربر پیامی ارسال کرد، تا زمانی که پاسخ پیام قبلی داده نشده
    (چه پاسخ با موفقیت ارسال شود و چه به خطا برخورد کند)، در صورت ارسال هر پیام جدید،
    پیام «لطفاً منتظر بمانید تا پاسخ پیام قبلی داده شود» ارسال شده و درخواست جدید مسدود گردد.
    این سپر تمامی سرویس‌ها را به صورت یکپارچه و سراسری پوشش می‌دهد:
    (چت، نانو بنانا و ادیت عکس، استودیو ویدیو، بینایی ماشین، صوت و ویس، ابزارها و دستورات).
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        # قابلیت اضطراری آزادسازی قفل توسط ادمین‌های ربات
        if isinstance(event, Message) and event.text:
            cmd = event.text.strip().lower()
            if cmd in ("/unlock", "/reset_busy") and user_id in ADMIN_IDS:
                await ConcurrencyManager.finish_user_processing(user_id)
                await event.reply("🔓 **قفل پردازش کاربر با موفقیت بازنشانی شد.**", parse_mode="Markdown")
                return None

        acquired = await ConcurrencyManager.try_start_user_processing(user_id)
        if not acquired:
            # کاربر قبلاً درخواستی فرستاده که هنوز پاسخش آماده یا ارسال نشده است!
            if isinstance(event, Message):
                should_warn = await ConcurrencyManager.should_send_busy_warning(user_id)
                if should_warn:
                    try:
                        await event.reply(BUSY_WAIT_MESSAGE, parse_mode="Markdown")
                    except Exception:
                        try:
                            await event.answer(BUSY_WAIT_MESSAGE, parse_mode="Markdown")
                        except Exception:
                            pass
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer("⏳ لطفاً منتظر بمانید تا پاسخ پیام قبلی داده شود.", show_alert=True)
                except Exception:
                    pass
            return None

        # اجرای کامل هندلر با تضمین آزادسازی قفل در هر شرایطی (پاسخ موفق یا خطا)
        try:
            return await handler(event, data)
        finally:
            await ConcurrencyManager.finish_user_processing(user_id)


class ThrottlingMiddleware(BaseMiddleware):
    """
    سپر امنیتی چندلایه و کنترل نرخ درخواست‌ها (Multi-Tier Rate Limiter & Anti-DoS).
    پوشش کامل:
    ۱. مهار ارسال‌های رگباری لحظه‌ای (Burst Pacing)
    ۲. سهمیه دقیقه‌ای (Per Minute)
    ۳. سهمیه ساعتی (Per Hour)
    ۴. سهمیه روزانه و ماهانه (Daily / Monthly)
    ۵. سهمیه سنگین ویدیو و تصویر (Heavy Operations Guard)
    ۶. بمباران متن‌های غول‌آسا و فایل‌های سنگین (Payload Bomb Guard)
    ۷. جلوگیری از سرریز صف سرور (Backpressure Guard)
    ۸. مصونیت ادمین‌های ربات (Admin Bypass)
    ۹. پاکسازی خودکار دوره‌ای حافظه (Auto Memory Cleanup)
    """
    def __init__(self, limit: float = BURST_MIN_INTERVAL):
        super().__init__()
        self.limit = limit
        self.trackers: Dict[int, UserRateTracker] = {}
        self.lock = asyncio.Lock()
        self.last_cleanup: float = time.time()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        # ۱. ادمین‌های ربات هیچ‌گاه لیمیت نمی‌شوند
        if user_id in ADMIN_IDS:
            return await handler(event, data)

        # ۲. سد دفاعی اندازه محتوا (Anti-Payload Bomb Guard)
        if isinstance(event, Message):
            # بررسی طول متن
            if event.text and len(event.text) > MAX_TEXT_LENGTH:
                await event.answer("⚠️ طول پیام شما بیش از حد مجاز است (حداکثر ۴۰۰۰ کاراکتر). لطفاً پیام خود را خلاصه‌تر ارسال فرمایید.")
                return None

            # بررسی حجم فایل و رسانه‌های ارسالی
            file_size = 0
            if event.photo:
                file_size = event.photo[-1].file_size or 0
            elif event.voice:
                file_size = event.voice.file_size or 0
            elif event.audio:
                file_size = event.audio.file_size or 0
            elif event.video:
                file_size = event.video.file_size or 0
            elif event.document:
                file_size = event.document.file_size or 0

            if file_size > MAX_FILE_SIZE_BYTES:
                await event.answer("⚠️ حجم فایل ارسالی بیش از سقف مجاز (۲۰ مگابایت) است. لطفاً فایل کم‌حجم‌تری ارسال فرمایید.")
                return None

        # ۳. سد دفاعی سرریز صف سرور (Server Overload / Backpressure Guard)
        if ConcurrencyManager.is_overloaded():
            if isinstance(event, Message):
                await event.answer("🚦 ترافیک سرور در حال حاضر بسیار بالاست. برای حفظ کیفیت و پایداری، لطفاً ۱ دقیقه دیگر پیام خود را مجدداً ارسال فرمایید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚦 سرور موقتاً شلوغ است. لطفاً کمی بعد کلیک کنید.", show_alert=True)
            return None

        # ۴. ارزیابی سهمیه‌ها در پنجره‌های زمانی (کاملاً موازی و غیرمسدودکننده بین کاربران)
        now = time.time()
        
        # پاکسازی خودکار دوره‌ای حافظه هر ۱۵ دقیقه
        if now - self.last_cleanup > 900.0:
            self.last_cleanup = now
            dead_uids = [uid for uid, trk in list(self.trackers.items()) if trk.is_inactive(now)]
            for uid in dead_uids:
                self.trackers.pop(uid, None)

        if user_id not in self.trackers:
            self.trackers[user_id] = UserRateTracker()

        trk = self.trackers[user_id]
        trk.prune(now)

        # تشخیص عملیات ویدیو
        text_str = ""
        if isinstance(event, Message):
            text_str = (event.text or event.caption or "").strip()
        elif isinstance(event, CallbackQuery):
            text_str = (event.data or "").strip()

        is_video_req = (
            text_str.startswith("/video") or
            text_str.startswith("video_") or
            any(text_str.startswith(p) for p in ["ویدیو بساز", "کلیپ بساز", "فیلم بساز"])
        )
        if is_video_req:
            if now - trk.last_video < MIN_VIDEO_INTERVAL:
                rem_sec = int(MIN_VIDEO_INTERVAL - (now - trk.last_video))
                mins, secs = divmod(rem_sec, 60)
                msg_time = f"{mins} دقیقه و {secs} ثانیه" if mins else f"{secs} ثانیه"
                if isinstance(event, Message):
                    await event.answer(f"⏳ پردازش و رندر ویدیو نیازمند توان بالای پردازشی است. لطفاً {msg_time} دیگر صبر کنید.")
                elif isinstance(event, CallbackQuery):
                    await event.answer(f"⏳ لطفاً {msg_time} دیگر صبر کنید.", show_alert=True)
                return None

            if len(trk.video_window) >= MAX_VIDEOS_PER_DAY:
                if isinstance(event, Message):
                    await event.answer("⚠️ سقف مجاز روزانه شما برای تولید ویدیو (۱۰ ویدیو در روز) تکمیل شده است. سهمیه شما فردا شارژ می‌شود.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ سقف روزانه ویدیو پر شده است.", show_alert=True)
                return None

        # تشخیص عملیات تصویر
        is_image_req = (
            text_str.startswith("/image") or
            any(text_str.startswith(p) for p in ["عکس بساز", "تصویر بساز", "یک عکس از", "یک تصویر از"])
        )
        if is_image_req:
            if now - trk.last_image < MIN_IMAGE_INTERVAL:
                rem_sec = int(MIN_IMAGE_INTERVAL - (now - trk.last_image))
                if isinstance(event, Message):
                    await event.answer(f"⏳ لطفاً بین درخواست‌های تولید تصویر حداقل {rem_sec} ثانیه مکث کنید.")
                elif isinstance(event, CallbackQuery):
                    await event.answer(f"⏳ لطفاً {rem_sec} ثانیه مکث کنید.", show_alert=False)
                return None

            if len(trk.image_window) >= MAX_IMAGES_PER_HOUR:
                if isinstance(event, Message):
                    await event.answer("⚠️ سقف مجاز ساعتی شما برای تولید عکس (۶۰ تصویر در ساعت) تکمیل شده است. لطفاً در ساعت بعد مراجعه فرمایید.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ سقف ساعتی تولید تصویر پر شد.", show_alert=True)
                return None

        # الف) بررسی لحظه‌ای (Burst - حداقل ۰.۸ ثانیه مکث)
        if now - trk.last_instant < self.limit:
            if isinstance(event, Message):
                await event.answer("⏳ لطفاً کمی صبور باشید و بین ارسال پیام‌ها مکث کنید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⏳ لطفاً کمی صبور باشید.", show_alert=False)
            return None

        # ب) بررسی در دقیقه (حداکثر ۳۰ پیام در ۶۰ ثانیه)
        if len(trk.minute_window) >= MAX_PER_MINUTE:
            if isinstance(event, Message):
                await event.answer("⚠️ شما به سقف مجاز (۳۰ درخواست در دقیقه) رسیدید. لطفاً ۱ دقیقه بعد تلاش فرمایید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ لطفاً ۱ دقیقه صبر کنید.", show_alert=True)
            return None

        # ج) بررسی در ساعت (حداکثر ۱۸۰ پیام در ساعت)
        if len(trk.hour_window) >= MAX_PER_HOUR:
            if isinstance(event, Message):
                await event.answer("⚠️ سقف مجاز ساعتی شما (۱۸۰ درخواست در ساعت) تکمیل شده است. لطفاً در ساعت بعد مراجعه فرمایید.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ سقف ساعتی پر شد.", show_alert=True)
            return None

        # د) بررسی در روز و ماه (حداکثر ۱۰۰۰ پیام در روز - معادل ۳۰,۰۰۰ در ماه)
        if len(trk.day_window) >= MAX_PER_DAY:
            if isinstance(event, Message):
                await event.answer("⚠️ سقف استفاده روزانه شما تکمیل شده است. سهمیه شما ساعت ۰۰:۰۰ بامداد تمدید می‌شود.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ سقف روزانه پر شد.", show_alert=True)
            return None

        # ثبت تایم‌استمپ‌های موفق
        trk.last_instant = now
        trk.minute_window.append(now)
        trk.hour_window.append(now)
        trk.day_window.append(now)
        if is_video_req:
            trk.last_video = now
            trk.video_window.append(now)
        if is_image_req:
            trk.last_image = now
            trk.image_window.append(now)

        return await handler(event, data)


class ChannelLockMiddleware(BaseMiddleware):
    """
    سپر قفل کانال (Channel Force-Join Middleware).
    در صورت فعال بودن قفل کانال در پنل مدیریت:
    - ادمین‌های ربات بدون محدودیت عبور می‌کنند.
    - کلیک روی دکمه «بررسی عضویت» اجازه عبور دارد تا وضعیت عضویت سنجیده شود.
    - سایر کاربران عادی تا زمان پیوستن به کانال مسدود شده و پیام عضویت اجباری با لینک دریافت می‌کنند.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        from aiogram.enums import ChatMemberStatus
        from app.bot.database import BotDatabase

        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        # 1. Admin bypass
        if user_id in ADMIN_IDS:
            return await handler(event, data)

        # 2. Allow channel verification callback
        if isinstance(event, CallbackQuery) and event.data == "check_channel_join":
            return await handler(event, data)

        db = BotDatabase.get_instance()

        # 3. Check if user is banned
        if await db.is_user_banned(user_id):
            if isinstance(event, Message):
                await event.answer("🚫 دسترسی شما به این ربات مسدود شده است.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 حساب کاربری شما مسدود است.", show_alert=True)
            return None

        # 4. Check if channel lock is enabled
        lock_info = await db.get_channel_lock_info()
        if not lock_info["enabled"] or not lock_info["channel_id"]:
            return await handler(event, data)

        channel_id = lock_info["channel_id"].strip()
        channel_link = lock_info["channel_link"].strip() or (f"https://t.me/{channel_id.lstrip('@')}" if channel_id.startswith('@') else channel_id)
        target_chat_id = int(channel_id) if ((channel_id.startswith("-") and channel_id[1:].isdigit()) or channel_id.isdigit()) else channel_id

        bot = data.get("bot")
        if bot:
            try:
                member = await bot.get_chat_member(chat_id=target_chat_id, user_id=user_id)
                if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                    return await handler(event, data)
            except Exception as e:
                logger.warning(f"[ChannelLockMiddleware] Could not verify membership for user {user_id} in {channel_id}: {e}")
                # If error (e.g. invalid channel ID or bot not in channel), do not lock users out
                return await handler(event, data)

        # User is not joined!
        from app.bot.keyboards import get_channel_force_join_keyboard
        lock_msg = (
            "📢 **عضویت در کانال الزامی است!**\n\n"
            "برای استفاده از خدمات هوش مصنوعی و امکانات ربات، لطفاً ابتدا در کانال رسمی ما عضو شوید:\n\n"
            f"👉 {channel_link}\n\n"
            "سپس جهت شروع روی دکمه «🔄 بررسی عضویت و ورود به ربات» کلیک فرمایید:"
        )
        markup = get_channel_force_join_keyboard(channel_link)

        if isinstance(event, Message):
            await event.answer(lock_msg, reply_markup=markup, parse_mode="Markdown")
        elif isinstance(event, CallbackQuery):
            await event.answer("⚠️ لطفاً ابتدا در کانال عضو شوید.", show_alert=True)
            try:
                await event.message.answer(lock_msg, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                pass
        return None


class ActivityTrackingMiddleware(BaseMiddleware):
    """
    📊 ردیابی بلادرنگ فعالیت تمامی کاربران (Real-Time Activity & Analytics Tracker).
    تضمین می‌کند که هر کاربری که با ربات تعامل دارد (پیام، دکمه، عکس، ویدیو، وویس، دستورات)
    به صورت بلادرنگ و با بالاترین دقت در دیتابیس و آمار پنل مدیریت ثبت گردد.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        from app.bot.database import BotDatabase

        user = None
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user and not user.is_bot:
            db = BotDatabase.get_instance()
            try:
                await db.touch_user_activity(
                    user_id=user.id,
                    username=user.username or "",
                    first_name=user.first_name or ""
                )
            except Exception as e:
                logger.warning(f"[ActivityTracking] Error recording activity for {user.id}: {e}")

        return await handler(event, data)


