"""Manual smoke test: hits real provider APIs through the Router.

Run with: uv run python scripts/smoke_test_router.py
Requires at least one real provider key in .env (see agents/providers.py
for which settings fields are checked).
"""

import logging

from leadradar.agents.providers import build_providers
from leadradar.llm.router import Router, RouterExhaustedError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


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
