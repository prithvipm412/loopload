"""Persistent road distances and map geometries, with offline fallbacks."""
import json
import math
import time
from pathlib import Path
from urllib.request import urlopen

DATA = Path(__file__).resolve().parent
OSRM = "https://router.project-osrm.org"


def _read(name, default):
    try:
        return json.loads((DATA / name).read_text())
    except (OSError, ValueError):
        return default


def _write(name, value):
    target = DATA / name
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(target)


def _request(url):
    with urlopen(url, timeout=8) as response:
        result = json.load(response)
    if result.get('code') != 'Ok':
        raise ValueError('OSRM did not return a route')
    return result


def _coordinates(cities):
    return ';'.join(f"{c['lon']},{c['lat']}" for c in cities)


def _haversine(a, b):
    lat1, lat2 = math.radians(a['lat']), math.radians(b['lat'])
    dlat = lat2 - lat1
    dlon = math.radians(b['lon'] - a['lon'])
    h = math.sin(dlat / 2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon / 2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(1, h))) * 1.3


def get_matrix(cities: list[dict]) -> dict:
    ids = [c['id'] for c in cities]
    cached = _read('matrix.json', {})
    if cached.get('cities') == ids and all(
        len(cached.get(k, [])) == len(ids) and all(len(r) == len(ids) for r in cached[k])
        for k in ('distance_km', 'duration_h')
    ):
        return cached
    try:
        result = _request(f'{OSRM}/table/v1/driving/{_coordinates(cities)}?annotations=distance,duration')
        distances = [[round(v / 1000, 1) for v in row] for row in result['distances']]
        durations = [[round(v / 3600, 3) for v in row] for row in result['durations']]
        if len(distances) != len(ids) or any(len(r) != len(ids) for r in distances + durations):
            raise ValueError('Invalid table dimensions')
        source = 'osrm'
    except Exception:
        distances = [[round(_haversine(a, b), 1) for b in cities] for a in cities]
        durations = [[round(km / 45, 3) for km in row] for row in distances]
        source = 'haversine'
    for i in range(len(ids)):
        distances[i][i] = durations[i][i] = 0
    matrix = dict(cities=ids, distance_km=distances, duration_h=durations, source=source)
    _write('matrix.json', matrix)
    return matrix


def get_path(a: str, b: str) -> list[list[float]]:
    cities = {c['id']: c for c in _read('cities.json', [])}
    endpoints = [cities[a], cities[b]]  # Invalid city codes are caller errors.
    key = f'{a}-{b}'
    cache = _read('paths.json', {})
    if key in cache:
        return cache[key]
    try:
        result = _request(f'{OSRM}/route/v1/driving/{_coordinates(endpoints)}?overview=simplified&geometries=geojson')
        path = result['routes'][0]['geometry']['coordinates']
        if len(path) < 2 or any(len(p) != 2 for p in path):
            raise ValueError('Invalid route geometry')
        if len(path) > 60:
            path = [path[round(i * (len(path) - 1) / 59)] for i in range(60)]
    except Exception:
        path = [[c['lon'], c['lat']] for c in endpoints]
    cache[key] = path
    _write('paths.json', cache)
    return path


def prefetch_paths(pairs):
    """Warm directed OD routes, throttling only actual network requests."""
    for a, b in sorted(set(tuple(pair) for pair in pairs)):
        if f'{a}-{b}' not in _read('paths.json', {}):
            get_path(a, b)
            time.sleep(0.2)
