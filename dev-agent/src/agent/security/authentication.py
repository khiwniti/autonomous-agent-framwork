"""API authentication and authorization - Phase 5."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field


class User(BaseModel):
    """User model."""

    id: str = Field(description="User ID")
    username: str = Field(description="Username")
    email: str | None = Field(default=None, description="Email")
    is_active: bool = Field(default=True, description="Is user active")
    is_admin: bool = Field(default=False, description="Is user admin")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp"
    )


class APIKey(BaseModel):
    """API key model."""

    key: str = Field(description="API key")
    name: str = Field(description="Key name")
    user_id: str = Field(description="Owner user ID")
    is_active: bool = Field(default=True, description="Is key active")
    expires_at: datetime | None = Field(default=None, description="Expiration timestamp")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp"
    )
    last_used: datetime | None = Field(default=None, description="Last used timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Key metadata")


class TokenData(BaseModel):
    """JWT token data."""

    sub: str = Field(description="Subject (user ID)")
    exp: datetime = Field(description="Expiration timestamp")
    iat: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Issued at timestamp"
    )
    scopes: list[str] = Field(default_factory=list, description="Permission scopes")


class AuthManager:
    """Manages authentication and authorization."""

    def __init__(
        self,
        secret_key: str | None = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
    ):
        """Initialize auth manager.

        Args:
            secret_key: JWT secret key (generated if not provided)
            algorithm: JWT algorithm
            access_token_expire_minutes: Access token expiration

        """
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes

        # In-memory storage (in production, use database)
        self.users: dict[str, User] = {}
        self.api_keys: dict[str, APIKey] = {}
        self.key_hashes: dict[str, str] = {}  # hash -> key_id

    def generate_api_key(
        self, user_id: str, name: str, expires_in_days: int | None = None
    ) -> str:
        """Generate a new API key.

        Args:
            user_id: User ID
            name: Key name
            expires_in_days: Optional expiration in days

        Returns:
            API key

        """
        # Generate secure random key
        key = f"sk-{secrets.token_urlsafe(32)}"

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Store API key
        api_key = APIKey(
            key=key,
            name=name,
            user_id=user_id,
            expires_at=expires_at,
        )
        self.api_keys[key] = api_key

        # Store hash for lookup
        key_hash = self._hash_key(key)
        self.key_hashes[key_hash] = key

        return key

    def validate_api_key(self, key: str) -> APIKey | None:
        """Validate an API key.

        Args:
            key: API key

        Returns:
            API key object or None if invalid

        """
        api_key = self.api_keys.get(key)

        if not api_key:
            return None

        # Check if active
        if not api_key.is_active:
            return None

        # Check if expired
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return None

        # Update last used
        api_key.last_used = datetime.now(timezone.utc)

        return api_key

    def revoke_api_key(self, key: str) -> bool:
        """Revoke an API key.

        Args:
            key: API key

        Returns:
            True if revoked, False if not found

        """
        api_key = self.api_keys.get(key)

        if not api_key:
            return False

        api_key.is_active = False
        return True

    def create_access_token(
        self, user_id: str, scopes: list[str] | None = None
    ) -> str:
        """Create a JWT access token.

        Args:
            user_id: User ID
            scopes: Permission scopes

        Returns:
            JWT token

        """
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=self.access_token_expire_minutes
        )

        token_data = TokenData(sub=user_id, exp=expires, scopes=scopes or [])

        encoded_jwt = jwt.encode(
            token_data.model_dump(),
            self.secret_key,
            algorithm=self.algorithm,
        )

        return encoded_jwt

    def verify_token(self, token: str) -> TokenData | None:
        """Verify a JWT token.

        Args:
            token: JWT token

        Returns:
            Token data or None if invalid

        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            token_data = TokenData(**payload)

            # Check expiration
            if token_data.exp < datetime.now(timezone.utc):
                return None

            return token_data

        except JWTError:
            return None

    def create_user(
        self, username: str, email: str | None = None, is_admin: bool = False
    ) -> User:
        """Create a new user.

        Args:
            username: Username
            email: Optional email
            is_admin: Is user admin

        Returns:
            Created user

        """
        user_id = f"user_{secrets.token_urlsafe(16)}"
        user = User(
            id=user_id, username=username, email=email, is_admin=is_admin
        )
        self.users[user_id] = user
        return user

    def get_user(self, user_id: str) -> User | None:
        """Get a user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None if not found

        """
        return self.users.get(user_id)

    def _hash_key(self, key: str) -> str:
        """Hash an API key for storage.

        Args:
            key: API key

        Returns:
            Hashed key

        """
        return hashlib.sha256(key.encode()).hexdigest()


# FastAPI dependencies


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def get_api_key(
    api_key: str = Security(api_key_header),
    auth_manager: AuthManager = Depends(),
) -> APIKey:
    """Dependency to get and validate API key.

    Args:
        api_key: API key from header
        auth_manager: Auth manager

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is invalid

    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    validated_key = auth_manager.validate_api_key(api_key)

    if not validated_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return validated_key


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    auth_manager: AuthManager = Depends(),
) -> User:
    """Dependency to get current user from JWT token.

    Args:
        credentials: Bearer token credentials
        auth_manager: Auth manager

    Returns:
        Current user

    Raises:
        HTTPException: If token is invalid

    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = auth_manager.verify_token(credentials.credentials)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_manager.get_user(token_data.sub)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin privileges.

    Args:
        current_user: Current user

    Returns:
        Current user if admin

    Raises:
        HTTPException: If user is not admin

    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )

    return current_user
