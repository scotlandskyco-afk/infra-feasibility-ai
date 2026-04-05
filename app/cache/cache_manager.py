"""
Caching layer — local JSON file cache with TTL.
Optionally swap for Redis by setting REDIS_URL in .env
"""
import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

CACHE_DIR = Path(os.getenv("CACHE_DIR", "cache"))
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path(key: str) -> Path:
    safe_key = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"{safe_key}.json"


def get_cached(key: str, ttl_hours: int = None) -> dict | None:
    """Return cached value if it exists and is not expired."""
    ttl = ttl_hours or CACHE_TTL_HOURS
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            envelope = json.load(f)
        cached_at = datetime.fromisoformat(envelope["cached_at"])
        if datetime.now() - cached_at > timedelta(hours=ttl):
            path.unlink(missing_ok=True)
            return None
        return envelope["data"]
    except Exception:
        return None


def set_cached(key: str, data: dict, ttl_hours: int = None) -> None:
    """Persist data to cache with timestamp."""
    path = _cache_path(key)
    envelope = {"cached_at": datetime.now().isoformat(), "data": data}
    with open(path, "w") as f:
        json.dump(envelope, f, default=str)


def clear_cache() -> int:
    """Remove all cache files. Returns count removed."""
    removed = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        removed += 1
    return removed
