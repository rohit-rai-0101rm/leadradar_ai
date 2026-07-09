import base64
import json

import pytest

from leadradar.agents.verdict import get_verdict
from leadradar.core.config import settings

BUSINESS = {"name": "Test Cafe"}

AUDIT_NO_WEBSITE = {
    "loaded": False,
    "load_time_ms": None,
    "has_ssl": False,
    "has_mobile_viewport": False,
    "screenshot_path": None,
    "error": "no_website",
}


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self) -> dict:
        return self._json_data

    def raise_for_status(self) -> None:
        pass


def _groq_response(content: str) -> FakeResponse:
    return FakeResponse(200, json_data={"choices": [{"message": {"content": content}}]})


def _audit_with_screenshot(path: str) -> dict:
    return {
        "loaded": True,
        "load_time_ms": 1200,
        "has_ssl": True,
        "has_mobile_viewport": False,
        "screenshot_path": path,
        "error": None,
    }


@pytest.fixture(autouse=True)
def _fake_keys(monkeypatch):
    monkeypatch.setattr(settings, "groq_key_1", "fake-groq-key")
    monkeypatch.setattr(settings, "groq_key_2", None)
    monkeypatch.setattr(settings, "gemini_key_1", None)
    monkeypatch.setattr(settings, "openrouter_key_1", "fake-openrouter-key")


def test_get_verdict_with_screenshot_sends_image_and_parses(tmp_path, monkeypatch):
    screenshot = tmp_path / "shot.png"
    screenshot.write_bytes(b"fake-png-bytes")
    expected_b64 = base64.b64encode(b"fake-png-bytes").decode()

    captured_bodies = []

    def fake_post(url, *args, **kwargs):
        captured_bodies.append(kwargs["json"])
        return _groq_response(
            json.dumps({"needs_redesign": True, "reasoning": "Looks outdated and cluttered."})
        )

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_verdict(BUSINESS, _audit_with_screenshot(str(screenshot)))

    assert result == {
        "needs_redesign": True,
        "reasoning": "Looks outdated and cluttered.",
        "error": None,
    }
    content = captured_bodies[0]["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[1]["image_url"]["url"] == f"data:image/png;base64,{expected_b64}"


def test_get_verdict_without_screenshot_sends_text_only(monkeypatch):
    captured_bodies = []

    def fake_post(url, *args, **kwargs):
        captured_bodies.append(kwargs["json"])
        return _groq_response(
            json.dumps({"needs_redesign": True, "reasoning": "No website at all is a major gap."})
        )

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_verdict(BUSINESS, AUDIT_NO_WEBSITE)

    assert result["needs_redesign"] is True
    content = captured_bodies[0]["messages"][0]["content"]
    assert isinstance(content, str)


def test_get_verdict_retries_once_on_malformed_json(monkeypatch):
    responses = [
        _groq_response("sorry, I cannot help with that"),
        _groq_response(
            json.dumps({"needs_redesign": False, "reasoning": "Site looks fine and modern."})
        ),
    ]
    calls = {"count": 0}

    def fake_post(url, *args, **kwargs):
        resp = responses[calls["count"]]
        calls["count"] += 1
        return resp

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_verdict(BUSINESS, AUDIT_NO_WEBSITE)

    assert calls["count"] == 2
    assert result == {
        "needs_redesign": False,
        "reasoning": "Site looks fine and modern.",
        "error": None,
    }


def test_get_verdict_falls_back_when_both_attempts_malformed(monkeypatch):
    def fake_post(url, *args, **kwargs):
        return _groq_response("not json at all")

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_verdict(BUSINESS, AUDIT_NO_WEBSITE)

    assert result["error"] == "verdict_parse_failed"
    assert result["needs_redesign"] is True


def test_get_verdict_parses_markdown_fenced_json_on_first_try(monkeypatch):
    calls = {"count": 0}

    def fake_post(url, *args, **kwargs):
        calls["count"] += 1
        fenced = (
            "```json\n"
            + json.dumps({"needs_redesign": True, "reasoning": "Broken layout on mobile."})
            + "\n```"
        )
        return _groq_response(fenced)

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_verdict(BUSINESS, AUDIT_NO_WEBSITE)

    assert calls["count"] == 1
    assert result == {
        "needs_redesign": True,
        "reasoning": "Broken layout on mobile.",
        "error": None,
    }
