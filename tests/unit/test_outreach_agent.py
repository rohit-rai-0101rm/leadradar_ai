import json

import pytest

from leadradar.agents.outreach_agent import get_outreach_email
from leadradar.core.config import settings

BUSINESS = {"name": "Test Cafe", "address": "123 Test Rd, Bandra West", "website": None}
AUDIT_NO_WEBSITE = {
    "loaded": False,
    "load_time_ms": None,
    "has_ssl": False,
    "has_mobile_viewport": False,
    "screenshot_path": None,
    "error": "no_website",
}
VERDICT = {
    "needs_redesign": True,
    "reasoning": "The business has no website at all, a major digital-presence gap.",
    "error": None,
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


@pytest.fixture(autouse=True)
def _fake_keys(monkeypatch):
    monkeypatch.setattr(settings, "groq_key_1", "fake-groq-key")
    monkeypatch.setattr(settings, "groq_key_2", None)
    monkeypatch.setattr(settings, "gemini_key_1", None)
    monkeypatch.setattr(settings, "openrouter_key_1", "fake-openrouter-key")


def test_get_outreach_email_parses_valid_response(monkeypatch):
    def fake_post(url, *args, **kwargs):
        return _groq_response(
            json.dumps(
                {
                    "subject": "Loved your spot on Test Rd",
                    "body": "Hi there,\n\nI noticed Test Cafe doesn't have a website yet...\n\n[Your Name]",
                }
            )
        )

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_outreach_email(BUSINESS, AUDIT_NO_WEBSITE, VERDICT)

    assert result["error"] is None
    assert result["subject"] == "Loved your spot on Test Rd"
    assert "[Your Name]" in result["body"]


def test_get_outreach_email_sends_text_only_even_with_screenshot(monkeypatch):
    audit_with_screenshot = {**AUDIT_NO_WEBSITE, "error": None, "screenshot_path": "screenshots/fake.png"}
    captured_bodies = []

    def fake_post(url, *args, **kwargs):
        captured_bodies.append(kwargs["json"])
        return _groq_response(json.dumps({"subject": "Hi", "body": "Body text here."}))

    monkeypatch.setattr("httpx.post", fake_post)

    get_outreach_email(BUSINESS, audit_with_screenshot, VERDICT)

    content = captured_bodies[0]["messages"][0]["content"]
    assert isinstance(content, str)  # plain string, no image_url content list


def test_get_outreach_email_retries_once_on_malformed_json(monkeypatch):
    responses = [
        _groq_response("sorry, I can't help with that"),
        _groq_response(json.dumps({"subject": "Second try subject", "body": "Second try body."})),
    ]
    calls = {"count": 0}

    def fake_post(url, *args, **kwargs):
        resp = responses[calls["count"]]
        calls["count"] += 1
        return resp

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_outreach_email(BUSINESS, AUDIT_NO_WEBSITE, VERDICT)

    assert calls["count"] == 2
    assert result == {"subject": "Second try subject", "body": "Second try body.", "error": None}


def test_get_outreach_email_tolerates_raw_newlines_in_body(monkeypatch):
    # Real models frequently emit literal newlines inside the "body" string
    # instead of escaping them as \n, which strict json.loads rejects.
    raw_with_literal_newlines = (
        '{"subject": "Hi from a local dev", "body": "Hi there,\n\n'
        'Loved your spot on Test Rd...\n\n[Your Name]"}'
    )

    def fake_post(url, *args, **kwargs):
        return _groq_response(raw_with_literal_newlines)

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_outreach_email(BUSINESS, AUDIT_NO_WEBSITE, VERDICT)

    assert result["error"] is None
    assert result["subject"] == "Hi from a local dev"
    assert "Loved your spot on Test Rd" in result["body"]


def test_get_outreach_email_tolerates_stray_trailing_brace(monkeypatch):
    # Real models occasionally append a stray extra "}" after the valid
    # JSON object closes — json.loads rejects the whole string as "Extra
    # data"; raw_decode should still find and use the valid part.
    raw_with_trailing_junk = (
        '{"subject": "Hi Mokai Cafe", "body": "Hi there,\n\nQuick note...\n\n[Your Name]"}\n}'
    )

    def fake_post(url, *args, **kwargs):
        return _groq_response(raw_with_trailing_junk)

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_outreach_email(BUSINESS, AUDIT_NO_WEBSITE, VERDICT)

    assert result["error"] is None
    assert result["subject"] == "Hi Mokai Cafe"


def test_get_outreach_email_falls_back_when_both_attempts_malformed(monkeypatch):
    def fake_post(url, *args, **kwargs):
        return _groq_response("not json at all")

    monkeypatch.setattr("httpx.post", fake_post)

    result = get_outreach_email(BUSINESS, AUDIT_NO_WEBSITE, VERDICT)

    assert result["error"] == "outreach_parse_failed"
    assert result["subject"]
    assert result["body"]
