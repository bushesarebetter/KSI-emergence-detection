"""A small Overpass client shared by the scripts that fetch OpenStreetMap data
around exported intersections.

Public mirrors are tried in turn with backoff. On 2026-09-17 overpass-api.de
answered every interpreter request from this network with 406 or a connect
timeout, so it is last; the other two answered a 20-point way query in two to
three minutes under load, which is why callers batch points per request.
"""
from __future__ import annotations

import time

import requests

ENDPOINTS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
RETRY_WAITS_S = (0, 10, 30, 60)
HTTP_TIMEOUT = (30, 600)  # connect, read: queries queue for minutes under load
USER_AGENT = "KSI-emergence-detection (+https://github.com/bushesarebetter/KSI-emergence-detection)"


def fetch(query: str, endpoints=ENDPOINTS, waits=RETRY_WAITS_S):
    """POST an Overpass QL query. Returns (json, None) or (None, last_error)."""
    err: Exception | None = None
    for attempt, wait in enumerate(waits):
        if wait:
            time.sleep(wait)
        url = endpoints[attempt % len(endpoints)]
        try:
            r = requests.post(url, data={"data": query}, timeout=HTTP_TIMEOUT,
                              headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            data = r.json()
            remark = data.get("remark") or ""
            if "error" in remark.lower():
                raise RuntimeError(remark)
            return data, None
        except Exception as exc:  # timeouts, 429/504, malformed JSON
            err = exc
    return None, err


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]
