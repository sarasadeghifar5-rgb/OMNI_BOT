"""
Async SQLite Database layer using aiosqlite for persistence.
"""
import os
import time
import aiosqlite
from typing import List, Dict, Optional, Any
from config import DB_PATH, DEFAULT_MODEL

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init(self):
        """Initialize database tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    selected_model TEXT DEFAULT 'gpt-5.6-sol',
                    created_at REAL,
                    last_active REAL,
                    is_blocked INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    model TEXT,
                    created_at REAL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS generation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    gen_type TEXT,
                    prompt TEXT,
                    result_url TEXT,
                    created_at REAL
                )
            """)
            await db.commit()

    async def get_or_create_user(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> Dict[str, Any]:
        """Fetch user or create if new."""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()

            if row is None:
                await db.execute("""
                    INSERT INTO users (user_id, username, first_name, selected_model, created_at, last_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, username, first_name, DEFAULT_MODEL, now, now))
                await db.commit()
                return {
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "selected_model": DEFAULT_MODEL,
                    "created_at": now,
                    "last_active": now,
                    "is_blocked": 0,
                    "message_count": 0
                }
            else:
                # Update last active & name info
                await db.execute("""
                    UPDATE users SET last_active = ?, username = ?, first_name = ?
                    WHERE user_id = ?
                """, (now, username, first_name, user_id))
                await db.commit()
                return dict(row)

    async def set_user_model(self, user_id: int, model_name: str):
        """Update active AI model for user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET selected_model = ? WHERE user_id = ?", (model_name, user_id))
            await db.commit()

    async def get_user_model(self, user_id: int) -> str:
        """Get selected AI model for user."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT selected_model FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
            return DEFAULT_MODEL

    async def add_message(self, user_id: int, role: str, content: str, model: str):
        """Record chat message for conversational context."""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO messages (user_id, role, content, model, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, role, content, model, now))
            await db.execute("UPDATE users SET message_count = message_count + 1 WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_history(self, user_id: int, limit: int = 10) -> List[Dict[str, str]]:
        """Fetch recent message history for multi-turn conversations."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT role, content FROM messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (user_id, limit))
            rows = await cursor.fetchall()
            history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
            return history

    async def clear_history(self, user_id: int):
        """Clear conversation history for a user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            await db.commit()

    async def log_generation(self, user_id: int, gen_type: str, prompt: str, result_url: Optional[str] = None):
        """Log multimedia generation (image/video)."""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO generation_logs (user_id, gen_type, prompt, result_url, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, gen_type, prompt, result_url or "", now))
            await db.commit()

    async def get_stats(self) -> Dict[str, Any]:
        """Aggregate stats for Admin dashboard."""
        now = time.time()
        one_day_ago = now - 86400
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (one_day_ago,))
            active_today = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'")
            total_prompts = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM generation_logs WHERE gen_type = 'image'")
            total_images = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM generation_logs WHERE gen_type = 'video'")
            total_videos = (await cursor.fetchone())[0]

            return {
                "total_users": total_users,
                "active_today": active_today,
                "total_prompts": total_prompts,
                "total_images": total_images,
                "total_videos": total_videos,
            }

    async def get_all_user_ids(self) -> List[int]:
        """Return list of all registered user IDs."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE is_blocked = 0")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

# Global instance
db = Database()
