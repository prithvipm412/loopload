#!/usr/bin/env bash
# Restore current-week inputs via the API; preserve the committed offline caches.
set -euo pipefail

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [http://localhost:8000]" >&2
  exit 1
fi
api_origin="${1:-${LOOPLOAD_API_URL:-http://localhost:8000}}"
if [ -n "${PYTHON:-}" ]; then
  python_bin="$PYTHON"
elif command -v python3.12 >/dev/null 2>&1; then
  python_bin=python3.12
else
  python_bin=python3
fi

"$python_bin" - "$api_origin" <<'PY'
import json
import math
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

origin = sys.argv[1].rstrip('/')


def request(method, path, body=None):
    encoded = json.dumps(body).encode() if body is not None else None
    req = Request(origin + path, data=encoded, method=method,
                  headers={'Content-Type':'application/json','Accept':'application/json'})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f'{path}: expected 200, got {response.status}')
        return json.load(response)


try:
    if urlsplit(origin).scheme not in ('http','https') or not urlsplit(origin).netloc:
        raise ValueError('API origin must be an HTTP(S) URL')
    timeout = float(os.environ.get('LOOPLOAD_TIMEOUT', '180'))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('LOOPLOAD_TIMEOUT must be a positive number of seconds')
    # Create a known cache entry so cache invalidation is verified, not assumed.
    prior = request('POST', '/api/plan', {'mode':'baseline'})
    old_id = prior['plan_id']
    restored = request('POST', '/api/scenario/regenerate', {'seed':42,'n_trucks':20,'n_loads':140})
    if len(restored['trucks']) != 20 or len(restored['loads']) != 140:
        raise ValueError('Regeneration did not return 20 trucks and 140 loads')
    if restored['week_start'] != '2026-11-09T00:00:00+05:30':
        raise ValueError('Regeneration returned the wrong demo week')
    try:
        request('GET', '/api/plan/' + quote(old_id, safe=''))
    except HTTPError as error:
        if error.code not in (404,410):
            raise
    else:
        raise ValueError('Regeneration kept a stale plan. The API owner must invalidate all plan/compare caches in /api/scenario/regenerate')
    print(f'Demo reset at {origin}: seed 42, 20 trucks, 140 loads; pre-reset plan invalidated.')
    print('Offline matrix, road paths, and forecast caches preserved.')
except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError) as error:
    print(f'Demo reset FAILED: {error}', file=sys.stderr)
    sys.exit(1)
PY
