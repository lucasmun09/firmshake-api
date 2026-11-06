import math

from config import ARRIVAL_RADIUS_METERS, ETA_SPEED_MPH

METERS_PER_MILE = 1609.34
METERS_PER_MINUTE_AT_ETA_SPEED = (ETA_SPEED_MPH * METERS_PER_MILE) / 60


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def calculate_eta(distance_meters: float) -> tuple[int, int]:
    """Return (eta_minutes, progress_percent) toward the meetup point."""
    if distance_meters <= ARRIVAL_RADIUS_METERS:
        return 0, 100

    eta_minutes = max(1, int(math.ceil(distance_meters / METERS_PER_MINUTE_AT_ETA_SPEED)))

    # Progress scales from 0% at 10km+ to 100% at arrival radius
    max_range = 10_000
    progress = int(
        max(
            0,
            min(
                100,
                100 * (1 - (distance_meters - ARRIVAL_RADIUS_METERS) / max_range),
            ),
        )
    )

    return eta_minutes, progress


def eta_from_coordinates(
    user_lat: float,
    user_lng: float,
    meetup_lat: float,
    meetup_lng: float,
) -> tuple[int, int, float]:
    distance = _haversine_meters(user_lat, user_lng, meetup_lat, meetup_lng)
    eta_minutes, progress = calculate_eta(distance)
    return eta_minutes, progress, distance
