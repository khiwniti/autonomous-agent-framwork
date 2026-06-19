"""Resource limits and quotas enforcement - Phase 6."""

import asyncio
import psutil
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

from agent.observability.logging import get_logger
from agent.observability.metrics import get_metrics


logger = get_logger(__name__)


class ResourceType(str, Enum):
    """Resource types."""

    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    TASKS = "tasks"
    REQUESTS = "requests"


class ResourceUsage(BaseModel):
    """Current resource usage."""

    cpu_percent: float = Field(description="CPU usage (%)")
    memory_mb: float = Field(description="Memory usage (MB)")
    memory_percent: float = Field(description="Memory usage (%)")
    disk_usage_gb: float = Field(description="Disk usage (GB)")
    disk_percent: float = Field(description="Disk usage (%)")
    active_tasks: int = Field(description="Active tasks")
    timestamp: datetime = Field(description="Measurement timestamp")


class ResourceQuota(BaseModel):
    """Resource quota for user/session."""

    user_id: str = Field(description="User ID")
    resource_type: ResourceType = Field(description="Resource type")
    limit: float = Field(description="Resource limit")
    used: float = Field(default=0.0, description="Resource used")
    reset_period: str = Field(
        default="daily", description="Reset period (daily/weekly/monthly)"
    )
    reset_at: datetime = Field(description="Next reset time")


