"""
Key Pool Manager for handling API Key rotation, failover, cooldowns, and health monitoring.
"""
import time
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class KeyPool:
    def __init__(self, name: str, keys: List[str], cooldown_seconds: int = 60):
        self.name = name
        self.keys = list(keys)
        self.cooldown_seconds = cooldown_seconds
        self.current_index = 0
        
        # Stats per key
        self.key_stats: Dict[str, Dict[str, any]] = {
            key: {
                "success_count": 0,
                "error_count": 0,
                "last_error_time": 0,
                "last_error_status": None,
                "is_disabled": False,
            }
            for key in self.keys
        }

    def get_key(self) -> str:
        """Returns the next healthy key in round-robin fashion."""
        if not self.keys:
            raise ValueError(f"No keys configured for pool '{self.name}'")

        now = time.time()
        num_keys = len(self.keys)

        # Try to find a key that is not in cooldown
        for _ in range(num_keys):
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % num_keys
            stats = self.key_stats[key]

            # Check if key is in cooldown
            if stats["last_error_time"] > 0 and (now - stats["last_error_time"]) < self.cooldown_seconds:
                continue

            return key

        # If all keys are in cooldown, pick the one with oldest error
        oldest_key = min(self.keys, key=lambda k: self.key_stats[k]["last_error_time"])
        return oldest_key

    def report_success(self, key: str):
        """Record successful call using this key."""
        if key in self.key_stats:
            self.key_stats[key]["success_count"] += 1
            self.key_stats[key]["last_error_time"] = 0

    def report_failure(self, key: str, status_code: Optional[int] = None, is_permanent: bool = False):
        """Record failure and put key into cooldown."""
        if key in self.key_stats:
            stats = self.key_stats[key]
            stats["error_count"] += 1
            stats["last_error_time"] = time.time()
            stats["last_error_status"] = status_code
            if is_permanent:
                stats["is_disabled"] = True
            logger.warning(
                f"Key pool '{self.name}' key {key[:8]}... failed with status {status_code}. "
                f"Cooldown for {self.cooldown_seconds}s."
            )

    def get_status_report(self) -> Dict[str, any]:
        """Generate human-readable status for admin."""
        total = len(self.keys)
        now = time.time()
        in_cooldown = sum(
            1 for k in self.keys 
            if (now - self.key_stats[k]["last_error_time"]) < self.cooldown_seconds and self.key_stats[k]["last_error_time"] > 0
        )
        total_success = sum(self.key_stats[k]["success_count"] for k in self.keys)
        total_errors = sum(self.key_stats[k]["error_count"] for k in self.keys)

        return {
            "name": self.name,
            "total_keys": total,
            "active_keys": total - in_cooldown,
            "in_cooldown": in_cooldown,
            "total_success": total_success,
            "total_errors": total_errors,
        }
