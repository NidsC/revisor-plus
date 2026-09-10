"""Tiny Postcodes.io client using only the Python standard library."""

from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://api.postcodes.io"
POSTCODE_RE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$", re.I)


class PostcodeLookupError(Exception):
    pass


def normalise_postcode(value: str) -> str:
    compact = re.sub(r"\s+", "", (value or "").upper())
    if len(compact) <= 3:
        return compact
    return f"{compact[:-3]} {compact[-3:]}"


def looks_like_postcode(value: str) -> bool:
    return bool(POSTCODE_RE.match((value or "").strip()))


def _request_json(url: str, *, data: dict | None = None, timeout: float = 4.0):
    body = None
    headers = {"Accept": "application/json", "User-Agent": "RevisorPlus/1.0"}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise PostcodeLookupError("That postcode could not be found.") from exc
        raise PostcodeLookupError("Postcode lookup is temporarily unavailable.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PostcodeLookupError("Postcode lookup is temporarily unavailable.") from exc


def lookup_postcode(postcode: str) -> dict:
    postcode = normalise_postcode(postcode)
    if not looks_like_postcode(postcode):
        raise PostcodeLookupError("Enter a full UK postcode, for example SW1A 1AA.")

    payload = _request_json(f"{BASE_URL}/postcodes/{quote(postcode)}")
    result = payload.get("result") or {}
    if not result:
        raise PostcodeLookupError("That postcode could not be found.")
    return result


def bulk_lookup(postcodes: list[str]) -> dict[str, dict]:
    cleaned = []
    seen = set()
    for value in postcodes:
        normalised = normalise_postcode(value)
        if normalised and normalised not in seen:
            cleaned.append(normalised)
            seen.add(normalised)

    if not cleaned:
        return {}

    # Postcodes.io accepts up to 100 postcodes per bulk request. Our search API
    # returns at most 30, so one request is enough.
    payload = _request_json(f"{BASE_URL}/postcodes", data={"postcodes": cleaned[:100]})
    output = {}
    for item in payload.get("result") or []:
        query = normalise_postcode(item.get("query") or "")
        result = item.get("result")
        if query and result:
            output[query] = result
    return output
