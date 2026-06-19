"""Rate limiting and quota management - Phase 5."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(
        self,
        rate: int,
        per: int,
        burst: int | None = None,
    ):
        """Initialize rate limiter.

        Args:
            rate: Number of requests allowed
            per: Time window in seconds
            burst: Optional burst capacity (defaults to rate)

        """
        self.rate = rate
        self.per = per
        self.burst = burst or rate

        # Token buckets: key -> (tokens, last_update)
        self.buckets: dict[str, tuple[float, datetime]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, tokens: int = 1) -> bool:
        """Acquire tokens from rate limiter.

        Args:
            key: Rate limiter key (e.g., user_id, api_key)
            tokens: Number of tokens to acquire

        Returns:
            True if acquired, False if rate limited

        """
        async with self._lock:
            now = datetime.now(timezone.utc)

            # Get or create bucket
            if key not in self.buckets:
                self.buckets[key] = (float(self.burst), now)

            current_tokens, last_update = self.buckets[key]

            # Refill tokens based on time passed
            time_passed = (now - last_update).total_seconds()
            refill_amount = (time_passed / self.per) * self.rate
            current_tokens = min(self.burst, current_tokens + refill_amount)

            # Try to consume tokens
            if current_tokens >= tokens:
                self.buckets[key] = (current_tokens - tokens, now)
                return True
            else:
                self.buckets[key] = (current_tokens, now)
                return False

    async def get_remaining(self, key: str) -> int:
        """Get remaining tokens for a key.

        Args:
            key: Rate limiter key

        Returns:
            Remaining tokens

        """
        async with self._lock:
            if key not in self.buckets:
                return self.burst

            current_tokens, last_update = self.buckets[key]

            # Calculate refilled tokens
            now = datetime.now(timezone.utc)
            time_passed = (now - last_update).total_seconds()
            refill_amount = (time_passed / self.per) * self.rate
            current_tokens = min(self.burst, current_tokens + refill_amount)

            return int(current_tokens)

    async def get_reset_time(self, key: str) -> datetime:
        """Get when the rate limit resets for a key.

        Args:
            key: Rate limiter key

        Returns:
            Reset timestamp

        """
        if key not in self.buckets:
            return datetime.now(timezone.utc)

        _, last_update = self.buckets[key]
        return last_update + timedelta(seconds=self.per)

    async def cleanup(self, max_age_seconds: int = 3600) -> int:
        """Clean up old buckets.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            Number of buckets cleaned up

        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            to_delete = []

            for key, (_, last_update) in self.buckets.items():
                age = (now - last_update).total_seconds()
                if age > max_age_seconds:
                    to_delete.append(key)

            for key in to_delete:
                del self.buckets[key]

            return len(to_delete)


class QuotaManager:
    """Manages usage quotas."""

    def __init__(self):
        """Initialize quota manager."""
        # Quotas: key -> {period: (limit, used, reset_time)}
        self.quotas: dict[str, dict[str, tuple[int, int, datetime]]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def set_quota(
        self,
        key: str,
        period: str,
        limit: int,
    ) -> None:
        """Set a quota for a key.

        Args:
            key: Quota key (e.g., user_id, api_key)
            period: Period (daily, weekly, monthly)
            limit: Quota limit

        """
        async with self._lock:
            reset_time = self._calculate_reset_time(period)
            self.quotas[key][period] = (limit, 0, reset_time)

    async def consume(self, key: str, period: str, amount: int = 1) -> bool:
        """Consume quota.

        Args:
            key: Quota key
            period: Period
            amount: Amount to consume

        Returns:
            True if consumed, False if quota exceeded

        """
        async with self._lock:
            if key not in self.quotas or period not in self.quotas[key]:
                # No quota set, allow
                return True

            limit, used, reset_time = self.quotas[key][period]

            # Check if quota has reset
            now = datetime.now(timezone.utc)
            if now >= reset_time:
                # Reset quota
                reset_time = self._calculate_reset_time(period)
                used = 0

            # Try to consume
            if used + amount <= limit:
                self.quotas[key][period] = (limit, used + amount, reset_time)
                return True
            else:
                return False

    async def get_quota_status(
        self, key: str, period: str
    ) -> dict[str, Any] | None:
        """Get quota status for a key.

        Args:
            key: Quota key
            period: Period

        Returns:
            Quota status or None if not set

        """
        async with self._lock:
            if key not in self.quotas or period not in self.quotas[key]:
                return None

            limit, used, reset_time = self.quotas[key][period]

            # Check if quota has reset
            now = datetime.now(timezone.utc)
            if now >= reset_time:
                reset_time = self._calculate_reset_time(period)
                used = 0
                self.quotas[key][period] = (limit, used, reset_time)

            return {
                "total": limit,
                "used": used,
                "remaining": limit - used,
                "period": period,
                "reset": reset_time,
            }

    def _calculate_reset_time(self, period: str) -> datetime:
        """Calculate quota reset time.

        Args:
            period: Period (daily, weekly, monthly)

        Returns:
            Reset timestamp

        """
        now = datetime.now(timezone.utc)

        if period == "daily":
            # Reset at midnight UTC
            reset = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if reset <= now:
                reset += timedelta(days=1)
        elif period == "weekly":
            # Reset on Monday midnight UTC
            days_to_monday = (7 - now.weekday()) % 7
            if days_to_monday == 0 and now.hour > 0:
                days_to_monday = 7
            reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                days=days_to_monday
            )
        elif period == "monthly":
            # Reset on first of next month
            if now.month == 12:
                reset = now.replace(
                    year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                )
            else:
                reset = now.replace(
                    month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
                )
        else:
            # Default to 24 hours
            reset = now + timedelta(days=1)

        return reset


# FastAPI middleware


class RateLimitMiddleware:
    """Rate limit middleware for FastAPI."""

    def __init__(
        self,
        rate_limiter: RateLimiter,
        get_key_func: callable,
    ):
        """Initialize middleware.

        Args:
            rate_limiter: Rate limiter instance
            get_key_func: Function to extract key from request

        """
        self.rate_limiter = rate_limiter
        self.get_key_func = get_key_func

    async def __call__(self, request: Request, call_next):
        """Process request with rate limiting.

        Args:
            request: HTTP request
            call_next: Next middleware

        Returns:
            HTTP response

        Raises:
            HTTPException: If rate limited

        """
        # Extract key
        key = await self.get_key_func(request)

        # Check rate limit
        allowed = await self.rate_limiter.acquire(key)

        if not allowed:
            reset_time = await self.rate_limiter.get_reset_time(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": str(int((reset_time - datetime.now(timezone.utc)).total_seconds())),
                    "X-RateLimit-Limit": str(self.rate_limiter.rate),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": reset_time.isoformat(),
                },
            )

        # Add rate limit headers
        remaining = await self.rate_limiter.get_remaining(key)
        reset_time = await self.rate_limiter.get_reset_time(key)

        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.rate)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = reset_time.isoformat()

        return response


# Helper functions


async def get_client_ip(request: Request) -> str:
    """Extract client IP from request.

    Args:
        request: HTTP request

    Returns:
        Client IP

    """
    # Check X-Forwarded-For header
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Fall back to client host
    return request.client.host if request.client else "unknown"


async def get_api_key_from_request(request: Request) -> str:
    """Extract API key from request.

    Args:
        request: HTTP request

    Returns:
        API key or IP if not found

    """
    # Check header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"key:{api_key}"

    # Fall back to IP
    return f"ip:{await get_client_ip(request)}"
