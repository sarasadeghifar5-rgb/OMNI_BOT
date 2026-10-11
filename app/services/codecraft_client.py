import os
import time
import asyncio
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger("CodeCraftClient")

FALLBACK_CODECRAFT_KEYS = [
    "cc_95SqyRcKCG5gd2hYjOiG5Ax3tSMiH1zvaT0QOGP4MPi0AloB",
]

DEFAULT_BASE_URL = "https://cleanapis.com/v1"



class CodeCraftKeyNode:
    def __init__(self, key: str):
        self.key = key.strip()
        self.cooldown_until: float = 0.0
        self.error_count: int = 0
        self.success_count: int = 0
        self.in_flight: int = 0
        suffix = self.key[-6:] if len(self.key) >= 6 else self.key
        self.label = f"CodeCraftKey[...{suffix}]"

    def is_available(self) -> bool:
        return time.time() >= self.cooldown_until

    def record_error(self, status_code: int = 0):
        self.error_count += 1
        now = time.time()
        if status_code in (429, 403):
            # Rate limit or quota cooldown (20 seconds)
            self.cooldown_until = now + 20.0
        elif status_code in (500, 502, 503, 504):
            # Upstream temporary server glitch (6 seconds)
            self.cooldown_until = now + 6.0
        elif status_code == 401:
            # Bad/expired key (cooldown 10 minutes)
            self.cooldown_until = now + 600.0
        else:
            self.cooldown_until = now + 4.0
        logger.warning(f"[{self.label}] recorded error {status_code}. Cooldown until {self.cooldown_until:.1f}")

    def record_success(self):
        self.success_count += 1
        self.error_count = max(0, self.error_count - 1)
        self.cooldown_until = 0.0


class CodeCraftKeyPool:
    _instance: Optional["CodeCraftKeyPool"] = None

    def __init__(self):
        self.nodes: List[CodeCraftKeyNode] = []
        self._lock = asyncio.Lock()
        self.load_keys()

    @classmethod
    def get_instance(cls) -> "CodeCraftKeyPool":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_keys(self):
        keys_set = []
        raw_keys = (os.getenv("CLEANAPIS_API_KEYS") or os.getenv("CODECRAFT_API_KEYS", "")).strip()
        single_key = (os.getenv("CLEANAPIS_API_KEY") or os.getenv("CODECRAFT_API_KEY", "")).strip()

        if raw_keys:
            for k in raw_keys.replace("\n", ",").split(","):
                clean = k.strip()
                if clean and clean not in keys_set:
                    keys_set.append(clean)

        if single_key and single_key not in keys_set:
            keys_set.append(single_key)

        for fb in FALLBACK_CODECRAFT_KEYS:
            if fb not in keys_set:
                keys_set.append(fb)

        self.nodes = [CodeCraftKeyNode(k) for k in keys_set]
        logger.info(f"CodeCraftKeyPool initialized with {len(self.nodes)} keys.")

    def add_key(self, key: str):
        clean = key.strip()
        if not clean:
            return
        for n in self.nodes:
            if n.key == clean:
                return
        self.nodes.insert(0, CodeCraftKeyNode(clean))
        logger.info(f"Added new key to CodeCraftKeyPool. Total keys: {len(self.nodes)}")

    def get_active_keys(self) -> List[str]:
        """
        Returns keys sorted by Least-Connections Load Balancing:
        Prioritizes available keys with lowest in-flight concurrent requests and lowest error count.
        Ensures multiple concurrent users are distributed evenly across different API keys.
        """
        now = time.time()
        sorted_nodes = sorted(
            self.nodes,
            key=lambda n: (
                (100000.0 if now < n.cooldown_until else 0.0)
                + (n.in_flight * 100)
                + (n.error_count * 10)
            )
        )
        return [n.key for n in sorted_nodes]

    def acquire_key(self, key: str):
        for n in self.nodes:
            if n.key == key:
                n.in_flight += 1
                break

    def release_key(self, key: str):
        for n in self.nodes:
            if n.key == key:
                n.in_flight = max(0, n.in_flight - 1)
                break

    def record_key_error(self, key: str, status_code: int = 0):
        for n in self.nodes:
            if n.key == key:
                n.record_error(status_code)
                break

    def record_key_success(self, key: str):
        for n in self.nodes:
            if n.key == key:
                n.record_success()
                break

    def get_headers(self, key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OmniLLM/2.0"
        }

    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        healthy = sum(1 for n in self.nodes if n.is_available())
        cooldown = len(self.nodes) - healthy
        total_errors = sum(n.error_count for n in self.nodes)
        total_successes = sum(n.success_count for n in self.nodes)
        return {
            "total": len(self.nodes),
            "healthy": healthy,
            "cooldown": cooldown,
            "total_errors": total_errors,
            "total_successes": total_successes,
            "keys": [
                {
                    "label": n.label,
                    "available": n.is_available(),
                    "cooldown_remaining": max(0, int(n.cooldown_until - now)),
                    "errors": n.error_count,
                    "successes": n.success_count
                }
                for n in self.nodes
            ]
        }
