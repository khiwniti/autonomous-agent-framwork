"""Input validation and sanitization - Phase 6."""

import html
import re
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field, field_validator


class ValidationError(Exception):
    """Validation error exception."""

    pass


class SanitizationMode(str, Enum):
    """Sanitization modes."""

    STRICT = "strict"  # Reject any suspicious input
    ESCAPE = "escape"  # Escape special characters
    STRIP = "strip"  # Remove suspicious patterns
    PERMISSIVE = "permissive"  # Allow with minimal sanitization


class InputValidator:
    """Input validation and sanitization utilities."""

    # Dangerous patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bunion\b.*\bselect\b)",
        r"(\bor\b\s+\d+\s*=\s*\d+)",
        r"(--[\s]*$)",
        r"(/\*.*\*/)",
        r"(;\s*drop\s+table)",
        r"(;\s*delete\s+from)",
        r"(;\s*insert\s+into)",
        r"(xp_cmdshell)",
        r"(exec\s*\()",
    ]

    XSS_PATTERNS = [
        r"<script[\s>]",
        r"javascript:",
        r"on\w+\s*=",  # Event handlers like onclick=
        r"<iframe[\s>]",
        r"<object[\s>]",
        r"<embed[\s>]",
    ]

    COMMAND_INJECTION_PATTERNS = [
        r"[;&|`$()]",  # Shell metacharacters
        r"\$\{.*\}",  # Variable expansion
        r"\$\(.*\)",  # Command substitution
    ]

    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.",
        r"~",
    ]

    # Safe characters for different contexts
    ALPHANUMERIC = re.compile(r"^[a-zA-Z0-9]+$")
    ALPHANUMERIC_DASH = re.compile(r"^[a-zA-Z0-9\-_]+$")
    EMAIL = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    URL = re.compile(
        r"^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=]+$"
    )

    @classmethod
    def sanitize_string(
        cls,
        value: str,
        mode: SanitizationMode = SanitizationMode.ESCAPE,
        max_length: int | None = None,
    ) -> str:
        """Sanitize string input.

        Args:
            value: Input string
            mode: Sanitization mode
            max_length: Maximum length

        Returns:
            Sanitized string

        Raises:
            ValidationError: If validation fails

        """
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value)}")

        # Check length
        if max_length and len(value) > max_length:
            if mode == SanitizationMode.STRICT:
                raise ValidationError(f"String exceeds maximum length {max_length}")
            value = value[:max_length]

        # Check for dangerous patterns
        if mode == SanitizationMode.STRICT:
            cls._check_dangerous_patterns(value)

        # Escape HTML by default
        if mode in [SanitizationMode.ESCAPE, SanitizationMode.PERMISSIVE]:
            value = html.escape(value)

        # Strip dangerous characters
        if mode == SanitizationMode.STRIP:
            value = cls._strip_dangerous_chars(value)

        return value

    @classmethod
    def _check_dangerous_patterns(cls, value: str) -> None:
        """Check for dangerous patterns.

        Args:
            value: Input string

        Raises:
            ValidationError: If dangerous pattern found

        """
        value_lower = value.lower()

        # Check SQL injection
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise ValidationError(f"Potential SQL injection detected: {pattern}")

        # Check XSS
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise ValidationError(f"Potential XSS detected: {pattern}")

        # Check command injection
        for pattern in cls.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, value):
                raise ValidationError(
                    f"Potential command injection detected: {pattern}"
                )

    @classmethod
    def _strip_dangerous_chars(cls, value: str) -> str:
        """Strip dangerous characters.

        Args:
            value: Input string

        Returns:
            Stripped string

        """
        # Remove null bytes
        value = value.replace("\x00", "")

        # Remove control characters except newline and tab
        value = "".join(char for char in value if ord(char) >= 32 or char in "\n\t")

        return value

    @classmethod
    def validate_alphanumeric(
        cls, value: str, allow_dash: bool = False
    ) -> str:
        """Validate alphanumeric input.

        Args:
            value: Input string
            allow_dash: Allow dash and underscore

        Returns:
            Validated string

        Raises:
            ValidationError: If validation fails

        """
        pattern = cls.ALPHANUMERIC_DASH if allow_dash else cls.ALPHANUMERIC
        if not pattern.match(value):
            raise ValidationError(
                f"Value must be alphanumeric{' with dash/underscore' if allow_dash else ''}"
            )
        return value

    @classmethod
    def validate_email(cls, value: str) -> str:
        """Validate email address.

        Args:
            value: Email address

        Returns:
            Validated email

        Raises:
            ValidationError: If validation fails

        """
        if not cls.EMAIL.match(value):
            raise ValidationError("Invalid email address")
        return value.lower()

    @classmethod
    def validate_url(
        cls,
        value: str,
        allowed_schemes: list[str] = ["http", "https"],
    ) -> str:
        """Validate URL.

        Args:
            value: URL string
            allowed_schemes: Allowed URL schemes

        Returns:
            Validated URL

        Raises:
            ValidationError: If validation fails

        """
        try:
            parsed = urlparse(value)

            if parsed.scheme not in allowed_schemes:
                raise ValidationError(
                    f"URL scheme must be one of {allowed_schemes}"
                )

            if not parsed.netloc:
                raise ValidationError("URL must have a valid domain")

            return value

        except Exception as e:
            raise ValidationError(f"Invalid URL: {str(e)}")

    @classmethod
    def validate_path(
        cls,
        value: str,
        base_path: Path | None = None,
        allow_absolute: bool = False,
    ) -> Path:
        """Validate file path.

        Args:
            value: Path string
            base_path: Base directory path
            allow_absolute: Allow absolute paths

        Returns:
            Validated path

        Raises:
            ValidationError: If validation fails

        """
        # Check for path traversal
        for pattern in cls.PATH_TRAVERSAL_PATTERNS:
            if pattern in value:
                raise ValidationError(f"Path traversal detected: {pattern}")

        path = Path(value)

        # Check absolute path
        if path.is_absolute() and not allow_absolute:
            raise ValidationError("Absolute paths not allowed")

        # Resolve and check against base path
        if base_path:
            try:
                resolved = (base_path / path).resolve()
                if not str(resolved).startswith(str(base_path.resolve())):
                    raise ValidationError("Path escapes base directory")
                return resolved
            except Exception as e:
                raise ValidationError(f"Invalid path: {str(e)}")

        return path

    @classmethod
    def validate_integer(
        cls,
        value: Any,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> int:
        """Validate integer input.

        Args:
            value: Input value
            min_value: Minimum value
            max_value: Maximum value

        Returns:
            Validated integer

        Raises:
            ValidationError: If validation fails

        """
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid integer: {value}")

        if min_value is not None and int_value < min_value:
            raise ValidationError(f"Value must be >= {min_value}")

        if max_value is not None and int_value > max_value:
            raise ValidationError(f"Value must be <= {max_value}")

        return int_value

    @classmethod
    def validate_float(
        cls,
        value: Any,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> float:
        """Validate float input.

        Args:
            value: Input value
            min_value: Minimum value
            max_value: Maximum value

        Returns:
            Validated float

        Raises:
            ValidationError: If validation fails

        """
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid float: {value}")

        if min_value is not None and float_value < min_value:
            raise ValidationError(f"Value must be >= {min_value}")

        if max_value is not None and float_value > max_value:
            raise ValidationError(f"Value must be <= {max_value}")

        return float_value

    @classmethod
    def validate_enum(
        cls,
        value: str,
        allowed_values: list[str],
        case_sensitive: bool = True,
    ) -> str:
        """Validate enum/choice input.

        Args:
            value: Input value
            allowed_values: List of allowed values
            case_sensitive: Case-sensitive comparison

        Returns:
            Validated value

        Raises:
            ValidationError: If validation fails

        """
        if not case_sensitive:
            value = value.lower()
            allowed_values = [v.lower() for v in allowed_values]

        if value not in allowed_values:
            raise ValidationError(f"Value must be one of {allowed_values}")

        return value

    @classmethod
    def sanitize_sql(cls, value: str) -> str:
        """Sanitize SQL input (for display, NOT for parameterized queries).

        Args:
            value: SQL string

        Returns:
            Sanitized SQL

        Note:
            This is for display purposes only. Always use parameterized queries.

        """
        # Escape single quotes
        value = value.replace("'", "''")

        # Remove comments
        value = re.sub(r"--.*$", "", value, flags=re.MULTILINE)
        value = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL)

        return value

    @classmethod
    def sanitize_shell(cls, value: str) -> str:
        """Sanitize shell input (for display, NOT for execution).

        Args:
            value: Shell command string

        Returns:
            Sanitized string

        Note:
            Never execute user input as shell commands. Use this for display only.

        """
        # Remove shell metacharacters
        dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">", "\n"]
        for char in dangerous_chars:
            value = value.replace(char, "")

        return value


class SecureInput(BaseModel):
    """Secure input model with validation."""

    value: str = Field(description="Input value")
    sanitized: bool = Field(default=False, description="Whether value is sanitized")

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: str) -> str:
        """Validate input value.

        Args:
            v: Input value

        Returns:
            Validated value

        """
        return InputValidator.sanitize_string(v, mode=SanitizationMode.ESCAPE)


class ValidationResult(BaseModel):
    """Validation result."""

    valid: bool = Field(description="Whether input is valid")
    sanitized_value: Any | None = Field(default=None, description="Sanitized value")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


def validate_input(
    value: Any,
    validator_func: callable,
    *args,
    **kwargs,
) -> ValidationResult:
    """Validate input with error handling.

    Args:
        value: Input value
        validator_func: Validator function
        *args: Additional positional arguments
        **kwargs: Additional keyword arguments

    Returns:
        Validation result

    """
    try:
        sanitized = validator_func(value, *args, **kwargs)
        return ValidationResult(valid=True, sanitized_value=sanitized)

    except ValidationError as e:
        return ValidationResult(
            valid=False,
            errors=[str(e)],
        )

    except Exception as e:
        return ValidationResult(
            valid=False,
            errors=[f"Unexpected error: {str(e)}"],
        )
