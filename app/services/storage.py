import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import SESSIONS_DIR

class SessionStorage:
    @staticmethod
    def _get_path(session_id: str) -> Path:
        # Sanitize session_id to avoid path traversal
        clean_id = "".join([c for c in session_id if c.isalnum() or c in ("-", "_")])
        return SESSIONS_DIR / f"{clean_id}.json"

    @classmethod
    def list_sessions(cls) -> List[Dict[str, Any]]:
        sessions = []
        for file in SESSIONS_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "id": data.get("id", file.stem),
                        "title": data.get("title", "گفتگوی جدید"),
                        "model": data.get("model", "deepseek-reasoner"),
                        "updated_at": data.get("updated_at", file.stat().st_mtime),
                        "message_count": len(data.get("messages", []))
                    })
            except Exception:
                continue

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
        return sessions

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        path = cls._get_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def save_session(
        cls,
        session_id: str,
        messages: List[Dict[str, Any]],
        model: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        path = cls._get_path(session_id)
        current = cls.get_session(session_id) or {}

        # Auto-generate title from first user message if not set
        if not title:
            title = current.get("title")
            if not title and messages:
                for m in messages:
                    if m.get("role") == "user":
                        text_content = ""
                        content = m.get("content")
                        if isinstance(content, str):
                            text_content = content
                        elif isinstance(content, list):
                            for part in content:
                                if part.get("type") == "text":
                                    text_content = part.get("text", "")
                                    break
                        title = text_content[:40] + ("..." if len(text_content) > 40 else "")
                        break
            if not title:
                title = "گفتگوی جدید"

        session_data = {
            "id": session_id,
            "title": title,
            "model": model,
            "messages": messages,
            "created_at": current.get("created_at", time.time()),
            "updated_at": time.time()
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        return session_data

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        path = cls._get_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False
