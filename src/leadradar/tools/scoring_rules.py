LOW_RATING_THRESHOLD = 4.0
SLOW_LOAD_MS_THRESHOLD = 3000

HOT_THRESHOLD = 70
WARM_THRESHOLD = 40


def score_lead(business: dict, audit_result: dict, verdict: dict) -> dict:
    score = 0

    no_website = audit_result.get("error") == "no_website" or not business.get("website")
    if no_website:
        score += 40

    if verdict.get("needs_redesign"):
        score += 30

    rating = business.get("rating")
    if rating is not None and rating < LOW_RATING_THRESHOLD:
        score += 10

    if not audit_result.get("has_ssl"):
        score += 10

    load_time_ms = audit_result.get("load_time_ms")
    if load_time_ms is not None and load_time_ms > SLOW_LOAD_MS_THRESHOLD:
        score += 10

    if score >= HOT_THRESHOLD:
        bucket = "HOT"
    elif score >= WARM_THRESHOLD:
        bucket = "WARM"
    else:
        bucket = "COLD"

    return {"score": score, "bucket": bucket}
