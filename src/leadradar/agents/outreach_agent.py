from pathlib import Path

from leadradar.agents.json_utils import parse_json_object
from leadradar.agents.providers import build_providers
from leadradar.llm.router import Router, RouterExhaustedError

PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "outreach_email.md"

FALLBACK_OUTREACH = {
    "subject": "Quick note about your website",
    "body": "Could not generate an outreach draft from the LLM.",
    "error": "outreach_parse_failed",
}


def _build_prompt(business: dict, audit_result: dict, verdict: dict) -> str:
    no_website = audit_result.get("error") == "no_website"
    website_status = "No website at all." if no_website else f"Has a website: {business.get('website')}"

    template = PROMPT_TEMPLATE_PATH.read_text()
    return (
        template.replace("{{business_name}}", str(business.get("name")))
        .replace("{{address}}", str(business.get("address")))
        .replace("{{website_status}}", website_status)
        .replace("{{reasoning}}", str(verdict.get("reasoning")))
    )


def _parse_outreach(raw: str) -> dict | None:
    data = parse_json_object(raw)
    if data is None:
        return None

    subject = data.get("subject")
    body = data.get("body")
    if not isinstance(subject, str) or not subject.strip():
        return None
    if not isinstance(body, str) or not body.strip():
        return None

    return {"subject": subject, "body": body}


def get_outreach_email(business: dict, audit_result: dict, verdict: dict) -> dict:
    providers = build_providers()
    if not providers:
        return {
            "subject": FALLBACK_OUTREACH["subject"],
            "body": "No LLM provider configured.",
            "error": "no_provider",
        }

    router = Router(providers=providers)
    prompt = _build_prompt(business, audit_result, verdict)

    for _attempt in range(2):
        try:
            raw = router.complete(prompt)
        except RouterExhaustedError as exc:
            return {
                "subject": FALLBACK_OUTREACH["subject"],
                "body": f"LLM router exhausted: {exc}",
                "error": "router_exhausted",
            }

        parsed = _parse_outreach(raw)
        if parsed is not None:
            return {**parsed, "error": None}

    return dict(FALLBACK_OUTREACH)
