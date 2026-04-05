"""
JSON-based caching layer with TTL support.
Stores responses in .cache/ directory to minimise redundant API calls.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))


class JSONCache:
    """Simple file-based JSON cache with time-to-live expiry."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if it exists and has not expired."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                envelope = json.load(f)
            if time.time() > envelope["expires_at"]:
                path.unlink(missing_ok=True)
                return None
            return envelope["data"]
        except (json.JSONDecodeError, KeyError):
            return None

    def set(self, key: str, data: Any, ttl_hours: float = 24.0) -> None:
        """Store data under key with a TTL in hours."""
        envelope = {
            "expires_at": time.time() + ttl_hours * 3600,
            "data": data,
        }
        with open(self._path(key), "w") as f:
            json.dump(envelope, f)

    def clear(self, key: Optional[str] = None) -> None:
        """Clear a specific key or the entire cache."""
        if key:
            self._path(key).unlink(missing_ok=True)
        else:
            for p in self.cache_dir.glob("*.json"):
                p.unlink(missing_ok=True)
