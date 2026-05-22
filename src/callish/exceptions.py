"""Exceptions raised by adapters and propagated through the callish façade."""

from __future__ import annotations


class AdapterError(Exception):
    """Base class for all adapter-raised errors."""


class NotFound(AdapterError):
    """The requested record does not exist upstream.

    The façade maps this to the model's ``DoesNotExist`` for Django parity.
    """


class Unauthorized(AdapterError):
    """Authentication or authorization failed upstream."""


class RateLimited(AdapterError):
    """The upstream API is rate-limiting the caller."""

    def __init__(self, *args: object, retry_after: float | None = None) -> None:
        super().__init__(*args)
        self.retry_after = retry_after


class Upstream5xx(AdapterError):
    """The upstream API returned a server error."""

    def __init__(self, *args: object, status: int | None = None) -> None:
        super().__init__(*args)
        self.status = status


class AdapterValidationError(AdapterError):
    """The upstream rejected the payload with field-level validation errors.

    ``errors`` is a mapping of field name to a list of error strings,
    matching Django's ``ValidationError.message_dict`` shape.
    """

    def __init__(
        self,
        message: str = "Adapter validation failed",
        *,
        errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors: dict[str, list[str]] = errors or {}