class ResourceMonitor:
    """Monitors and enforces resource limits."""

    def __init__(
        self,
        cpu_limit_percent: float = 80.0,
        memory_limit_mb: float = 2048.0,
        disk_limit_gb: float = 10.0,
        max_concurrent_tasks: int = 100,
        monitoring_interval: int = 5,
    ):
        """Initialize resource monitor.

        Args:
            cpu_limit_percent: CPU usage limit (%)
            memory_limit_mb: Memory limit (MB)
            disk_limit_gb: Disk usage limit (GB)
            max_concurrent_tasks: Maximum concurrent tasks
            monitoring_interval: Monitoring interval (seconds)

        """
        self.cpu_limit = cpu_limit_percent
        self.memory_limit = memory_limit_mb
        self.disk_limit = disk_limit_gb
        self.max_tasks = max_concurrent_tasks
        self.monitoring_interval = monitoring_interval

        self.active_tasks = 0
        self.monitoring = False
        self.monitor_task = None

        self.metrics = get_metrics()

        # Resource quotas
        self.quotas: dict[str, dict[ResourceType, ResourceQuota]] = {}

    def get_current_usage(self) -> ResourceUsage:
        """Get current resource usage.

        Returns:
            Current resource usage

        """
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory usage
        memory = psutil.virtual_memory()
        memory_mb = memory.used / (1024 * 1024)
        memory_percent = memory.percent

        # Disk usage
        disk = psutil.disk_usage("/")
        disk_gb = disk.used / (1024 * 1024 * 1024)
        disk_percent = disk.percent

        return ResourceUsage(
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            disk_usage_gb=disk_gb,
            disk_percent=disk_percent,
            active_tasks=self.active_tasks,
            timestamp=datetime.now(timezone.utc),
        )

    def check_limits(self, usage: ResourceUsage | None = None) -> dict[str, bool]:
        """Check if resource limits are exceeded.

        Args:
            usage: Optional pre-fetched usage (fetches if None)

        Returns:
            Dictionary of resource name to exceeded status

        """
        if usage is None:
            usage = self.get_current_usage()

        return {
            "cpu": usage.cpu_percent > self.cpu_limit,
            "memory": usage.memory_mb > self.memory_limit,
            "disk": usage.disk_usage_gb > self.disk_limit,
            "tasks": usage.active_tasks >= self.max_tasks,
        }

    def can_accept_task(self) -> tuple[bool, str | None]:
        """Check if system can accept new task.

        Returns:
            Tuple of (can_accept, reason_if_not)

        """
        usage = self.get_current_usage()
        limits = self.check_limits(usage)

        if limits["tasks"]:
            return False, f"Maximum concurrent tasks ({self.max_tasks}) reached"

        if limits["cpu"]:
            return (
                False,
                f"CPU usage ({usage.cpu_percent:.1f}%) exceeds limit ({self.cpu_limit}%)",
            )

        if limits["memory"]:
            return (
                False,
                f"Memory usage ({usage.memory_mb:.0f}MB) exceeds limit ({self.memory_limit}MB)",
            )

        return True, None

    async def acquire_task_slot(self, timeout: float = 30.0) -> bool:
        """Acquire a task execution slot.

        Args:
            timeout: Maximum wait time (seconds)

        Returns:
            True if acquired, False if timeout

        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            can_accept, reason = self.can_accept_task()

            if can_accept:
                self.active_tasks += 1
                logger.info(
                    f"Task slot acquired ({self.active_tasks}/{self.max_tasks})"
                )
                return True

            logger.warning(f"Waiting for resources: {reason}")
            await asyncio.sleep(1)

        logger.error(f"Task slot acquisition timeout after {timeout}s")
        return False

    def release_task_slot(self) -> None:
        """Release a task execution slot."""
        if self.active_tasks > 0:
            self.active_tasks -= 1
            logger.info(f"Task slot released ({self.active_tasks}/{self.max_tasks})")

    def set_quota(
        self,
        user_id: str,
        resource_type: ResourceType,
        limit: float,
        reset_period: str = "daily",
    ) -> ResourceQuota:
        """Set user resource quota.

        Args:
            user_id: User ID
            resource_type: Resource type
            limit: Resource limit
            reset_period: Reset period

        Returns:
            Created quota

        """
        if user_id not in self.quotas:
            self.quotas[user_id] = {}

        reset_at = self._calculate_reset_time(reset_period)

        quota = ResourceQuota(
            user_id=user_id,
            resource_type=resource_type,
            limit=limit,
            used=0.0,
            reset_period=reset_period,
            reset_at=reset_at,
        )

        self.quotas[user_id][resource_type] = quota
        return quota

    def consume_quota(
        self,
        user_id: str,
        resource_type: ResourceType,
        amount: float = 1.0,
    ) -> tuple[bool, str | None]:
        """Consume user quota.

        Args:
            user_id: User ID
            resource_type: Resource type
            amount: Amount to consume

        Returns:
            Tuple of (success, error_message)

        """
        if user_id not in self.quotas:
            return True, None

        if resource_type not in self.quotas[user_id]:
            return True, None

        quota = self.quotas[user_id][resource_type]

        # Check reset
        if datetime.now(timezone.utc) >= quota.reset_at:
            quota.used = 0.0
            quota.reset_at = self._calculate_reset_time(quota.reset_period)

        # Check limit
        if quota.used + amount > quota.limit:
            return (
                False,
                f"{resource_type.value} quota exceeded ({quota.used}/{quota.limit})",
            )

        quota.used += amount
        return True, None

    def get_quota_status(
        self, user_id: str, resource_type: ResourceType
    ) -> dict[str, Any] | None:
        """Get quota status for user.

        Args:
            user_id: User ID
            resource_type: Resource type

        Returns:
            Quota status or None

        """
        if user_id not in self.quotas:
            return None

        if resource_type not in self.quotas[user_id]:
            return None

        quota = self.quotas[user_id][resource_type]

        return {
            "resource_type": resource_type.value,
            "limit": quota.limit,
            "used": quota.used,
            "remaining": quota.limit - quota.used,
            "reset_at": quota.reset_at.isoformat(),
        }

    def _calculate_reset_time(self, period: str) -> datetime:
        """Calculate quota reset time.

        Args:
            period: Reset period

        Returns:
            Reset datetime

        """
        now = datetime.now(timezone.utc)

        if period == "hourly":
            return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        elif period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                days=1
            )
        elif period == "weekly":
            days_until_monday = (7 - now.weekday()) % 7
            return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                days=days_until_monday if days_until_monday > 0 else 7
            )
        elif period == "monthly":
            if now.month == 12:
                return now.replace(
                    year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0
                )
            else:
                return now.replace(
                    month=now.month + 1, day=1, hour=0, minute=0, second=0
                )

        return now + timedelta(days=1)

    async def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Resource monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self.monitoring = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Resource monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Resource monitoring loop."""
        while self.monitoring:
            try:
                usage = self.get_current_usage()
                limits = self.check_limits(usage)

                # Log warnings if limits exceeded
                if limits["cpu"]:
                    logger.warning(
                        f"CPU usage high: {usage.cpu_percent:.1f}% (limit: {self.cpu_limit}%)"
                    )

                if limits["memory"]:
                    logger.warning(
                        f"Memory usage high: {usage.memory_mb:.0f}MB (limit: {self.memory_limit}MB)"
                    )

                if limits["disk"]:
                    logger.warning(
                        f"Disk usage high: {usage.disk_usage_gb:.1f}GB (limit: {self.disk_limit}GB)"
                    )

                if limits["tasks"]:
                    logger.warning(
                        f"Task limit reached: {usage.active_tasks}/{self.max_tasks}"
                    )

                # Update metrics
                self.metrics.memory_entries_total.labels(memory_type="system").set(
                    usage.memory_mb
                )

                await asyncio.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"Resource monitoring error: {str(e)}")
                await asyncio.sleep(self.monitoring_interval)


# Global resource monitor
_resource_monitor: ResourceMonitor | None = None


def get_resource_monitor() -> ResourceMonitor:
    """Get global resource monitor.

    Returns:
        Global resource monitor

    """
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


def initialize_resource_monitor(
    cpu_limit_percent: float = 80.0,
    memory_limit_mb: float = 2048.0,
    disk_limit_gb: float = 10.0,
    max_concurrent_tasks: int = 100,
) -> ResourceMonitor:
    """Initialize global resource monitor.

    Args:
        cpu_limit_percent: CPU limit
        memory_limit_mb: Memory limit
        disk_limit_gb: Disk limit
        max_concurrent_tasks: Max tasks

    Returns:
        Initialized resource monitor

    """
    global _resource_monitor
    _resource_monitor = ResourceMonitor(
        cpu_limit_percent,
        memory_limit_mb,
        disk_limit_gb,
        max_concurrent_tasks,
    )
    return _resource_monitor
