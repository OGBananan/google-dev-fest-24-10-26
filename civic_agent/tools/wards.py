"""TOOLBOX — ward and department routing.

Nearest ward centroid from wards.json. No live Geocoding call: one less
network dependency in the room, and accurate enough at ward scale.
"""

from math import asin, cos, radians, sin, sqrt

from ..data import load


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def find_ward(
    issue_type: str,
    lat: float = None,
    lng: float = None,
    area_name: str = None,
) -> dict:
    """Find the AMC ward and responsible department for a location.

    Prefers coordinates. Falls back to matching a typed area name.

    Args:
        issue_type: pothole, garbage, streetlight, waterlogging or other.
        lat: Latitude from the browser, if available.
        lng: Longitude from the browser, if available.
        area_name: Area name typed by the user, if no coordinates.

    Returns:
        ward_id, ward_name, zone, department and how the ward was resolved.
    """
    db = load()
    wards = db["wards"]
    department = db["departments"].get(issue_type, "General Complaints")

    ward = None
    resolved_by = None

    if lat is not None and lng is not None:
        ward = min(wards, key=lambda w: _haversine_km(lat, lng, w["lat"], w["lng"]))
        resolved_by = "coordinates"
    elif area_name:
        needle = area_name.strip().lower()
        for w in wards:
            names = [w["name"]] + w.get("areas", [])
            if any(needle in n.lower() or n.lower() in needle for n in names):
                ward = w
                resolved_by = "area name"
                break

    if ward is None:
        return {
            "error": "could not resolve a ward",
            "hint": "ask the user which area of Ahmedabad this is in",
            "known_areas": sorted({a for w in wards for a in w.get("areas", [])}),
        }

    return {
        "ward_id": ward["id"],
        "ward_name": ward["name"],
        "zone": ward["zone"],
        "department": department,
        "resolved_by": resolved_by,
    }
