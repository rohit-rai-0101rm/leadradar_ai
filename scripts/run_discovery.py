"""Phase 1 discovery entrypoint: pulls real restaurant data for Bandra, Mumbai.

Run with: uv run python scripts/run_discovery.py
Requires GOOGLE_PLACES_KEY in .env.
"""

from leadradar.tools.places_client import discover_businesses

BANDRA_LAT = 19.0596
BANDRA_LNG = 72.8295
RADIUS_M = 3000
CATEGORY = "restaurant"


def main() -> None:
    businesses = discover_businesses(
        lat=BANDRA_LAT, lng=BANDRA_LNG, radius_m=RADIUS_M, category=CATEGORY
    )

    print(f"Found {len(businesses)} businesses in Bandra, Mumbai\n")

    name_width = max((len(b["name"] or "") for b in businesses), default=4)
    header = f"{'NAME':<{name_width}}  {'WEBSITE':<30}  {'RATING':<6}  PHONE"
    print(header)
    print("-" * len(header))

    for business in businesses:
        website = business["website"] or "NO WEBSITE"
        rating = business["rating"] if business["rating"] is not None else "-"
        phone = business["phone"] or "-"
        print(f"{business['name']:<{name_width}}  {website:<30}  {rating!s:<6}  {phone}")

    no_website_count = sum(1 for b in businesses if not b["website"])
    print(f"\n{no_website_count}/{len(businesses)} businesses have no website")


if __name__ == "__main__":
    main()
