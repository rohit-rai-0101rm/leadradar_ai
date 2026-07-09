import logging

import pytest

from leadradar.llm import cooldown
from leadradar.llm.router import Router, RouterExhaustedError


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self) -> dict:
        return self._json_data

    def raise_for_status(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _reset_cooldown():
    cooldown.reset()
    yield
    cooldown.reset()


def test_router_falls_back_to_next_provider_on_429(monkeypatch, caplog):
    """Groq's only key hits a simulated 429; router should mark it cooling
    down, log the fallback, and succeed via the Gemini provider instead."""

    def fake_post(url, *args, **kwargs):
        if "groq.com" in url:
            return FakeResponse(429, text="quota exceeded")
        if "generativelanguage.googleapis.com" in url:
            return FakeResponse(
                200,
                json_data={
                    "candidates": [
                        {"content": {"parts": [{"text": "hello from gemini"}]}}
                    ]
                },
            )
        raise AssertionError(f"unexpected provider called: {url}")

    monkeypatch.setattr("httpx.post", fake_post)

    router = Router(
        providers=[
            {"name": "groq", "keys": ["groq-key-1"], "model": "llama-3.3-70b"},
            {"name": "gemini", "keys": ["gemini-key-1"], "model": "gemini-2.0-flash"},
        ]
    )

    with caplog.at_level(logging.WARNING):
        result = router.complete("say hello")

    assert result == "hello from gemini"
    assert cooldown.is_cooling_down("groq", "groq-key-1") is True
    assert any("llm_router_fallback" in record.message for record in caplog.records)
    assert any("provider=groq" in record.message and "reason=rate_limit" in record.message for record in caplog.records)


def test_router_rotates_keys_within_same_provider_before_falling_back(monkeypatch):
    calls = []

    def fake_post(url, *args, **kwargs):
        headers = kwargs.get("headers", {})
        calls.append(headers.get("Authorization"))
        if headers.get("Authorization") == "Bearer groq-key-1":
            return FakeResponse(429, text="quota exceeded")
        return FakeResponse(
            200, json_data={"choices": [{"message": {"content": "second key worked"}}]}
        )

    monkeypatch.setattr("httpx.post", fake_post)

    router = Router(
        providers=[
            {"name": "groq", "keys": ["groq-key-1", "groq-key-2"], "model": "llama-3.3-70b"},
        ]
    )

    result = router.complete("say hello")

    assert result == "second key worked"
    assert calls == ["Bearer groq-key-1", "Bearer groq-key-2"]
    assert cooldown.is_cooling_down("groq", "groq-key-1") is True
    assert cooldown.is_cooling_down("groq", "groq-key-2") is False


def test_router_raises_when_all_providers_exhausted(monkeypatch):
    def fake_post(url, *args, **kwargs):
        return FakeResponse(429, text="quota exceeded")

    monkeypatch.setattr("httpx.post", fake_post)

    router = Router(
        providers=[
            {"name": "groq", "keys": ["groq-key-1"], "model": "llama-3.3-70b"},
            {"name": "gemini", "keys": ["gemini-key-1"], "model": "gemini-2.0-flash"},
        ]
    )

    with pytest.raises(RouterExhaustedError):
        router.complete("say hello")


def test_router_skips_keys_already_cooling_down(monkeypatch):
    cooldown.mark_cooling_down("groq", "groq-key-1", minutes=60)
    calls = []

    def fake_post(url, *args, **kwargs):
        calls.append(url)
        return FakeResponse(
            200, json_data={"choices": [{"message": {"content": "used fresh key"}}]}
        )

    monkeypatch.setattr("httpx.post", fake_post)

    router = Router(
        providers=[
            {"name": "groq", "keys": ["groq-key-1", "groq-key-2"], "model": "llama-3.3-70b"},
        ]
    )

    result = router.complete("say hello")

    assert result == "used fresh key"
    assert len(calls) == 1


def test_router_forwards_image_base64_to_provider(monkeypatch):
    captured_bodies = []

    def fake_post(url, *args, **kwargs):
        captured_bodies.append(kwargs["json"])
        return FakeResponse(
            200, json_data={"choices": [{"message": {"content": "described the image"}}]}
        )

    monkeypatch.setattr("httpx.post", fake_post)

    router = Router(
        providers=[{"name": "groq", "keys": ["groq-key-1"], "model": "llama-4-scout"}]
    )

    result = router.complete("describe this screenshot", image_base64="ZmFrZS1pbWFnZS1ieXRlcw==")

    assert result == "described the image"
    content = captured_bodies[0]["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "describe this screenshot"}
    assert content[1]["image_url"]["url"] == "data:image/png;base64,ZmFrZS1pbWFnZS1ieXRlcw=="
