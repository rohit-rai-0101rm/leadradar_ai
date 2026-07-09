import httpx

from leadradar.core.config import settings

SEARCH_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.websiteUri,places.rating,places.internationalPhoneNumber"
)
MAX_RESULTS_PER_CALL = 20


class PlacesApiError(Exception):
    """Raised when the Places API returns a non-2xx response or an error status."""


def discover_businesses(lat: float, lng: float, radius_m: int, category: str) -> list[dict]:
    if not settings.google_places_key:
        raise PlacesApiError("GOOGLE_PLACES_KEY is not set in .env")

    response = httpx.post(
        SEARCH_NEARBY_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.google_places_key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        json={
            "includedTypes": [category],
            "maxResultCount": MAX_RESULTS_PER_CALL,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius_m,
                }
            },
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise PlacesApiError(
            f"Places API request failed ({response.status_code}): {response.text}"
        )

    places = response.json().get("places", [])
    businesses = [_to_business(place) for place in places]
    return _deduplicate_by_place_id(businesses)


def _to_business(place: dict) -> dict:
    return {
        "place_id": place["id"],
        "name": place.get("displayName", {}).get("text"),
        "address": place.get("formattedAddress"),
        "website": place.get("websiteUri"),
        "rating": place.get("rating"),
        "phone": place.get("internationalPhoneNumber"),
    }


def _deduplicate_by_place_id(businesses: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduplicated = []
    for business in businesses:
        if business["place_id"] in seen:
            continue
        seen.add(business["place_id"])
        deduplicated.append(business)
    return deduplicated
