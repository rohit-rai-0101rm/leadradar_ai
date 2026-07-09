"""Phase 1 discovery + audit + verdict entrypoint: pulls real restaurant
data for Bandra, Mumbai, audits each business's website, and gets an LLM
verdict on whether it needs a redesign.

Run with: uv run python scripts/run_discovery.py
Requires GOOGLE_PLACES_KEY in .env, plus at least one LLM provider key.
"""

from leadradar.agents.verdict import get_verdict
from leadradar.tools.places_client import discover_businesses
from leadradar.tools.web_audit import audit_website

BANDRA_LAT = 19.0596
BANDRA_LNG = 72.8295
RADIUS_M = 3000
CATEGORY = "restaurant"

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


def main() -> None:
    businesses = discover_businesses(
        lat=BANDRA_LAT, lng=BANDRA_LNG, radius_m=RADIUS_M, category=CATEGORY
    )

    print(f"Found {len(businesses)} businesses in Bandra, Mumbai — auditing websites...\n")
    audit_businesses(businesses)

    print("Getting LLM verdicts...\n")
    verdict_businesses(businesses)

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


if __name__ == "__main__":
    main()
