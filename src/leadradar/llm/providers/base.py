from abc import ABC, abstractmethod


def openai_style_content(prompt: str, image_base64: str | None = None) -> str | list[dict]:
    """Builds the `content` field for OpenAI-compatible chat completion APIs
    (used by both Groq and OpenRouter). Returns a plain string when there's
    no image, or a multimodal content list when there is.
    """
    if image_base64 is None:
        return prompt
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
    ]


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
    def complete(self, prompt: str, image_base64: str | None = None) -> str:
        """Send prompt (and optional base64-encoded image) to the provider,
        return completion text.

        Must raise RateLimitError on HTTP 429 and AuthError on HTTP 401/403
        so the Router can catch them and fail over.
        """
