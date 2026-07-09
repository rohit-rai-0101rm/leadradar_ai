"""Manual smoke test: hits real provider APIs through the Router.

Run with: uv run python scripts/smoke_test_router.py
Requires real keys in .env (GROQ_KEY_1 and/or OPENROUTER_KEY_1 and/or GEMINI_KEY_1).
"""

import logging

from leadradar.core.config import settings
from leadradar.llm.router import ProviderConfig, Router, RouterExhaustedError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def build_providers() -> list[ProviderConfig]:
    providers: list[ProviderConfig] = []

    groq_keys = [k for k in [settings.groq_key_1, settings.groq_key_2] if k]
    if groq_keys:
        providers.append({"name": "groq", "keys": groq_keys, "model": "llama-3.3-70b-versatile"})

    if settings.gemini_key_1:
        providers.append(
            {"name": "gemini", "keys": [settings.gemini_key_1], "model": "gemini-2.0-flash"}
        )

    if settings.openrouter_key_1:
        providers.append(
            {
                "name": "openrouter",
                "keys": [settings.openrouter_key_1],
                "model": "meta-llama/llama-3.1-8b-instruct:free",
            }
        )

    return providers


def main() -> None:
    providers = build_providers()
    if not providers:
        raise SystemExit("No provider keys found in .env — add at least one and retry.")

    print(f"Configured providers (in priority order): {[p['name'] for p in providers]}")

    router = Router(providers=providers)
    try:
        result = router.complete("Say hello in exactly five words.")
    except RouterExhaustedError as exc:
        raise SystemExit(f"Router exhausted: {exc}") from exc

    print(f"\nResponse: {result}")


if __name__ == "__main__":
    main()
