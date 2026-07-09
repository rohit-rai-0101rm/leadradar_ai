import time

_cooldowns: dict[tuple[str, str], float] = {}


def mark_cooling_down(provider_name: str, key: str, minutes: int = 60) -> None:
    _cooldowns[(provider_name, key)] = time.time() + minutes * 60


def is_cooling_down(provider_name: str, key: str) -> bool:
    until = _cooldowns.get((provider_name, key))
    return until is not None and time.time() < until


def reset() -> None:
    """Clear all cooldown state. Intended for tests."""
    _cooldowns.clear()
