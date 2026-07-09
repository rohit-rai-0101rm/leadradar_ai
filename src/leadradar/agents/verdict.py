import base64
from pathlib import Path

from leadradar.agents.json_utils import parse_json_object
from leadradar.agents.providers import build_providers
from leadradar.llm.router import Router, RouterExhaustedError

FALLBACK_VERDICT = {
    "needs_redesign": True,
    "reasoning": "Could not get a verdict from the LLM.",
    "error": "verdict_parse_failed",
}


def _build_prompt(business: dict, audit_result: dict) -> str:
    no_website = audit_result.get("error") == "no_website"
    signal_lines = [
        f"Business: {business.get('name')}",
        f"no_website: {no_website}",
        f"loaded: {audit_result.get('loaded')}",
        f"load_time_ms: {audit_result.get('load_time_ms')}",
        f"has_ssl: {audit_result.get('has_ssl')}",
        f"has_mobile_viewport: {audit_result.get('has_mobile_viewport')}",
    ]
    if audit_result.get("error") and not no_website:
        signal_lines.append(f"error: {audit_result['error']}")

    return (
        "You are evaluating a local business's digital presence for a lead-generation tool.\n"
        + "\n".join(signal_lines)
        + "\n\nIf a screenshot is attached, use it to judge the site's visual quality. "
        "Respond with STRICT JSON only, no markdown, no extra text, in exactly this shape:\n"
        '{"needs_redesign": true or false, "reasoning": "2-3 sentences explaining why"}'
    )


def _parse_verdict(raw: str) -> dict | None:
    data = parse_json_object(raw)
    if data is None:
        return None

    needs_redesign = data.get("needs_redesign")
    reasoning = data.get("reasoning")
    if not isinstance(needs_redesign, bool) or not isinstance(reasoning, str) or not reasoning.strip():
        return None

    return {"needs_redesign": needs_redesign, "reasoning": reasoning}


def get_verdict(business: dict, audit_result: dict) -> dict:
    providers = build_providers()
    if not providers:
        return {
            "needs_redesign": True,
            "reasoning": "No LLM provider configured.",
            "error": "no_provider",
        }

    router = Router(providers=providers)
    prompt = _build_prompt(business, audit_result)

    image_base64 = None
    screenshot_path = audit_result.get("screenshot_path")
    if screenshot_path:
        image_base64 = base64.b64encode(Path(screenshot_path).read_bytes()).decode()

    for _attempt in range(2):
        try:
            raw = router.complete(prompt, image_base64=image_base64)
        except RouterExhaustedError as exc:
            return {
                "needs_redesign": True,
                "reasoning": f"LLM router exhausted: {exc}",
                "error": "router_exhausted",
            }

        parsed = _parse_verdict(raw)
        if parsed is not None:
            return {**parsed, "error": None}

    return dict(FALLBACK_VERDICT)
