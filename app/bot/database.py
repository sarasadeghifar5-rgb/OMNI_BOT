import json
import time
import asyncio
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import aiosqlite
from app.bot.config import DB_PATH, DEFAULT_MODEL, DEFAULT_TTS_VOICE, MAX_HISTORY_TURNS, ADMIN_IDS, MAIN_ADMIN_ID, SECOND_ADMIN_ID

class BotDatabase:
    _instance: Optional["BotDatabase"] = None

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        # Enterprise in-memory fast caching for zero-latency lookups
        self._user_cache: Dict[int, tuple[Dict[str, Any], float]] = {}
        self._banned_cache: Dict[int, tuple[bool, float]] = {}
        self._vip_cache: Dict[int, tuple[bool, float]] = {}
        self._settings_cache: Dict[str, tuple[Any, float]] = {}

    @classmethod
    def get_instance(cls) -> "BotDatabase":
        if cls._instance is None:
            cls._instance = BotDatabase()
        return cls._instance

    @asynccontextmanager
    async def connect(self):
        async with aiosqlite.connect(self.db_path, timeout=60.0) as db:
            await db.execute("PRAGMA busy_timeout = 60000;")
            yield db

    async def init_db(self):
        """Initialize database schema with WAL mode for high concurrency."""
        async with self.connect() as db:
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")
            await db.execute("PRAGMA busy_timeout = 60000;")

            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    selected_model TEXT DEFAULT 'gemini',
                    web_search_enabled INTEGER DEFAULT 0,
                    tts_voice TEXT DEFAULT 'kore',
                    custom_api_keys TEXT DEFAULT '{}',
                    created_at REAL,
                    last_active REAL,
                    total_messages INTEGER DEFAULT 0,
                    region TEXT DEFAULT 'de',
                    last_gift_claim REAL DEFAULT 0,
                    credits INTEGER DEFAULT 50,
                    inviter_id INTEGER DEFAULT 0,
                    invited_count INTEGER DEFAULT 0,
                    is_vip INTEGER DEFAULT 0,
                    vip_until REAL DEFAULT 0,
                    stars_balance INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    image_ratio TEXT DEFAULT '1:1',
                    image_size TEXT DEFAULT '1K',
                    video_ratio TEXT DEFAULT '16:9',
                    video_seconds TEXT DEFAULT '5',
                    video_size TEXT DEFAULT '720P',
                    last_chat_model TEXT DEFAULT 'gemini-3.7-flash'
                )
            """)

            # Safe column migration for existing tables
            async with db.execute("PRAGMA table_info(users)") as cur:
                existing_cols = [row[1] for row in await cur.fetchall()]
            for col, c_type in [
                ("region", "TEXT DEFAULT 'de'"),
                ("last_gift_claim", "REAL DEFAULT 0"),
                ("credits", "INTEGER DEFAULT 50"),
                ("inviter_id", "INTEGER DEFAULT 0"),
                ("invited_count", "INTEGER DEFAULT 0"),
                ("is_vip", "INTEGER DEFAULT 0"),
                ("vip_until", "REAL DEFAULT 0"),
                ("stars_balance", "INTEGER DEFAULT 0"),
                ("is_banned", "INTEGER DEFAULT 0"),
                ("image_ratio", "TEXT DEFAULT '1:1'"),
                ("image_size", "TEXT DEFAULT '1K'"),
                ("video_ratio", "TEXT DEFAULT '16:9'"),
                ("video_seconds", "TEXT DEFAULT '5'"),
                ("video_size", "TEXT DEFAULT '720P'"),
                ("last_chat_model", "TEXT DEFAULT 'gemini-3.7-flash'")
            ]:
                if col not in existing_cols:
                    try:
                        await db.execute(f"ALTER TABLE users ADD COLUMN {col} {c_type};")
                    except Exception:
                        pass

            # Bot Settings Table (Channel lock, star pricing, runtime keys)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Transactions Table (Telegram Stars & Payments)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    telegram_payment_charge_id TEXT,
                    invoice_payload TEXT,
                    stars_amount INTEGER,
                    status TEXT,
                    created_at REAL
                )
            """)

            # Banned Users Table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY,
                    reason TEXT,
                    banned_at REAL
                )
            """)

            # Messages / History table (with index for fast retrieval)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    model TEXT,
                    has_images INTEGER DEFAULT 0,
                    created_at REAL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id, id);")

            # Rate limit tracking
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER PRIMARY KEY,
                    last_request_time REAL DEFAULT 0,
                    request_count INTEGER DEFAULT 0
                )
            """)

            await db.commit()

    async def _async_touch_user(self, user_id: int, username: str, first_name: str):
        try:
            now = time.time()
            async with self.connect() as db:
                await db.execute(
                    "UPDATE users SET last_active = ?, username = ?, first_name = ? WHERE user_id = ?",
                    (now, username or "", first_name or "", user_id)
                )
                await db.commit()
        except Exception:
            pass

    async def touch_user_activity(self, user_id: int, username: Optional[str] = "", first_name: Optional[str] = ""):
        """Lightweight touch to ensure user exists and last_active is updated accurately in RAM and DB."""
        now = time.time()
        if user_id in self._user_cache:
            cached_user, exp = self._user_cache[user_id]
            cached_user["last_active"] = now
            if username:
                cached_user["username"] = username
            if first_name:
                cached_user["first_name"] = first_name
            last_flush = cached_user.get("_last_db_flush", 0.0)
            if now - last_flush > 30.0:
                cached_user["_last_db_flush"] = now
                self._user_cache[user_id] = (cached_user, now + 120.0)
                asyncio.create_task(self._async_touch_user(user_id, username or cached_user.get("username", ""), first_name or cached_user.get("first_name", "")))
            return
        await self.get_or_create_user(user_id, username, first_name)

    async def get_or_create_user(self, user_id: int, username: Optional[str] = "", first_name: Optional[str] = "") -> Dict[str, Any]:
        """Fetch user profile or create one if it's their first time, with sub-millisecond RAM caching."""
        now = time.time()

        # 1. Fast path: In-memory cache hit
        if user_id in self._user_cache:
            cached_user, exp = self._user_cache[user_id]
            if now < exp:
                if now - cached_user.get("last_active", 0) > 60.0:
                    cached_user["last_active"] = now
                    import asyncio
                    asyncio.create_task(self._async_touch_user(user_id, username or cached_user.get("username", ""), first_name or cached_user.get("first_name", "")))
                return dict(cached_user)

        # 2. Disk path
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            is_adm = (user_id in ADMIN_IDS or user_id in (MAIN_ADMIN_ID, SECOND_ADMIN_ID))
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    u_dict = dict(row)
                    if is_adm:
                        await db.execute(
                            "UPDATE users SET last_active = ?, username = ?, first_name = ?, is_vip = 1, vip_until = -1, credits = 999999 WHERE user_id = ?",
                            (now, username or row["username"], first_name or row["first_name"], user_id)
                        )
                        u_dict["is_vip"] = 1
                        u_dict["vip_until"] = -1
                    else:
                        await db.execute(
                            "UPDATE users SET last_active = ?, username = ?, first_name = ? WHERE user_id = ?",
                            (now, username or row["username"], first_name or row["first_name"], user_id)
                        )
                    await db.commit()
                    u_dict["last_active"] = now
                    self._user_cache[user_id] = (u_dict, now + 45.0)
                    return u_dict

            # Insert new user
            adm_vip = 1 if is_adm else 0
            adm_until = -1.0 if is_adm else 0.0
            adm_credits = 999999 if is_adm else 50
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, selected_model, web_search_enabled, tts_voice, created_at, last_active, region, last_gift_claim, credits, inviter_id, invited_count, is_vip, vip_until)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, 'de', 0, ?, 0, 0, ?, ?)
            """, (user_id, username or "", first_name or "", DEFAULT_MODEL, DEFAULT_TTS_VOICE, now, now, adm_credits, adm_vip, adm_until))
            await db.commit()

            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                new_row = await cur.fetchone()
                if new_row:
                    new_dict = dict(new_row)
                    self._user_cache[user_id] = (new_dict, now + 45.0)
                    return new_dict

            return {
                "user_id": user_id,
                "username": username or "",
                "first_name": first_name or "",
                "selected_model": DEFAULT_MODEL,
                "web_search_enabled": 0,
                "tts_voice": DEFAULT_TTS_VOICE,
                "custom_api_keys": "{}",
                "created_at": now,
                "last_active": now,
                "total_messages": 0,
                "region": "de",
                "last_gift_claim": 0,
                "credits": 50,
                "inviter_id": 0,
                "invited_count": 0,
                "last_chat_model": "gemini-3.7-flash"
            }

    async def update_user_model(self, user_id: int, model_id: str):
        studio_ids = {"agnes-image-2.5-flash", "agnes-video-2.5", "nano-banana", "nano-banana-2", "nano-banana-pro"}
        is_chat_model = model_id not in studio_ids
        if user_id in self._user_cache:
            self._user_cache[user_id][0]["selected_model"] = model_id
            if is_chat_model:
                self._user_cache[user_id][0]["last_chat_model"] = model_id
        async with self.connect() as db:
            if is_chat_model:
                await db.execute("UPDATE users SET selected_model = ?, last_chat_model = ? WHERE user_id = ?", (model_id, model_id, user_id))
            else:
                await db.execute("UPDATE users SET selected_model = ? WHERE user_id = ?", (model_id, user_id))
            await db.commit()

    async def get_user_chat_model(self, user_id: int) -> str:
        """Returns the user's preferred chat model when exiting studio mode."""
        user = await self.get_or_create_user(user_id)
        m = user.get("last_chat_model")
        studio_ids = {"agnes-image-2.5-flash", "agnes-video-2.5", "nano-banana", "nano-banana-2", "nano-banana-pro"}
        if not m or m in studio_ids:
            return "gemini-3.7-flash"
        return m

    async def set_user_chat_model(self, user_id: int, model_id: str):
        studio_ids = {"agnes-image-2.5-flash", "agnes-video-2.5", "nano-banana", "nano-banana-2", "nano-banana-pro"}
        if model_id in studio_ids:
            return
        if user_id in self._user_cache:
            self._user_cache[user_id][0]["last_chat_model"] = model_id
        async with self.connect() as db:
            await db.execute("UPDATE users SET last_chat_model = ? WHERE user_id = ?", (model_id, user_id))
            await db.commit()

    async def toggle_web_search(self, user_id: int) -> bool:
        """Toggle web search state for user and return the new state."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT web_search_enabled FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                current = row["web_search_enabled"] if row else 0
            new_val = 0 if current else 1
            await db.execute("UPDATE users SET web_search_enabled = ? WHERE user_id = ?", (new_val, user_id))
            await db.commit()
            if user_id in self._user_cache:
                self._user_cache[user_id][0]["web_search_enabled"] = new_val
            return bool(new_val)

    async def update_tts_voice(self, user_id: int, voice: str):
        if user_id in self._user_cache:
            self._user_cache[user_id][0]["tts_voice"] = voice
        async with self.connect() as db:
            await db.execute("UPDATE users SET tts_voice = ? WHERE user_id = ?", (voice, user_id))
            await db.commit()

    async def get_user_image_settings(self, user_id: int) -> tuple[str, str]:
        """Returns (ratio, size) for user image generation."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT image_ratio, image_size FROM users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                if row:
                    r = row["image_ratio"] or "1:1"
                    s = row["image_size"] or "1K"
                    return r, s
        return "1:1", "1K"

    async def update_user_image_settings(self, user_id: int, ratio: Optional[str] = None, size: Optional[str] = None):
        """Updates user image generation settings, ensuring user row exists."""
        await self.get_or_create_user(user_id)
        async with self.connect() as db:
            updates = []
            params = []
            if ratio:
                updates.append("image_ratio = ?")
                params.append(ratio)
            if size:
                updates.append("image_size = ?")
                params.append(size)
            if updates:
                params.append(user_id)
                await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params)
                await db.commit()

    async def get_user_video_settings(self, user_id: int) -> tuple[str, str, str]:
        """Returns (ratio, seconds, size) for user video generation."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT video_ratio, video_seconds, video_size FROM users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                if row:
                    r = row["video_ratio"] or "16:9"
                    sec = row["video_seconds"] or "5"
                    s = row["video_size"] or "720P"
                    return r, sec, s
        return "16:9", "5", "720P"

    async def update_user_video_settings(self, user_id: int, ratio: Optional[str] = None, seconds: Optional[str] = None, size: Optional[str] = None):
        """Updates user video generation settings, ensuring user row exists."""
        await self.get_or_create_user(user_id)
        async with self.connect() as db:
            updates = []
            params = []
            if ratio:
                updates.append("video_ratio = ?")
                params.append(ratio)
            if seconds:
                updates.append("video_seconds = ?")
                params.append(seconds)
            if size:
                updates.append("video_size = ?")
                params.append(size)
            if updates:
                params.append(user_id)
                await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params)
                await db.commit()

    async def add_message(self, user_id: int, role: str, content: str, model: str = "", has_images: bool = False):
        """Append a message to the user's conversation history."""
        now = time.time()
        async with self.connect() as db:
            await db.execute("""
                INSERT INTO messages (user_id, role, content, model, has_images, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, role, content, model, 1 if has_images else 0, now))
            await db.execute("UPDATE users SET total_messages = total_messages + 1, last_active = ? WHERE user_id = ?", (now, user_id))
            await db.commit()

    async def get_chat_history(self, user_id: int, limit: int = MAX_HISTORY_TURNS) -> List[Dict[str, Any]]:
        """Retrieve recent conversation history formatted for LLMGateway."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            # Fetch last N messages in ascending chronological order
            query = """
                SELECT role, content FROM (
                    SELECT id, role, content FROM messages
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
            """
            async with db.execute(query, (user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def clear_chat_history(self, user_id: int):
        """Wipe conversation memory for the user."""
        async with self.connect() as db:
            await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_stats(self) -> Dict[str, Any]:
        """Get overall bot usage statistics."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT COUNT(*) as count FROM users") as cur:
                u_row = await cur.fetchone()
                total_users = u_row["count"] if u_row else 0

            async with db.execute("SELECT COUNT(*) as count FROM messages") as cur:
                m_row = await cur.fetchone()
                total_msgs = m_row["count"] if m_row else 0

            one_day_ago = time.time() - 86400
            async with db.execute("SELECT COUNT(*) as count FROM users WHERE last_active >= ?", (one_day_ago,)) as cur:
                a_row = await cur.fetchone()
                active_today = a_row["count"] if a_row else 0

            return {
                "total_users": total_users,
                "total_messages": total_msgs,
                "active_today": active_today
            }

    async def get_all_user_ids(self) -> List[int]:
        """Get all user IDs for broadcasting."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT user_id FROM users") as cur:
                rows = await cur.fetchall()
                return [r["user_id"] for r in rows]

    async def update_user_region(self, user_id: int, region: str):
        """Update selected server/processing region."""
        async with self.connect() as db:
            await db.execute("UPDATE users SET region = ? WHERE user_id = ?", (region, user_id))
            await db.commit()

    async def claim_daily_gift(self, user_id: int) -> tuple[bool, int, float]:
        """
        Claims daily bonus credits. Allowed once every 24 hours.
        Returns: (success: bool, amount: int, remaining_seconds: float)
        """
        import random
        now = time.time()
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT last_gift_claim, credits FROM users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return False, 0, 0

                last_claim = row["last_gift_claim"] or 0
                elapsed = now - last_claim
                if elapsed < 86400 and last_claim > 0:
                    remaining = 86400 - elapsed
                    return False, 0, remaining

                # Grant 50-100 bonus credits
                bonus = random.randint(50, 100)
                await db.execute(
                    "UPDATE users SET last_gift_claim = ?, credits = COALESCE(credits, 0) + ? WHERE user_id = ?",
                    (now, bonus, user_id)
                )
                await db.commit()
                return True, bonus, 0

    async def add_referral(self, inviter_id: int, new_user_id: int) -> bool:
        """
        Records referral if user was not already referred.
        Grants 50 credits to both inviter and new user.
        """
        if inviter_id == new_user_id:
            return False

        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT inviter_id FROM users WHERE user_id = ?", (new_user_id,)) as cur:
                row = await cur.fetchone()
                if not row or (row["inviter_id"] and row["inviter_id"] != 0):
                    return False

            # Update new user
            await db.execute(
                "UPDATE users SET inviter_id = ?, credits = COALESCE(credits, 0) + 50 WHERE user_id = ?",
                (inviter_id, new_user_id)
            )
            # Update inviter
            await db.execute(
                "UPDATE users SET invited_count = COALESCE(invited_count, 0) + 1, credits = COALESCE(credits, 0) + 50 WHERE user_id = ?",
                (inviter_id,)
            )
            await db.commit()
            return True

    async def get_setting(self, key: str, default: Any = None) -> Any:
        """Fetch a dynamic setting from bot_settings with RAM caching."""
        now = time.time()
        if key in self._settings_cache:
            val, exp = self._settings_cache[key]
            if now < exp:
                return val

        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)) as cur:
                row = await cur.fetchone()
                val = row["value"] if (row and row["value"] is not None) else default
                self._settings_cache[key] = (val, now + 120.0)
                return val

    async def set_setting(self, key: str, value: Any):
        """Set a dynamic setting in bot_settings and update RAM cache."""
        self._settings_cache[key] = (str(value), time.time() + 120.0)
        async with self.connect() as db:
            await db.execute(
                "INSERT INTO bot_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value))
            )
            await db.commit()

    async def is_channel_lock_enabled(self) -> bool:
        val = await self.get_setting("channel_lock_enabled", "0")
        return str(val) == "1"

    async def get_channel_lock_info(self) -> Dict[str, str]:
        return {
            "enabled": str(await self.get_setting("channel_lock_enabled", "0")) == "1",
            "channel_id": await self.get_setting("channel_lock_id", ""),
            "channel_link": await self.get_setting("channel_lock_link", "")
        }

    async def is_user_vip(self, user_id: int) -> bool:
        """Check if user has active VIP subscription or is admin with RAM caching."""
        if user_id in ADMIN_IDS or user_id in (MAIN_ADMIN_ID, SECOND_ADMIN_ID):
            return True

        now = time.time()
        if user_id in self._vip_cache:
            is_v, exp = self._vip_cache[user_id]
            if now < exp:
                return is_v

        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT is_vip, vip_until FROM users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                res = False
                if row:
                    if row["is_vip"] and row["vip_until"] == -1:
                        res = True
                    elif row["is_vip"] and (row["vip_until"] or 0) > now:
                        res = True
                self._vip_cache[user_id] = (res, now + 60.0)
                return res

    async def set_user_vip(self, user_id: int, days: int = 30) -> float:
        """Grant or extend VIP status. days=-1 means lifetime."""
        now = time.time()
        self._vip_cache[user_id] = (True, now + 60.0)
        if user_id in self._user_cache:
            self._user_cache[user_id][0]["is_vip"] = 1
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT vip_until FROM users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                current_until = (row["vip_until"] or 0) if row else 0

            if days == -1:
                new_until = -1.0
            else:
                base_time = max(now, current_until) if current_until > 0 else now
                new_until = base_time + (days * 86400)

            if row:
                await db.execute(
                    "UPDATE users SET is_vip = 1, vip_until = ? WHERE user_id = ?",
                    (new_until, user_id)
                )
            else:
                await db.execute(
                    "INSERT INTO users (user_id, is_vip, vip_until, created_at, last_active, credits) VALUES (?, 1, ?, ?, ?, 50)",
                    (user_id, new_until, now, now)
                )
            await db.commit()
            return new_until

    async def revoke_user_vip(self, user_id: int):
        """Cancel VIP status for a user."""
        self._vip_cache[user_id] = (False, time.time() + 60.0)
        if user_id in self._user_cache:
            self._user_cache[user_id][0]["is_vip"] = 0
        async with self.connect() as db:
            await db.execute("UPDATE users SET is_vip = 0, vip_until = 0 WHERE user_id = ?", (user_id,))
            await db.commit()

    async def is_user_banned(self, user_id: int) -> bool:
        """Check if user is banned with RAM caching."""
        now = time.time()
        if user_id in self._banned_cache:
            is_b, exp = self._banned_cache[user_id]
            if now < exp:
                return is_b

        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,)) as cur:
                res = (await cur.fetchone()) is not None
                self._banned_cache[user_id] = (res, now + 60.0)
                return res

    async def ban_user(self, user_id: int, reason: str = ""):
        """Ban user from using the bot."""
        now = time.time()
        self._banned_cache[user_id] = (True, now + 300.0)
        async with self.connect() as db:
            await db.execute(
                "INSERT OR REPLACE INTO banned_users (user_id, reason, banned_at) VALUES (?, ?, ?)",
                (user_id, reason, now)
            )
            await db.execute(
                "INSERT INTO users (user_id, is_banned, created_at, last_active) VALUES (?, 1, ?, ?) ON CONFLICT(user_id) DO UPDATE SET is_banned = 1",
                (user_id, now, now)
            )
            await db.commit()

    async def unban_user(self, user_id: int):
        """Unban user."""
        self._banned_cache[user_id] = (False, time.time() + 300.0)
        async with self.connect() as db:
            await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
            await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
            await db.commit()

    async def record_star_transaction(self, user_id: int, charge_id: str, payload: str, stars: int):
        """Record Telegram Stars payment transaction and update user stats."""
        now = time.time()
        async with self.connect() as db:
            await db.execute("""
                INSERT INTO transactions (user_id, telegram_payment_charge_id, invoice_payload, stars_amount, status, created_at)
                VALUES (?, ?, ?, ?, 'success', ?)
            """, (user_id, charge_id, payload, stars, now))
            await db.execute("""
                INSERT INTO users (user_id, stars_balance, created_at, last_active) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET stars_balance = COALESCE(stars_balance, 0) + excluded.stars_balance
            """, (user_id, stars, now, now))
            await db.commit()

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch detailed user record."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def add_user_credits(self, user_id: int, amount: int):
        """Adjust credits balance for a user."""
        now = time.time()
        async with self.connect() as db:
            await db.execute("""
                INSERT INTO users (user_id, credits, created_at, last_active) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET credits = COALESCE(credits, 0) + excluded.credits
            """, (user_id, amount, now, now))
            await db.commit()

    async def get_detailed_stats(self) -> Dict[str, Any]:
        """Fetch comprehensive, highly precise analytics for admin panel."""
        now = time.time()
        one_hour_ago = now - 3600
        one_day_ago = now - 86400
        seven_days_ago = now - (7 * 86400)
        thirty_days_ago = now - (30 * 86400)

        async with self.connect() as db:
            db.row_factory = aiosqlite.Row

            # 1. User counts across timeframes
            async with db.execute("SELECT COUNT(*) as c FROM users") as cur:
                total_users = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM users WHERE last_active >= ?", (one_hour_ago,)) as cur:
                active_1h = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM users WHERE last_active >= ?", (one_day_ago,)) as cur:
                active_today = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM users WHERE last_active >= ?", (seven_days_ago,)) as cur:
                active_week = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM users WHERE last_active >= ?", (thirty_days_ago,)) as cur:
                active_month = (await cur.fetchone())["c"]

            # 2. Registration growth
            async with db.execute("SELECT COUNT(*) as c FROM users WHERE created_at >= ?", (one_day_ago,)) as cur:
                new_today = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM users WHERE created_at >= ?", (seven_days_ago,)) as cur:
                new_week = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM users WHERE created_at >= ?", (thirty_days_ago,)) as cur:
                new_month = (await cur.fetchone())["c"]

            # 3. Message counts
            async with db.execute("SELECT COUNT(*) as c FROM messages") as cur:
                total_messages = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM messages WHERE created_at >= ?", (one_day_ago,)) as cur:
                messages_24h = (await cur.fetchone())["c"]

            # 4. VIP statistics
            async with db.execute("SELECT COUNT(*) as c FROM users WHERE is_vip = 1 AND (vip_until = -1 OR vip_until > ?)", (now,)) as cur:
                total_vips = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM users WHERE is_vip = 1 AND vip_until = -1") as cur:
                lifetime_vips = (await cur.fetchone())["c"]

            async with db.execute("SELECT COUNT(*) as c FROM users WHERE is_vip = 1 AND vip_until > ?", (now,)) as cur:
                temporary_vips = (await cur.fetchone())["c"]

            # 5. Financial & Telegram Stars
            async with db.execute("SELECT COALESCE(SUM(stars_amount), 0) as s, COUNT(*) as c FROM transactions WHERE status = 'success'") as cur:
                tx_row = await cur.fetchone()
                total_stars = tx_row["s"]
                total_transactions = tx_row["c"]

            # 6. Banned users
            async with db.execute("SELECT COUNT(*) as c FROM banned_users") as cur:
                total_banned = (await cur.fetchone())["c"]

            # 7. Model distribution
            async with db.execute("""
                SELECT selected_model, COUNT(*) as cnt 
                FROM users 
                WHERE selected_model IS NOT NULL AND selected_model != ''
                GROUP BY selected_model 
                ORDER BY cnt DESC 
                LIMIT 6
            """) as cur:
                top_models = [(r["selected_model"], r["cnt"]) for r in await cur.fetchall()]

            # 8. Top 5 active users
            async with db.execute("""
                SELECT user_id, username, first_name, total_messages, is_vip, vip_until 
                FROM users 
                ORDER BY total_messages DESC 
                LIMIT 5
            """) as cur:
                top_users = [dict(r) for r in await cur.fetchall()]

            # 9. Recent 5 registered users
            async with db.execute("""
                SELECT user_id, username, first_name, created_at, last_active, is_vip 
                FROM users 
                ORDER BY created_at DESC 
                LIMIT 5
            """) as cur:
                recent_users = [dict(r) for r in await cur.fetchall()]

            return {
                "total_users": total_users,
                "active_1h": active_1h,
                "active_today": active_today,
                "active_week": active_week,
                "active_month": active_month,
                "new_today": new_today,
                "new_week": new_week,
                "new_month": new_month,
                "total_messages": total_messages,
                "messages_24h": messages_24h,
                "total_vips": total_vips,
                "lifetime_vips": lifetime_vips,
                "temporary_vips": temporary_vips,
                "total_stars": total_stars,
                "total_transactions": total_transactions,
                "total_banned": total_banned,
                "top_models": top_models,
                "top_users": top_users,
                "recent_users": recent_users
            }

    async def get_all_users_export(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Fetch list of users for administrative audit and export."""
        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT user_id, username, first_name, selected_model, credits, 
                       is_vip, vip_until, stars_balance, total_messages, created_at, last_active
                FROM users 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,)) as cur:
                return [dict(r) for r in await cur.fetchall()]

