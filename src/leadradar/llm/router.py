import logging
import time
from typing import TypedDict

from leadradar.llm import cooldown
from leadradar.llm.providers.base import AuthError, Provider, ProviderError, RateLimitError
from leadradar.llm.providers.gemini_provider import GeminiProvider
from leadradar.llm.providers.groq_provider import GroqProvider
from leadradar.llm.providers.openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)

PROVIDER_CLASSES: dict[str, type[Provider]] = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
}


class ProviderConfig(TypedDict):
    name: str
    keys: list[str]
    model: str


class RouterExhaustedError(Exception):
    """Raised when every provider/key combination has failed or is cooling down."""


class Router:
    def __init__(self, providers: list[ProviderConfig], cooldown_minutes: int = 60) -> None:
        self.providers = providers
        self.cooldown_minutes = cooldown_minutes

    def complete(self, prompt: str, image_base64: str | None = None) -> str:
        for provider_config in self.providers:
            provider_name = provider_config["name"]
            provider_cls = PROVIDER_CLASSES[provider_name]
            for key in provider_config["keys"]:
                if cooldown.is_cooling_down(provider_name, key):
                    continue

                provider = provider_cls(key=key, model=provider_config["model"])
                try:
                    return provider.complete(prompt, image_base64)
                except (RateLimitError, AuthError, ProviderError) as exc:
                    if isinstance(exc, RateLimitError):
                        reason = "rate_limit"
                    elif isinstance(exc, AuthError):
                        reason = "auth_error"
                    else:
                        reason = "provider_error"
                    cooldown.mark_cooling_down(provider_name, key, minutes=self.cooldown_minutes)
                    logger.warning(
                        "llm_router_fallback provider=%s reason=%s timestamp=%s",
                        provider_name,
                        reason,
                        time.time(),
                    )
                    continue

        raise RouterExhaustedError(
            "All configured LLM providers/keys failed or are cooling down."
        )
