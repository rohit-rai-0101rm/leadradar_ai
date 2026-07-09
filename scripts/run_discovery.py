"""Phase 1 full pipeline entrypoint: discovers real restaurants in Bandra,
Mumbai, audits each website, gets an LLM verdict, scores each business as
a lead, and writes the results to output/leads_{timestamp}.json.

Run with: uv run python scripts/run_discovery.py
Requires GOOGLE_PLACES_KEY in .env, plus at least one LLM provider key.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from leadradar.agents.verdict import get_verdict
from leadradar.tools.places_client import discover_businesses
from leadradar.tools.scoring_rules import score_lead
from leadradar.tools.web_audit import audit_website

BANDRA_LAT = 19.0596
BANDRA_LNG = 72.8295
RADIUS_M = 3000
CATEGORY = "restaurant"

OUTPUT_DIR = Path("output")

NO_WEBSITE_AUDIT = {
    "loaded": False,
    "load_time_ms": None,
    "has_ssl": False,
    "has_mobile_viewport": False,
    "screenshot_path": None,
    "error": "no_website",
}


def audit_businesses(businesses: list[dict]) -> None:
    for business in businesses:
        if business["website"]:
            business["audit"] = audit_website(business["website"], name=business["name"])
        else:
            business["audit"] = dict(NO_WEBSITE_AUDIT)


def verdict_businesses(businesses: list[dict]) -> None:
    for business in businesses:
        business["verdict"] = get_verdict(business, business["audit"])


def score_businesses(businesses: list[dict]) -> None:
    for business in businesses:
        business["scoring"] = score_lead(business, business["audit"], business["verdict"])


def write_output_json(businesses: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"leads_{timestamp}.json"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "businesses": businesses,
    }
    output_path.write_text(json.dumps(payload, indent=2))
    return output_path


def main() -> None:
    businesses = discover_businesses(
        lat=BANDRA_LAT, lng=BANDRA_LNG, radius_m=RADIUS_M, category=CATEGORY
    )

    print(f"Found {len(businesses)} businesses in Bandra, Mumbai — auditing websites...\n")
    audit_businesses(businesses)

    print("Getting LLM verdicts...\n")
    verdict_businesses(businesses)

    score_businesses(businesses)
    businesses.sort(key=lambda b: b["scoring"]["score"], reverse=True)

    name_width = max((len(b["name"] or "") for b in businesses), default=4)
    header = (
        f"{'NAME':<{name_width}}  {'WEBSITE':<30}  {'LOADED':<6}  {'SSL':<5}  "
        f"{'REDESIGN?':<9}  {'RATING':<6}  PHONE"
    )
    print(header)
    print("-" * len(header))

    for business in businesses:
        website = business["website"] or "NO WEBSITE"
        audit = business["audit"]
        loaded = "yes" if audit["loaded"] else "no"
        ssl = "yes" if audit["has_ssl"] else "no"
        redesign = "yes" if business["verdict"]["needs_redesign"] else "no"
        rating = business["rating"] if business["rating"] is not None else "-"
        phone = business["phone"] or "-"
        print(
            f"{business['name']:<{name_width}}  {website:<30}  {loaded:<6}  {ssl:<5}  "
            f"{redesign:<9}  {rating!s:<6}  {phone}"
        )

    no_website_count = sum(1 for b in businesses if not b["website"])
    failed_to_load_count = sum(
        1 for b in businesses if b["website"] and not b["audit"]["loaded"]
    )
    needs_redesign_count = sum(1 for b in businesses if b["verdict"]["needs_redesign"])
    print(f"\n{no_website_count}/{len(businesses)} businesses have no website")
    print(f"{failed_to_load_count}/{len(businesses)} businesses have a website that failed to load")
    print(f"{needs_redesign_count}/{len(businesses)} businesses flagged as needing a redesign")

    print("\nVerdict details:")
    for business in businesses:
        verdict = business["verdict"]
        flag = "NEEDS REDESIGN" if verdict["needs_redesign"] else "looks fine"
        print(f"- {business['name']} [{flag}]: {verdict['reasoning']}")

    print("\nLead summary (sorted by score, worst websites first):")
    summary_header = f"{'NAME':<{name_width}}  {'BUCKET':<6}  {'SCORE':<5}  NEEDS_REDESIGN?"
    print(summary_header)
    print("-" * len(summary_header))
    for business in businesses:
        scoring = business["scoring"]
        redesign = "yes" if business["verdict"]["needs_redesign"] else "no"
        print(
            f"{business['name']:<{name_width}}  {scoring['bucket']:<6}  "
            f"{scoring['score']:<5}  {redesign}"
        )

    output_path = write_output_json(businesses)
    print(f"\nWrote {len(businesses)} leads to {output_path}")


if __name__ == "__main__":
    main()
