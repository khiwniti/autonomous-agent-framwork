"""Secrets management system - Phase 6."""

import base64
import json
import os
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from pydantic import BaseModel, Field

from agent.observability.audit import get_audit_logger, AuditEventType, AuditSeverity


class SecretType(str, Enum):
    """Secret types."""

    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    DATABASE_URL = "database_url"
    GENERIC = "generic"


class SecretBackend(str, Enum):
    """Secret storage backends."""

    FILE = "file"  # Encrypted file storage
    ENVIRONMENT = "environment"  # Environment variables
    MEMORY = "memory"  # In-memory storage (not persistent)


class Secret(BaseModel):
    """Secret model."""

    name: str = Field(description="Secret name")
    type: SecretType = Field(description="Secret type")
    value: str = Field(description="Secret value (encrypted)")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    expires_at: datetime | None = Field(default=None, description="Expiration time")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")
    rotation_enabled: bool = Field(default=False, description="Rotation enabled")
    rotation_interval_days: int = Field(default=90, description="Rotation interval")


class SecretsManager:
    """Manages secrets with encryption and secure storage."""

    def __init__(
        self,
        backend: SecretBackend = SecretBackend.FILE,
        secrets_file: str | Path | None = None,
        encryption_key: str | None = None,
        master_password: str | None = None,
    ):
        """Initialize secrets manager.

        Args:
            backend: Storage backend
            secrets_file: Path to secrets file (for FILE backend)
            encryption_key: Base64-encoded encryption key
            master_password: Master password for key derivation

        """
        self.backend = backend
        self.secrets_file = Path(secrets_file) if secrets_file else Path(".secrets/secrets.json")
        self.audit_logger = get_audit_logger()

        # Initialize encryption
        if encryption_key:
            self.encryption_key = encryption_key.encode()
        elif master_password:
            self.encryption_key = self._derive_key(master_password)
        else:
            # Generate new key
            self.encryption_key = Fernet.generate_key()

        self.cipher = Fernet(self.encryption_key)

        # Storage
        self.secrets: dict[str, Secret] = {}

        # Load existing secrets
        if backend == SecretBackend.FILE:
            self._load_from_file()
        elif backend == SecretBackend.ENVIRONMENT:
            self._load_from_environment()

    def _derive_key(self, password: str, salt: bytes | None = None) -> bytes:
        """Derive encryption key from password.

        Args:
            password: Master password
            salt: Optional salt (generates if None)

        Returns:
            Derived key

        """
        if salt is None:
            salt = b"autonomous-agent-salt"  # In production, use random salt

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def _encrypt(self, value: str) -> str:
        """Encrypt value.

        Args:
            value: Plain text value

        Returns:
            Encrypted value (base64)

        """
        encrypted = self.cipher.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, encrypted_value: str) -> str:
        """Decrypt value.

        Args:
            encrypted_value: Encrypted value (base64)

        Returns:
            Decrypted plain text

        """
        encrypted = base64.b64decode(encrypted_value.encode())
        decrypted = self.cipher.decrypt(encrypted)
        return decrypted.decode()

    def set_secret(
        self,
        name: str,
        value: str,
        secret_type: SecretType = SecretType.GENERIC,
        expires_in_days: int | None = None,
        rotation_enabled: bool = False,
        rotation_interval_days: int = 90,
        metadata: dict[str, Any] | None = None,
    ) -> Secret:
        """Set secret value.

        Args:
            name: Secret name
            value: Secret value
            secret_type: Secret type
            expires_in_days: Expiration period in days
            rotation_enabled: Enable automatic rotation
            rotation_interval_days: Rotation interval
            metadata: Additional metadata

        Returns:
            Created secret

        """
        # Encrypt value
        encrypted_value = self._encrypt(value)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        now = datetime.now(timezone.utc)

        secret = Secret(
            name=name,
            type=secret_type,
            value=encrypted_value,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            metadata=metadata or {},
            rotation_enabled=rotation_enabled,
            rotation_interval_days=rotation_interval_days,
        )

        self.secrets[name] = secret

        # Persist
        if self.backend == SecretBackend.FILE:
            self._save_to_file()

        # Audit log
        self.audit_logger.log_event(
            event_type=AuditEventType.DATA_CREATE,
            action=f"set secret {name}",
            outcome="success",
            severity=AuditSeverity.MEDIUM,
            resource_type="secret",
            resource_id=name,
            details={"secret_type": secret_type.value},
        )

        return secret

    def get_secret(
        self,
        name: str,
        user_id: str | None = None,
    ) -> str | None:
        """Get secret value.

        Args:
            name: Secret name
            user_id: User accessing secret

        Returns:
            Decrypted secret value or None

        """
        if name not in self.secrets:
            self.audit_logger.log_event(
                event_type=AuditEventType.DATA_READ,
                action=f"get secret {name}",
                outcome="failure",
                severity=AuditSeverity.LOW,
                user_id=user_id,
                resource_type="secret",
                resource_id=name,
                details={"error": "secret not found"},
            )
            return None

        secret = self.secrets[name]

        # Check expiration
        if secret.expires_at and datetime.now(timezone.utc) > secret.expires_at:
            self.audit_logger.log_event(
                event_type=AuditEventType.DATA_READ,
                action=f"get secret {name}",
                outcome="failure",
                severity=AuditSeverity.MEDIUM,
                user_id=user_id,
                resource_type="secret",
                resource_id=name,
                details={"error": "secret expired"},
            )
            return None

        # Decrypt value
        try:
            decrypted = self._decrypt(secret.value)

            # Audit log
            self.audit_logger.log_event(
                event_type=AuditEventType.DATA_READ,
                action=f"get secret {name}",
                outcome="success",
                severity=AuditSeverity.LOW,
                user_id=user_id,
                resource_type="secret",
                resource_id=name,
            )

            return decrypted

        except Exception as e:
            self.audit_logger.log_event(
                event_type=AuditEventType.DATA_READ,
                action=f"get secret {name}",
                outcome="failure",
                severity=AuditSeverity.HIGH,
                user_id=user_id,
                resource_type="secret",
                resource_id=name,
                details={"error": str(e)},
            )
            return None

    def delete_secret(
        self,
        name: str,
        user_id: str | None = None,
    ) -> bool:
        """Delete secret.

        Args:
            name: Secret name
            user_id: User deleting secret

        Returns:
            True if deleted, False otherwise

        """
        if name not in self.secrets:
            return False

        del self.secrets[name]

        # Persist
        if self.backend == SecretBackend.FILE:
            self._save_to_file()

        # Audit log
        self.audit_logger.log_event(
            event_type=AuditEventType.DATA_DELETE,
            action=f"delete secret {name}",
            outcome="success",
            severity=AuditSeverity.HIGH,
            user_id=user_id,
            resource_type="secret",
            resource_id=name,
        )

        return True

    def list_secrets(
        self,
        secret_type: SecretType | None = None,
    ) -> list[dict[str, Any]]:
        """List secrets (metadata only, no values).

        Args:
            secret_type: Filter by secret type

        Returns:
            List of secret metadata

        """
        result = []

        for name, secret in self.secrets.items():
            if secret_type and secret.type != secret_type:
                continue

            result.append({
                "name": name,
                "type": secret.type.value,
                "created_at": secret.created_at.isoformat(),
                "expires_at": secret.expires_at.isoformat() if secret.expires_at else None,
                "rotation_enabled": secret.rotation_enabled,
                "metadata": secret.metadata,
            })

        return result

    def rotate_secret(
        self,
        name: str,
        new_value: str,
        user_id: str | None = None,
    ) -> bool:
        """Rotate secret value.

        Args:
            name: Secret name
            new_value: New secret value
            user_id: User rotating secret

        Returns:
            True if rotated, False otherwise

        """
        if name not in self.secrets:
            return False

        secret = self.secrets[name]

        # Update value
        secret.value = self._encrypt(new_value)
        secret.updated_at = datetime.now(timezone.utc)

        # Persist
        if self.backend == SecretBackend.FILE:
            self._save_to_file()

        # Audit log
        self.audit_logger.log_event(
            event_type=AuditEventType.DATA_UPDATE,
            action=f"rotate secret {name}",
            outcome="success",
            severity=AuditSeverity.HIGH,
            user_id=user_id,
            resource_type="secret",
            resource_id=name,
        )

        return True

    def check_expiration(self) -> list[str]:
        """Check for expired or expiring secrets.

        Returns:
            List of expired secret names

        """
        expired = []
        now = datetime.now(timezone.utc)

        for name, secret in self.secrets.items():
            if secret.expires_at and now > secret.expires_at:
                expired.append(name)

        return expired

    def check_rotation_needed(self) -> list[str]:
        """Check secrets needing rotation.

        Returns:
            List of secret names needing rotation

        """
        needs_rotation = []
        now = datetime.now(timezone.utc)

        for name, secret in self.secrets.items():
            if not secret.rotation_enabled:
                continue

            rotation_due = secret.updated_at + timedelta(
                days=secret.rotation_interval_days
            )

            if now >= rotation_due:
                needs_rotation.append(name)

        return needs_rotation

    def _save_to_file(self) -> None:
        """Save secrets to file."""
        if not self.secrets_file:
            return

        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            name: secret.model_dump(mode="json")
            for name, secret in self.secrets.items()
        }

        with open(self.secrets_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

        # Set restrictive permissions
        os.chmod(self.secrets_file, 0o600)

    def _load_from_file(self) -> None:
        """Load secrets from file."""
        if not self.secrets_file or not self.secrets_file.exists():
            return

        with open(self.secrets_file, "r") as f:
            data = json.load(f)

        for name, secret_data in data.items():
            self.secrets[name] = Secret.model_validate(secret_data)

    def _load_from_environment(self) -> None:
        """Load secrets from environment variables."""
        prefix = "SECRET_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                name = key[len(prefix):].lower()
                encrypted_value = self._encrypt(value)

                self.secrets[name] = Secret(
                    name=name,
                    type=SecretType.GENERIC,
                    value=encrypted_value,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

    def export_encryption_key(self) -> str:
        """Export encryption key (base64).

        Returns:
            Base64-encoded encryption key

        Warning:
            Store this key securely! Loss means secrets cannot be decrypted.

        """
        return base64.b64encode(self.encryption_key).decode()


# Global secrets manager
_secrets_manager: SecretsManager | None = None


def get_secrets_manager() -> SecretsManager:
    """Get global secrets manager.

    Returns:
        Global secrets manager instance

    """
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def initialize_secrets_manager(
    backend: SecretBackend = SecretBackend.FILE,
    secrets_file: str | Path | None = None,
    encryption_key: str | None = None,
    master_password: str | None = None,
) -> SecretsManager:
    """Initialize global secrets manager.

    Args:
        backend: Storage backend
        secrets_file: Secrets file path
        encryption_key: Encryption key
        master_password: Master password

    Returns:
        Initialized secrets manager

    """
    global _secrets_manager
    _secrets_manager = SecretsManager(
        backend, secrets_file, encryption_key, master_password
    )
    return _secrets_manager
