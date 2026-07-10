"""Full pipeline entrypoint: discovers real businesses of a given category in
a given area, audits each website, gets an LLM verdict, scores each business
as a lead, generates outreach email drafts for HOT/WARM leads, and writes
the results to output/leads_{category}_{location}_{timestamp}.json.

Run with:
  uv run python scripts/run_discovery.py --category beauty_salon \
      --lat 19.1358 --lng 72.8262 --location-name "Andheri West, Mumbai"

All flags are optional and default to restaurants in Bandra, Mumbai.
Category must be a valid Google Places "Table A" type
(https://developers.google.com/maps/documentation/places/web-service/place-types).
Requires GOOGLE_PLACES_KEY in .env, plus at least one LLM provider key.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from leadradar.agents.outreach_agent import get_outreach_email
from leadradar.agents.verdict import get_verdict
from leadradar.tools.places_client import discover_businesses
from leadradar.tools.scoring_rules import score_lead
from leadradar.tools.web_audit import audit_website

DEFAULT_LAT = 19.0596
DEFAULT_LNG = 72.8295
DEFAULT_RADIUS_M = 3000
DEFAULT_CATEGORY = "restaurant"
DEFAULT_LOCATION_NAME = "Bandra, Mumbai"

OUTPUT_DIR = Path("output")
OUTREACH_BUCKETS = ("HOT", "WARM")

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


def outreach_businesses(businesses: list[dict]) -> None:
    for business in businesses:
        if business["scoring"]["bucket"] in OUTREACH_BUCKETS:
            business["outreach"] = get_outreach_email(
                business, business["audit"], business["verdict"]
            )
        else:
            business["outreach"] = None


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def write_output_json(businesses: list[dict], category: str, location_name: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = (
        OUTPUT_DIR / f"leads_{_slugify(category)}_{_slugify(location_name)}_{timestamp}.json"
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "location_name": location_name,
        "businesses": businesses,
    }
    output_path.write_text(json.dumps(payload, indent=2))
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help=f"Google Places 'Table A' type to search for (default: {DEFAULT_CATEGORY})",
    )
    parser.add_argument(
        "--lat", type=float, default=DEFAULT_LAT, help=f"Latitude (default: {DEFAULT_LAT})"
    )
    parser.add_argument(
        "--lng", type=float, default=DEFAULT_LNG, help=f"Longitude (default: {DEFAULT_LNG})"
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=DEFAULT_RADIUS_M,
        help=f"Search radius in meters (default: {DEFAULT_RADIUS_M})",
    )
    parser.add_argument(
        "--location-name",
        default=DEFAULT_LOCATION_NAME,
        help=f"Human-readable area label for output/console (default: {DEFAULT_LOCATION_NAME!r})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    category = args.category
    location_name = args.location_name

    businesses = discover_businesses(
        lat=args.lat, lng=args.lng, radius_m=args.radius, category=category
    )

    print(f"Found {len(businesses)} {category} businesses in {location_name} — auditing websites...\n")
    audit_businesses(businesses)

    print("Getting LLM verdicts...\n")
    verdict_businesses(businesses)

    score_businesses(businesses)
    businesses.sort(key=lambda b: b["scoring"]["score"], reverse=True)

    print("Generating outreach drafts for HOT/WARM leads...\n")
    outreach_businesses(businesses)

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
    outreach_count = sum(1 for b in businesses if b["outreach"] is not None)
    print(f"\n{no_website_count}/{len(businesses)} businesses have no website")
    print(f"{failed_to_load_count}/{len(businesses)} businesses have a website that failed to load")
    print(f"{needs_redesign_count}/{len(businesses)} businesses flagged as needing a redesign")
    print(f"{outreach_count}/{len(businesses)} outreach drafts generated (HOT/WARM leads only)")

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

    print("\nOutreach drafts (full bodies saved in the JSON output):")
    for business in businesses:
        if business["outreach"] is not None:
            print(f"- {business['name']}: \"{business['outreach']['subject']}\"")

    output_path = write_output_json(businesses, category, location_name)
    print(f"\nWrote {len(businesses)} leads to {output_path}")


if __name__ == "__main__":
    main()
