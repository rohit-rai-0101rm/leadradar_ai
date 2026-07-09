from abc import ABC, abstractmethod


class RateLimitError(Exception):
    """Raised when a provider returns a 429 quota-exceeded response."""


class AuthError(Exception):
    """Raised when a provider returns a 401/403 auth-failure response."""


class Provider(ABC):
    name: str

    def __init__(self, key: str, model: str) -> None:
        self.key = key
        self.model = model

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Send prompt to the provider, return completion text.

        Must raise RateLimitError on HTTP 429 and AuthError on HTTP 401/403
        so the Router can catch them and fail over.
        """
