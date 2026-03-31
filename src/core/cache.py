import json
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".libfix" / "cache"
CACHE_EXPIRY_DAYS = 7


class PackageCache:
    def __init__(self, cache_dir: Path = CACHE_DIR, expiry_days: int = CACHE_EXPIRY_DAYS):
        self.cache_dir = cache_dir
        self.expiry_days = expiry_days
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, package_name: str) -> Path:
        safe_name = package_name.lower().replace("-", "_").replace(".", "_")
        return self.cache_dir / f"{safe_name}.json"

    def get(self, package_name: str) -> Optional[dict]:
        cache_path = self._get_cache_path(package_name)
        if not cache_path.exists():
            return None

        try:
            age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            if age > timedelta(days=self.expiry_days):
                logger.debug(f"Cache expired for {package_name}")
                return None

            with open(cache_path, "r") as f:
                data = json.load(f)
            logger.debug(f"Cache hit for {package_name}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Error reading cache for {package_name}: {e}")
            return None

    def set(self, package_name: str, data: dict) -> None:
        cache_path = self._get_cache_path(package_name)
        try:
            with open(cache_path, "w") as f:
                json.dump(data, f)
            logger.debug(f"Cached data for {package_name}")
        except OSError as e:
            logger.warning(f"Error writing cache for {package_name}: {e}")

    def clear(self) -> None:
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        logger.info("Cache cleared")

    def clear_expired(self) -> int:
        count = 0
        cutoff = datetime.now() - timedelta(days=self.expiry_days)
        for cache_file in self.cache_dir.glob("*.json"):
            if datetime.fromtimestamp(cache_file.stat().st_mtime) < cutoff:
                cache_file.unlink()
                count += 1
        logger.info(f"Cleared {count} expired cache entries")
        return count


_cache: Optional[PackageCache] = None


def get_cache() -> PackageCache:
    global _cache
    if _cache is None:
        _cache = PackageCache()
    return _cache
