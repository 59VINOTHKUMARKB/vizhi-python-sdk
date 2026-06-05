"""Exceptions raised by the Vizhi Python SDK."""

from __future__ import annotations


class VizhiError(Exception):
    """Base class for all SDK errors."""


class AuthenticationError(VizhiError):
    """Raised when the Vizhi API token is rejected."""


class APIError(VizhiError):
    """Raised when the Vizhi backend returns an unsuccessful response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class InvalidResponseError(VizhiError):
    """Raised when the backend response does not match the SDK contract."""
