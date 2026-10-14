"""
Live company knowledge via Aidata Search API.

POST https://aidata.welfog.com/api/search
Headers: Content-Type: application/json, x-api-key: welfog-search-2026
Body: { query, limit?, threshold? }

Returns instruction + context for Gemini.
"""
from __future__ import annotations

from typing import Any

import requests

from config import (
    AIDATA_SEARCH_API_KEY,
    AIDATA_SEARCH_ENABLED,
    AIDATA_SEARCH_TIMEOUT,
    AIDATA_SEARCH_URL,
)


def is_aidata_search_enabled() -> bool:
    return bool(AIDATA_SEARCH_ENABLED and AIDATA_SEARCH_URL and AIDATA_SEARCH_API_KEY)


def search_company_knowledge(
    query: str,
    *,
    limit: int = 5,
    threshold: float | None = None,
) -> dict[str, Any]:
    """
    Call live Aidata search. Normalized:
      ok, found, results, context, instruction, query, error?
    """
    q = (query or "").strip()
    empty: dict[str, Any] = {
        "ok": False,
        "query": q,
        "found": 0,
        "results": [],
        "context": "",
        "instruction": (
            "Use the context below as company knowledge. Prefer these facts over "
            "guessing. If context is insufficient, say you do not have enough "
            "company information."
        ),
        "error": None,
    }
    if not q:
        empty["error"] = "empty_query"
        return empty
    if not is_aidata_search_enabled():
        empty["error"] = "disabled"
        return empty

    lim = max(1, min(20, int(limit or 5)))
    body: dict[str, Any] = {"query": q, "limit": lim}
    if threshold is not None:
        try:
            body["threshold"] = float(threshold)
        except (TypeError, ValueError):
            pass

    try:
        res = requests.post(
            AIDATA_SEARCH_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": AIDATA_SEARCH_API_KEY,
                "Accept": "application/json",
            },
            json=body,
            timeout=AIDATA_SEARCH_TIMEOUT,
        )
        if res.status_code != 200:
            print(f"[aidata] HTTP {res.status_code}")
            empty["error"] = f"http_{res.status_code}"
            return empty
        data = res.json() if res.content else {}
        if not isinstance(data, dict):
            empty["error"] = "bad_json"
            return empty
        results = data.get("results") if isinstance(data.get("results"), list) else []
        found = int(data.get("found") or len(results) or 0)
        compact = []
        for r in results[:lim]:
            if not isinstance(r, dict):
                continue
            compact.append(
                {
                    "title": r.get("title"),
                    "text": (r.get("text") or "")[:600],
                    "score": r.get("score"),
                    "tags": r.get("tags"),
                }
            )
        out = {
            "ok": bool(data.get("ok", True)),
            "query": data.get("query") or q,
            "found": found,
            "results": compact,
            "context": str(data.get("context") or "").strip(),
            "instruction": str(data.get("instruction") or empty["instruction"]).strip(),
            "error": None,
        }
        print(f"[aidata] found={found} query={q[:60]!r}")
        return out
    except Exception as exc:
        print(f"[aidata] failed: {exc}")
        empty["error"] = str(exc)[:200]
        return empty
