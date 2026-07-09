import json

# strict=False tolerates raw control characters (e.g. literal newlines)
# inside string values — LLMs frequently emit actual line breaks in
# multi-line fields instead of escaping them as \n, which strict JSON
# parsing would otherwise reject outright.
_DECODER = json.JSONDecoder(strict=False)


def parse_json_object(raw: str) -> dict | None:
    """Extracts a JSON object from raw LLM output, tolerating markdown code
    fences, chatty prose before/after the JSON, and stray trailing
    characters some models append after a valid object. Returns None if no
    valid JSON object could be found.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    start = text.find("{")
    if start == -1:
        return None

    try:
        # raw_decode parses one JSON value starting at index 0 of the
        # slice and ignores anything trailing it, unlike json.loads which
        # rejects the whole string if there's extra data after the value.
        data, _ = _DECODER.raw_decode(text[start:])
    except json.JSONDecodeError:
        return None

    return data if isinstance(data, dict) else None
