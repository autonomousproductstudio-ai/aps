"""_reddit — shared Reddit access. Not a tool (leading underscore → registry skips it).

Uses an OAuth app token when REDDIT_CLIENT_ID/SECRET are set (higher, compliant
quota); otherwise falls back to the public .json endpoints with a descriptive
User-Agent. Either way callers get parsed JSON or raise.
"""
from __future__ import annotations

import os

from aps.tools.base import USER_AGENT, DEFAULT_TIMEOUT

_token_cache: dict[str, str] = {}


def _get_token() -> str | None:
    cid = os.getenv("REDDIT_CLIENT_ID")
    secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return None
    if "t" in _token_cache:
        return _token_cache["t"]
    from aps.infra import http
    resp = http.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(cid, secret),
        headers={"User-Agent": USER_AGENT},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    tok = resp.json().get("access_token")
    if tok:
        _token_cache["t"] = tok
    return tok


def reddit_get(path: str, params: dict) -> dict:
    """GET a Reddit endpoint. `path` like '/search' or '/r/python/top'.

    Returns parsed JSON. Raises on network/HTTP error (caller falls back to fixture).
    """
    from aps.infra import http
    token = _get_token()
    if token:
        base = "https://oauth.reddit.com"
        headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"}
    else:
        base = "https://www.reddit.com"
        headers = {"User-Agent": USER_AGENT}
    url = f"{base}{path}.json" if not path.endswith(".json") else f"{base}{path}"
    r = http.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    return r.json()


def posts_to_evidence(data: dict, limit: int):
    """Map a Reddit listing JSON into Evidence objects."""
    from aps.state.models import Evidence
    children = (data.get("data", {}) or {}).get("children", []) or []
    out = []
    for c in children[:limit]:
        d = c.get("data", {})
        body = d.get("selftext") or d.get("body") or ""
        meta = f"{d.get('score', 0)} pts, {d.get('num_comments', 0)} comments"
        out.append(Evidence(
            source="reddit",
            url="https://www.reddit.com" + (d.get("permalink") or ""),
            title=d.get("title") or f"r/{d.get('subreddit', '')} comment",
            snippet=(body or meta)[:280],
        ))
    return out
