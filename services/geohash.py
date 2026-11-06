BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def encode_geohash(lat: float, lng: float, precision: int = 9) -> str:
    min_lat, max_lat = -90.0, 90.0
    min_lng, max_lng = -180.0, 180.0
    hash_value = ""
    bit = 0
    ch = 0
    is_lng = True

    while len(hash_value) < precision:
        if is_lng:
            mid = (min_lng + max_lng) / 2
            if lng >= mid:
                ch |= 1 << (4 - bit)
                min_lng = mid
            else:
                max_lng = mid
        else:
            mid = (min_lat + max_lat) / 2
            if lat >= mid:
                ch |= 1 << (4 - bit)
                min_lat = mid
            else:
                max_lat = mid

        is_lng = not is_lng
        if bit < 4:
            bit += 1
        else:
            hash_value += BASE32[ch]
            bit = 0
            ch = 0

    return hash_value


def haversine_distance_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    d_lat = radians(b_lat - a_lat)
    d_lng = radians(b_lng - a_lng)
    lat1 = radians(a_lat)
    lat2 = radians(b_lat)
    h = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lng / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))
