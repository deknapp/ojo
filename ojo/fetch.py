"""HTTP with a cache, because the upstreams are volunteer-run or fragile.

Every remote call in this project goes through here and lands in `.cache/`.
That is not a performance decision. It means a build is reproducible from a
checkout without hammering Overpass, and it means the exact bytes a claim was
derived from are still on disk when someone asks where a number came from.
"""

from __future__ import annotations

import hashlib
import json
import re
import logging
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .config import CACHE_DIR, NOMINATIM_DELAY_S, NOMINATIM_URL, OVERPASS_URL, USER_AGENT

log = logging.getLogger(__name__)

_last_nominatim_call = 0.0


def _cache_path(kind: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return CACHE_DIR / kind / f"{digest}.json"


def cached_json(kind: str, key: str, produce) -> dict | list:
    """Return cached JSON for `key`, calling `produce()` on a miss."""
    path = _cache_path(kind, key)
    if path.exists():
        return json.loads(path.read_text())
    value = produce()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def get(url: str, data: dict | None = None, timeout: int = 180) -> bytes:
    body = urllib.parse.urlencode(data).encode() if data else None
    request = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def overpass_slot_wait() -> int:
    """Seconds until the public instance will accept another query.

    Overpass publishes its own rate limiter at /api/status. Reading it and
    waiting the stated time is enormously better behaved than retrying into a
    429, and it is the difference between a build that finishes and a build
    that gets the IP throttled.
    """
    try:
        status = get(OVERPASS_URL.replace("/interpreter", "/status"), timeout=30).decode()
    except Exception:  # noqa: BLE001 - status is advisory; fall back to a fixed wait
        return 30
    if "slots available now" in status:
        return 0
    waits = [int(m) for m in re.findall(r"in (\d+) seconds", status)]
    return min(waits) + 2 if waits else 30


def overpass(query: str, *, retries: int = 4) -> dict:
    """Run an Overpass QL query.

    Retries exist because the public instance returns 504 under load often
    enough that a single failure would make builds flaky, and a flaky build
    tempts people to skip the data refresh. Between attempts it asks the
    instance when it would like to be called back, rather than guessing.
    """

    def produce() -> dict:
        last: Exception | None = None
        for attempt in range(retries):
            try:
                return json.loads(get(OVERPASS_URL, {"data": query}))
            except Exception as exc:  # noqa: BLE001 - retried and re-raised below
                last = exc
                wait = max(overpass_slot_wait(), 10 * (attempt + 1))
                log.warning("overpass attempt %d failed (%s); waiting %ds", attempt + 1, exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"overpass failed after {retries} attempts") from last

    return cached_json("overpass", query, produce)  # type: ignore[return-value]


def geocode(query: str) -> tuple[float, float] | None:
    """Geocode one free-text address. Returns None when nothing matches.

    The caller is expected to snap the result onto a named road afterwards:
    Nominatim will happily return `Old Airport Road` for `7500 Airport Road`,
    which is a real street half a kilometre away from the intended one.
    """

    def produce() -> list:
        global _last_nominatim_call
        elapsed = time.monotonic() - _last_nominatim_call
        if elapsed < NOMINATIM_DELAY_S:
            time.sleep(NOMINATIM_DELAY_S - elapsed)
        _last_nominatim_call = time.monotonic()
        url = f"{NOMINATIM_URL}?{urllib.parse.urlencode({'format': 'json', 'limit': 1, 'q': query})}"
        return json.loads(get(url, timeout=60))

    results = cached_json("nominatim", query, produce)
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])
