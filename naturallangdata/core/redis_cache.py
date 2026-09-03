"""Redis client wrapper with automatic in-memory fallback for schema caching."""
import fnmatch
import json
import logging
from typing import Any, Dict, List, Optional
import redis

from naturallangdata.core.config import Settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Cache client supporting Redis and seamless in-memory fallback."""

    def __init__(self, settings: Settings) -> None:
        self._url = settings.redis_url
        self._in_memory_store: Dict[str, str] = {}
        self._is_in_memory = False
        self._client: Optional[redis.Redis] = None
        self._connect()

    def _connect(self) -> None:
        try:
            client = redis.from_url(self._url, decode_responses=True, socket_timeout=1.5)
            client.ping()
            self._client = client
            self._is_in_memory = False
        except Exception:
            self._client = None
            self._is_in_memory = True

    @property
    def is_fallback(self) -> bool:
        """Indicate whether the cache is running in fallback in-memory mode."""
        return self._is_in_memory

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Store serialized JSON or string value by key."""
        str_val = value if isinstance(value, str) else json.dumps(value)
        if not self._is_in_memory and self._client:
            try:
                self._client.set(name=key, value=str_val, ex=ex)
                return True
            except Exception:
                self._is_in_memory = True
        self._in_memory_store[key] = str_val
        return True

    def get(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize value by key."""
        raw: Optional[str] = None
        if not self._is_in_memory and self._client:
            try:
                raw = self._client.get(name=key)
            except Exception:
                self._is_in_memory = True
        if raw is None:
            raw = self._in_memory_store.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def keys(self, pattern: str = "*") -> List[str]:
        """List keys matching a wildcard pattern."""
        if not self._is_in_memory and self._client:
            try:
                return list(self._client.keys(pattern=pattern))
            except Exception:
                self._is_in_memory = True
        return [k for k in self._in_memory_store.keys() if fnmatch.fnmatch(k, pattern)]

    def delete(self, key: str) -> bool:
        """Remove a key from the cache."""
        if not self._is_in_memory and self._client:
            try:
                self._client.delete(key)
            except Exception:
                self._is_in_memory = True
        self._in_memory_store.pop(key, None)
        return True

    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all stored table schema definitions across engines."""
        schema_keys = self.keys("schema:*")
        results: Dict[str, Dict[str, Any]] = {}
        for key in schema_keys:
            data = self.get(key)
            if data and isinstance(data, dict):
                parts = key.split(":")
                table_name = parts[-1]
                results[table_name] = data
        return results
