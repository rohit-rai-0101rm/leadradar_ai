from leadradar.core.config import settings
from leadradar.llm.router import ProviderConfig


def build_providers() -> list[ProviderConfig]:
    providers: list[ProviderConfig] = []

    groq_keys = [k for k in [settings.groq_key_1, settings.groq_key_2] if k]
    if groq_keys:
        providers.append(
            {"name": "groq", "keys": groq_keys, "model": "meta-llama/llama-4-scout-17b-16e-instruct"}
        )

    gemini_keys = [
        k for k in [settings.gemini_key_1, settings.gemini_key_2, settings.gemini_key_3] if k
    ]
    if gemini_keys:
        providers.append(
            {"name": "gemini", "keys": gemini_keys, "model": "gemini-2.5-flash"}
        )

    if settings.openrouter_key_1:
        providers.append(
            {
                "name": "openrouter",
                "keys": [settings.openrouter_key_1],
                "model": "nvidia/nemotron-nano-12b-v2-vl:free",
            }
        )

    return providers
