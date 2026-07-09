import pytest

from leadradar.core.config import settings
from leadradar.tools.places_client import PlacesApiError, discover_businesses

# Shaped like the real Places API (New) searchNearby response captured live
# against Bandra, Mumbai. One place ("Mokai Cafe Chapel Road") intentionally
# has no websiteUri, matching what we saw for real.
FAKE_PLACES_RESPONSE = {
    "places": [
        {
            "id": "ChIJO6enasHJ5zsRO69nxUQXoBE",
            "internationalPhoneNumber": "+91 90049 88941",
            "formattedAddress": "Shop no. 1, Bandra West, Mumbai",
            "rating": 4.3,
            "websiteUri": "https://benne.in/",
            "displayName": {"text": "Benne - Heritage Bangalore Dosa", "languageCode": "en"},
        },
        {
            "id": "ChIJd-G2HwDJ5zsRTrJrA_ESL6U",
            "internationalPhoneNumber": "+91 98209 83607",
            "formattedAddress": "600 hill crest Building, Bandra West, Mumbai",
            "rating": 4.3,
            "displayName": {"text": "Mokai Cafe Chapel Road", "languageCode": "en"},
        },
    ]
}


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self) -> dict:
        return self._json_data


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(settings, "google_places_key", "fake-key-for-tests")


def test_discover_businesses_maps_fields_and_handles_missing_website(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResponse(200, FAKE_PLACES_RESPONSE))

    businesses = discover_businesses(lat=19.0596, lng=72.8295, radius_m=3000, category="restaurant")

    assert len(businesses) == 2
    assert businesses[0] == {
        "place_id": "ChIJO6enasHJ5zsRO69nxUQXoBE",
        "name": "Benne - Heritage Bangalore Dosa",
        "address": "Shop no. 1, Bandra West, Mumbai",
        "website": "https://benne.in/",
        "rating": 4.3,
        "phone": "+91 90049 88941",
    }
    assert businesses[1]["name"] == "Mokai Cafe Chapel Road"
    assert businesses[1]["website"] is None


def test_discover_businesses_deduplicates_by_place_id(monkeypatch):
    duplicated_response = {"places": FAKE_PLACES_RESPONSE["places"] + [FAKE_PLACES_RESPONSE["places"][0]]}
    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResponse(200, duplicated_response))

    businesses = discover_businesses(lat=19.0596, lng=72.8295, radius_m=3000, category="restaurant")

    assert len(businesses) == 2
    place_ids = [b["place_id"] for b in businesses]
    assert len(place_ids) == len(set(place_ids))


def test_discover_businesses_raises_on_api_error(monkeypatch):
    monkeypatch.setattr(
        "httpx.post", lambda *a, **k: FakeResponse(400, {}, text="invalid request")
    )

    with pytest.raises(PlacesApiError):
        discover_businesses(lat=19.0596, lng=72.8295, radius_m=3000, category="restaurant")


def test_discover_businesses_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr(settings, "google_places_key", None)

    with pytest.raises(PlacesApiError):
        discover_businesses(lat=19.0596, lng=72.8295, radius_m=3000, category="restaurant")
