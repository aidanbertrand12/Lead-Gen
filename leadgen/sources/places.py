"""Google Places API (New) text search — the best source for oilfield *service* companies
(fabrication, trucking, welding, rentals, inspection...), which aren't on the BOEM list.

Requires GOOGLE_PLACES_API_KEY. Pricing: Text Search Pro is billed per request;
check https://developers.google.com/maps/billing-and-pricing/pricing before large runs.
"""
from __future__ import annotations

import os
import time

import requests

from ..models import Company

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.websiteUri",
    "places.nationalPhoneNumber", "places.addressComponents", "nextPageToken",
])

GULF_CITIES = [
    # Texas
    "Houston, TX", "Pasadena, TX", "Baytown, TX", "Beaumont, TX", "Port Arthur, TX",
    "Galveston, TX", "Texas City, TX", "Freeport, TX", "Victoria, TX", "Corpus Christi, TX",
    "Brownsville, TX", "Alvin, TX", "Conroe, TX", "Katy, TX",
    # Louisiana
    "Houma, LA", "Lafayette, LA", "New Iberia, LA", "Morgan City, LA", "Lake Charles, LA",
    "Broussard, LA", "Thibodaux, LA", "Galliano, LA", "Port Fourchon, LA", "Harvey, LA",
    "Belle Chasse, LA", "Abbeville, LA", "Youngsville, LA", "Scott, LA",
    # Mississippi / Alabama / Florida panhandle
    "Pascagoula, MS", "Gulfport, MS", "Moss Point, MS", "Mobile, AL", "Theodore, AL",
    "Bayou La Batre, AL", "Pensacola, FL", "Panama City, FL",
]

QUERIES = [
    "oilfield services", "oil and gas company", "offshore services", "oilfield equipment rental",
    "pipeline contractor", "oilfield fabrication", "drilling contractor", "oilfield trucking",
    "well services", "marine offshore supply",
]


def _component(place: dict, kind: str) -> str:
    for comp in place.get("addressComponents", []):
        if kind in comp.get("types", []):
            return comp.get("shortText", "")
    return ""


def search(query: str, api_key: str, max_pages: int = 3) -> list[Company]:
    out, token = [], None
    for _ in range(max_pages):
        body = {"textQuery": query, "pageSize": 20}
        if token:
            body["pageToken"] = token
        resp = requests.post(ENDPOINT, json=body, timeout=30, headers={
            "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELDS,
        })
        resp.raise_for_status()
        data = resp.json()
        for p in data.get("places", []):
            out.append(Company(
                name=p.get("displayName", {}).get("text", ""),
                address=p.get("formattedAddress", ""),
                city=_component(p, "locality"),
                state=_component(p, "administrative_area_level_1"),
                zip=_component(p, "postal_code"),
                phone=p.get("nationalPhoneNumber", ""),
                website=p.get("websiteUri", ""),
                website_source="places" if p.get("websiteUri") else "",
                source="google_places",
                source_id=p.get("id", ""),
            ))
        token = data.get("nextPageToken")
        if not token:
            break
        time.sleep(1)
    return out


def fetch(cities: list[str] | None = None, queries: list[str] | None = None,
          max_pages: int = 3, log=print) -> list[Company]:
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise RuntimeError("Set GOOGLE_PLACES_API_KEY to use the Google Places source.")
    out = []
    for city in cities or GULF_CITIES:
        for q in queries or QUERIES:
            try:
                found = search(f"{q} in {city}", api_key, max_pages)
                log(f"  places: '{q}' in {city}: {len(found)}")
                out.extend(found)
            except requests.HTTPError as e:
                log(f"  places error for '{q}' in {city}: {e}")
    return out
