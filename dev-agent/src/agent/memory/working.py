"""Working memory implementation for short-term context storage.

Working memory stores conversation history, task context, and intermediate results
during agent execution. Supports both in-memory and Redis backends.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from agent.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Single memory entry."""

    key: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl: int | None = None  # Time-to-live in seconds
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if entry has expired.

        Returns:
            True if expired,False otherwise
        """
        if self.ttl is None:
            return False

        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > self.ttl


class WorkingMemory:
    """Working memory for short-term context storage.

    Stores conversation history, task context, and intermediate results.
    Supports TTL-based expiration and automatic cleanup.
    """

    def __init__(self, default_ttl: int | None = None) -> None:
        """Initialize working memory.

        Args:
            default_ttl: Default TTL in seconds (defaults to settings)
        """
        settings = get_settings()
        self.default_ttl = default_ttl or settings.memory_ttl
        self.backend = settings.memory_backend

        # In-memory storage
        self._store: dict[str, MemoryEntry] = {}

        # TODO: Redis backend support
        self._redis_client = None

        logger.info(f"Initialized working memory with backend={self.backend}")

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store value in memory.

        Args:
            key: Memory key
            value: Value to store
            ttl: Time-to-live in seconds (defaults to instance TTL)
            metadata: Optional metadata
        """
        entry = MemoryEntry(
            key=key,
            value=value,
            ttl=ttl or self.default_ttl,
            metadata=metadata or {},
        )

        if self.backend == "redis" and self._redis_client:
            # TODO: Redis implementation
            pass
        else:
            # In-memory storage
            self._store[key] = entry

        logger.debug(f"Stored memory: {key} (ttl={entry.ttl}s)")

    async def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from memory.

        Args:
            key: Memory key
            default: Default value if not found

        Returns:
            Stored value or default
        """
        if self.backend == "redis" and self._redis_client:
            # TODO: Redis implementation
            return default
        else:
            # In-memory retrieval
            entry = self._store.get(key)

            if entry is None:
                return default

            # Check expiration
            if entry.is_expired():
                logger.debug(f"Memory expired: {key}")
                del self._store[key]
                return default

            return entry.value

    async def delete(self, key: str) -> bool:
        """Delete value from memory.

        Args:
            key: Memory key

        Returns:
            True if deleted, False if not found
        """
        if self.backend == "redis" and self._redis_client:
            # TODO: Redis implementation
            return False
        else:
            if key in self._store:
                del self._store[key]
                logger.debug(f"Deleted memory: {key}")
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in memory.

        Args:
            key: Memory key

        Returns:
            True if exists and not expired, False otherwise
        """
        value = await self.get(key)
        return value is not None

    async def keys(self, pattern: str = "*") -> list[str]:
        """List keys matching pattern.

        Args:
            pattern: Key pattern (supports * wildcard)

        Returns:
            List of matching keys
        """
        if self.backend == "redis" and self._redis_client:
            # TODO: Redis implementation
            return []
        else:
            # Simple pattern matching for in-memory
            all_keys = list(self._store.keys())

            if pattern == "*":
                return all_keys

            # Simple prefix matching
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return [k for k in all_keys if k.startswith(prefix)]

            return [k for k in all_keys if k == pattern]

    async def clear(self) -> None:
        """Clear all memory."""
        if self.backend == "redis" and self._redis_client:
            # TODO: Redis implementation
            pass
        else:
            self._store.clear()

        logger.info("Cleared all memory")

    async def cleanup_expired(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed
        """
        if self.backend == "redis":
            # Redis handles TTL automatically
            return 0
        else:
            expired_keys = [
                key for key, entry in self._store.items() if entry.is_expired()
            ]

            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

            return len(expired_keys)

    async def get_stats(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dictionary with memory stats
        """
        # Cleanup expired first
        await self.cleanup_expired()

        if self.backend == "redis" and self._redis_client:
            # TODO: Redis stats
            return {"backend": "redis", "keys": 0}
        else:
            total_size = sum(
                len(json.dumps(entry.value)) for entry in self._store.values()
            )

            return {
                "backend": "in-memory",
                "keys": len(self._store),
                "size_bytes": total_size,
                "ttl_default": self.default_ttl,
            }

    async def close(self) -> None:
        """Close memory and release resources."""
        if self._redis_client:
            await self._redis_client.close()

    async def __aenter__(self) -> "WorkingMemory":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Global working memory instance
_global_memory: WorkingMemory | None = None


def get_working_memory() -> WorkingMemory:
    """Get global working memory instance.

    Returns:
        Singleton WorkingMemory instance
    """
    global _global_memory
    if _global_memory is None:
        _global_memory = WorkingMemory()
    return _global_memory
