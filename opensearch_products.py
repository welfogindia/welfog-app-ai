"""Direct OpenSearch catalog search (products_v1) — same index the website uses."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from config import (
    OPENSEARCH_BASE,
    OPENSEARCH_INDEX,
    OPENSEARCH_PASSWORD,
    OPENSEARCH_SIZE,
    OPENSEARCH_TIMEOUT,
    OPENSEARCH_USER,
)

# Primary product-type match — color/size intentionally excluded so a lone
# color hit (e.g. red ball) cannot outrank the real product type (t-shirt).
# NOTE: pro_features is object+enabled:false in OpenSearch — not searchable;
# we parse it from _source for UI filters + client-side filtering.
_PRODUCT_FIELDS = [
    "name^6",
    "slug^3",
    "sku^2",
    "category_name^4",
    "brand^2",
]

# Secondary full-phrase ranking (includes color_name / size in text scoring)
_PHRASE_FIELDS = [
    "name^3",
    "slug^2",
    "sku",
    "category_name^2",
    "brand",
    "color_name",
    "size",
]

# Skip noisy / empty feature values when building filter chips
_SKIP_FEATURE_VALUES = frozenset(
    {
        "",
        "-",
        "n/a",
        "na",
        "none",
        "null",
        "others",
        "other",
        "no brand",
        "not specified",
        "not applicable",
        "no theme",
        "na.",
        "nil",
        "unknown",
    }
)


def _token_variants(token: str) -> set[str]:
    """Light stemming only (hoodies↔hoodie) — no word dictionaries."""
    t = (token or "").lower().strip()
    if not t:
        return set()
    out = {t}
    if t.endswith("ies") and len(t) > 4:
        out.add(t[:-3] + "y")
        out.add(t[:-1])
    elif t.endswith("es") and len(t) > 3:
        out.add(t[:-2])
        out.add(t[:-1])
    elif t.endswith("s") and len(t) > 3:
        out.add(t[:-1])
    else:
        out.add(t + "s")
        out.add(t + "es")
    return out


def _query_tokens(query: str) -> list[str]:
    """Significant query tokens by length only — AI forms meaning, no stopword lists."""
    toks = re.findall(r"[a-z0-9]+", (query or "").lower())
    long = [t for t in toks if len(t) >= 4]
    if long:
        return long
    return [t for t in toks if len(t) >= 3]


def parse_pro_features(raw: Any) -> dict[str, str]:
    """Parse pro_features JSON string (or dict) → {Feature Name: value}."""
    if isinstance(raw, dict):
        src = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            src = json.loads(s)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    else:
        return {}
    if not isinstance(src, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in src.items():
        key = re.sub(r"\s+", " ", str(k or "").strip())
        val = re.sub(r"\s+", " ", str(v or "").strip())
        if not key or not val:
            continue
        if val.lower() in _SKIP_FEATURE_VALUES:
            continue
        out[key] = val
    return out


def product_matches_feature(
    product: dict,
    *,
    feature_key: str | None = None,
    feature_value: str | None = None,
) -> bool:
    """Match Color/Size fields or parsed pro_features (client-side)."""
    want_key = re.sub(r"\s+", " ", (feature_key or "").strip())
    want_val = re.sub(r"\s+", " ", (feature_value or "").strip())
    if not want_key and not want_val:
        return True
    want_val_l = want_val.lower()
    want_key_l = want_key.lower()
    nested = product.get("data") if isinstance(product.get("data"), dict) else {}

    def _val_hit(raw: Any) -> bool:
        if not want_val_l:
            return True
        if raw in (None, ""):
            return False
        parts = [re.sub(r"\s+", " ", x.strip()) for x in re.split(r"[,|/]+", str(raw))]
        parts = [p for p in parts if p] or [str(raw).strip()]
        for p in parts:
            pl = p.lower()
            if want_val_l == pl or want_val_l in pl or pl in want_val_l:
                return True
        return False

    if want_key_l in ("color", "colour", "colors"):
        color = product.get("color_name") or nested.get("color_name") or product.get("colors")
        return _val_hit(color)

    if want_key_l in ("size", "sizes"):
        size = product.get("size") or nested.get("size")
        return _val_hit(size)

    feats = product.get("pro_features")
    if not isinstance(feats, dict):
        feats = parse_pro_features(feats)
    if not feats:
        return False

    if want_key:
        for k, v in feats.items():
            kl = k.lower()
            if kl == want_key_l or want_key_l in kl or kl in want_key_l:
                if _val_hit(v):
                    return True
        return False
    return any(_val_hit(v) for v in feats.values())


def collect_feature_filters(products: list[dict], *, limit: int = 36) -> dict[str, Any]:
    """
    Unique filters from result set: Color + Size + pro_features.
    Same key+value once even if many products share it.
    """
    # key -> value_lower -> {value, count}
    buckets: dict[str, dict[str, dict[str, Any]]] = {}

    def _add(key: str, val: str) -> None:
        key = re.sub(r"\s+", " ", (key or "").strip())
        val = re.sub(r"\s+", " ", (val or "").strip())
        if not key or not val:
            return
        if val.lower() in _SKIP_FEATURE_VALUES:
            return
        vl = val.lower()
        group = buckets.setdefault(key, {})
        if vl not in group:
            group[vl] = {"key": key, "value": val, "count": 0}
        group[vl]["count"] += 1

    for p in products:
        nested = p.get("data") if isinstance(p.get("data"), dict) else {}
        # Color / Size from catalog fields (not only pro_features)
        color = p.get("color_name") or nested.get("color_name") or p.get("colors")
        if isinstance(color, list):
            for c in color:
                _add("Color", str(c))
        elif color not in (None, ""):
            for part in re.split(r"[,|/]+", str(color)):
                _add("Color", part)

        size = p.get("size") or nested.get("size")
        if size not in (None, ""):
            for part in re.split(r"[,|/]+", str(size)):
                _add("Size", part)

        feats = p.get("pro_features")
        if not isinstance(feats, dict):
            feats = parse_pro_features(feats)
        if not feats:
            continue
        for key, val in feats.items():
            # Avoid duplicating Color/Size already taken from fields
            if key.lower() in ("color", "colour", "colors", "size", "sizes"):
                continue
            parts = [re.sub(r"\s+", " ", x.strip()) for x in str(val).split(",")]
            parts = [x for x in parts if x and x.lower() not in _SKIP_FEATURE_VALUES]
            if not parts:
                parts = [str(val)]
            for part in parts:
                _add(key, part)

    # Color + Size first, then other features A–Z
    def _key_order(k: str) -> tuple:
        kl = k.lower()
        if kl == "color":
            return (0, k.lower())
        if kl == "size":
            return (1, k.lower())
        return (2, k.lower())

    groups: list[dict[str, Any]] = []
    flat: list[dict[str, Any]] = []
    for key in sorted(buckets.keys(), key=_key_order):
        options = sorted(buckets[key].values(), key=lambda o: (-o["count"], o["value"].lower()))
        options = options[:8]
        if not options:
            continue
        groups.append(
            {
                "key": key,
                "label": key,
                "options": [
                    {
                        "value": o["value"],
                        "label": o["value"],
                        "count": o["count"],
                        "query": f"{key}: {o['value']}",
                    }
                    for o in options
                ],
            }
        )
        for o in options:
            flat.append(
                {
                    "key": key,
                    "value": o["value"],
                    "label": f"{key}: {o['value']}",
                    "count": o["count"],
                    "query": f"{key}: {o['value']}",
                }
            )

    if not groups:
        return {"groups": [], "items": [], "description": ""}
    return {
        "groups": groups[:14],
        "items": flat[:limit],
        "description": (
            "Unique Color, Size, and product features from these results. "
            "Same name/value listed once only."
        ),
    }


def _hay_tokens(product: dict) -> set[str]:
    feat_bits = ""
    feats = product.get("pro_features")
    if isinstance(feats, dict):
        feat_bits = " ".join(f"{k} {v}" for k, v in feats.items())
    elif feats:
        feat_bits = str(feats)
    hay = " ".join(
        [
            str(product.get(k) or "").lower()
            for k in ("name", "category_name", "slug", "sku", "brand")
        ]
        + [feat_bits.lower()]
    )
    base = set(re.findall(r"[a-z0-9]+", hay))
    expanded = set(base)
    for ht in base:
        expanded |= _token_variants(ht)
    return expanded


def _filter_relevant_hits(products: list[dict], query: str) -> list[dict]:
    """
    Keep a hit only if EVERY significant query token appears in name/category/slug
    /pro_features (with light stem variants). Stops partial junk matches without a
    stopword list — e.g. 'show me hoodies' requires both 'show' AND 'hoodies'.
    """
    tokens = _query_tokens(query)
    if not tokens or not products:
        return products

    required = [_token_variants(t) for t in tokens]
    kept: list[dict] = []
    for p in products:
        hay = _hay_tokens(p)
        if all(variants & hay for variants in required):
            kept.append(p)
    return kept


def _keyword_variants(value: str) -> list[str]:
    """Case variants for keyword fields (color_name, size, brand, category_name)."""
    v = re.sub(r"\s+", " ", (value or "").strip())
    if not v:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for cand in (v, v.lower(), v.upper(), v.title()):
        if cand and cand not in seen:
            seen.add(cand)
            out.append(cand)
    return out


def _term_boosts(field: str, value: str, boost: float) -> list[dict]:
    clauses: list[dict] = []
    for cand in _keyword_variants(value):
        clauses.append({"term": {field: {"value": cand, "boost": boost}}})
    return clauses


def _strip_facet_tokens(query: str, *facets: str | None) -> str:
    """Remove AI-supplied color/size/brand tokens from the primary product query."""
    q = re.sub(r"\s+", " ", (query or "").strip())
    if not q:
        return q
    for facet in facets:
        raw = re.sub(r"\s+", " ", (facet or "").strip())
        if not raw:
            continue
        q = re.sub(rf"\b{re.escape(raw)}\b", " ", q, flags=re.I)
    return re.sub(r"\s+", " ", q).strip()


def _num(v: Any) -> float | None:
    try:
        if v in (None, ""):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def format_os_hit(source: dict) -> dict:
    """Map OpenSearch _source → chat/search product shape (website price formula)."""
    src = source if isinstance(source, dict) else {}
    unit = _num(src.get("unit_price")) or 0.0
    purchase = _num(src.get("purchase_price")) or 0.0
    shipping = _num(src.get("shipping_cost")) or 0.0
    has_discount = unit > purchase
    stroked = unit if has_discount else purchase
    main = (purchase if has_discount else unit) + shipping

    pro_id = src.get("pro_id")
    pg_id = src.get("id")  # Postgres / stock row id
    thumb = src.get("thumbnail_img") or src.get("thumb_url") or ""

    return {
        "id": pro_id,
        "pid": pro_id,
        "pro_id": pro_id,
        "stock_id": pg_id,
        "stockId": pg_id,
        "name": src.get("name") or str(pro_id or ""),
        "slug": src.get("slug"),
        "sku": src.get("sku"),
        "brand": src.get("brand"),
        "category_id": src.get("category_id"),
        "category_name": src.get("category_name"),
        "color_name": src.get("color_name"),
        "size": src.get("size"),
        "stock": src.get("stock"),
        "rating": src.get("rating") or 0,
        "thumbnail_image": thumb,
        "thumbnail_img": thumb,
        "unit_price": src.get("unit_price"),
        "purchase_price": src.get("purchase_price"),
        "shipping_cost": src.get("shipping_cost"),
        "has_discount": has_discount,
        "stroked_price": stroked if stroked else None,
        "main_price": main,
        "selling_price": main,
        "new_price": main,
        "base_price": stroked if has_discount else main,
        "old_price": stroked if has_discount else None,
        "todays_deal": src.get("todays_deal"),
        "delivery_time": src.get("delivery_time"),
        "delivery_time_unit": src.get("delivery_time_unit"),
        "location_id": src.get("location_id"),
        "pro_features": parse_pro_features(src.get("pro_features")),
        "data": {
            "id": pg_id,
            "user_id": src.get("user_id"),
            "thumbnail_img": thumb,
            "unit_price": src.get("unit_price"),
            "purchase_price": src.get("purchase_price"),
            "shipping_cost": src.get("shipping_cost"),
            "slug": src.get("slug"),
            "color_name": src.get("color_name"),
            "size": src.get("size"),
            "stock": src.get("stock"),
            "category_id": src.get("category_id"),
            "brand": src.get("brand"),
        },
    }


def _facet_match_meta(
    products: list[dict],
    *,
    color: str | None,
    size_label: str | None,
    brand: str | None,
    category: str | None,
) -> dict[str, Any]:
    """Tell the model how well color/size/etc matched among returned hits."""

    def _hit(val: Any, want: str | None) -> bool:
        if not want:
            return False
        hay = str(val or "").strip().lower()
        w = want.strip().lower()
        return bool(hay) and (w == hay or w in hay or hay in w)

    n = len(products)
    color_n = sum(1 for p in products if _hit(p.get("color_name"), color)) if color else None
    size_n = sum(1 for p in products if _hit(p.get("size"), size_label)) if size_label else None
    brand_n = sum(1 for p in products if _hit(p.get("brand"), brand)) if brand else None
    cat_n = (
        sum(1 for p in products if _hit(p.get("category_name"), category)) if category else None
    )

    hints: list[str] = []
    if color and n:
        if color_n == 0:
            hints.append(
                f"Requested color '{color}' is NOT in these results. "
                "Say so naturally and offer the same product type in other colors shown — "
                "do NOT pretend these are that color."
            )
        elif color_n < max(1, n // 3):
            hints.append(
                f"Only {color_n}/{n} results match color '{color}'. "
                "Lead with matching ones; mention others are different colors."
            )
    if size_label and n:
        if size_n == 0:
            hints.append(
                f"Requested size '{size_label}' is NOT in these results. "
                "Say so naturally; show other sizes of the same product type if present."
            )
        elif size_n < max(1, n // 3):
            hints.append(
                f"Only {size_n}/{n} results match size '{size_label}'. Mention that briefly."
            )
    if brand and n and brand_n == 0:
        hints.append(
            f"Requested brand '{brand}' not in results — say so; don't invent that brand."
        )
    if category and n and cat_n == 0:
        hints.append(
            f"Requested category '{category}' not clearly in results — be honest about what's shown."
        )

    return {
        "requested_color": color,
        "requested_size": size_label,
        "requested_brand": brand,
        "requested_category": category,
        "color_matches": color_n,
        "size_matches": size_n,
        "brand_matches": brand_n,
        "category_matches": cat_n,
        "result_count": n,
        "hints": hints,
    }


def build_search_body(
    *,
    query: str,
    page: int = 1,
    size: int | None = None,
    color: str | None = None,
    size_label: str | None = None,
    brand: str | None = None,
    category: str | None = None,
    feature_key: str | None = None,
    feature_value: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock: bool = True,
) -> dict[str, Any]:
    """
    Priority: primary product query (q) >> color/size/brand/pro_features boosts.
    Product-type must match first; facets only re-rank within that set.
    """
    q = re.sub(r"\s+", " ", (query or "").strip())
    page = max(1, int(page or 1))
    per = int(size if size is not None else OPENSEARCH_SIZE)
    per = max(1, min(per, 50))
    offset = (page - 1) * per
    feat_key = re.sub(r"\s+", " ", (feature_key or "").strip())
    feat_val = re.sub(r"\s+", " ", (feature_value or "").strip())

    filters: list[dict] = []
    must: list[dict] = []
    should: list[dict] = []

    if in_stock:
        filters.append({"range": {"stock": {"gt": 0}}})

    price_range: dict[str, float] = {}
    if min_price is not None:
        try:
            price_range["gte"] = float(min_price)
        except (TypeError, ValueError):
            pass
    if max_price is not None:
        try:
            price_range["lte"] = float(max_price)
        except (TypeError, ValueError):
            pass
    if price_range:
        filters.append({"range": {"unit_price": price_range}})

    # pro_features is NOT indexed in OpenSearch (object enabled:false).
    # Feature filters are applied client-side after hits are fetched.

    # Strip facet tokens so must focuses on product type ("t shirt" not "red")
    core_q = _strip_facet_tokens(q, color, size_label, brand, feat_key, feat_val) or q

    if q and re.fullmatch(r"\d{4,}", q):
        try:
            filters.append({"term": {"pro_id": int(q)}})
        except ValueError:
            pass
    elif core_q:
        # PRIMARY: product type / category / name — dominates score
        must.append(
            {
                "multi_match": {
                    "query": core_q,
                    "fields": _PRODUCT_FIELDS,
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "operator": "or",
                    "boost": 4.0,
                }
            }
        )
        # Soft full-phrase nudge (includes color words still in q)
        if q != core_q or color or size_label or feat_val:
            should.append(
                {
                    "multi_match": {
                        "query": q,
                        "fields": _PHRASE_FIELDS,
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                        "operator": "or",
                        "boost": 1.2,
                    }
                }
            )
    elif q:
        must.append(
            {
                "multi_match": {
                    "query": q,
                    "fields": _PRODUCT_FIELDS,
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "boost": 4.0,
                }
            }
        )

    # SECONDARY facets — light boosts only (must never outrun product-type score)
    if color:
        should.extend(_term_boosts("color_name", color, 1.8))
        should.append({"match": {"name": {"query": color, "boost": 0.8}}})
    if size_label:
        should.extend(_term_boosts("size", size_label, 1.5))
    if brand:
        should.extend(_term_boosts("brand", brand, 1.6))
        should.append({"match": {"name": {"query": brand, "boost": 0.9}}})
    if category:
        should.extend(_term_boosts("category_name", category, 1.6))
        should.append({"match": {"name": {"query": category, "boost": 1.0}}})

    bool_q: dict[str, Any] = {}
    if must:
        bool_q["must"] = must
    elif not filters:
        bool_q["must"] = [{"match_all": {}}]
    if should:
        bool_q["should"] = should
        bool_q["minimum_should_match"] = 0
    if filters:
        bool_q["filter"] = filters

    if not bool_q.get("must") and not bool_q.get("filter") and not bool_q.get("should"):
        bool_q = {"must": [{"match_none": {}}]}

    return {
        "query": {"bool": bool_q},
        "sort": [{"_score": {"order": "desc"}}, {"id": {"order": "desc"}}],
        "size": per,
        "from": offset,
        "track_total_hits": True,
        "_core_q": core_q,
    }


def search_products_os(
    *,
    query: str,
    page: int = 1,
    color: str | None = None,
    size_label: str | None = None,
    brand: str | None = None,
    category: str | None = None,
    feature_key: str | None = None,
    feature_value: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> dict[str, Any]:
    """POST /{index}/_search with basic auth. Returns chat-friendly product payload."""
    # Fetch a wider page when feature-filtering (pro_features not indexed)
    fetch_size = OPENSEARCH_SIZE
    if feature_key or feature_value:
        fetch_size = max(OPENSEARCH_SIZE, 50)
    body = build_search_body(
        query=query,
        page=page,
        size=fetch_size,
        color=color,
        size_label=size_label,
        brand=brand,
        category=category,
        feature_key=feature_key,
        feature_value=feature_value,
        min_price=min_price,
        max_price=max_price,
    )
    core_q = body.pop("_core_q", query)
    url = f"{OPENSEARCH_BASE}/{OPENSEARCH_INDEX}/_search"
    print("================")
    print(f"OPENSEARCH URL  = {url}")
    print(f"OPENSEARCH q    = {query!r}  (primary product core = {core_q!r})")
    if color:
        print(f"OPENSEARCH color boost (secondary) = {color!r}")
    if size_label:
        print(f"OPENSEARCH size boost  (secondary) = {size_label!r}")
    if brand:
        print(f"OPENSEARCH brand boost (secondary) = {brand!r}")
    if category:
        print(f"OPENSEARCH category    (secondary) = {category!r}")
    if feature_key or feature_value:
        print(f"OPENSEARCH feature filter = {feature_key!r}: {feature_value!r}")
    print("================")

    try:
        resp = requests.post(
            url,
            auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
            json=body,
            timeout=OPENSEARCH_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
    except requests.RequestException as exc:
        return {
            "result": False,
            "error": True,
            "message": f"OpenSearch request failed: {exc}",
            "products": [],
            "total": 0,
            "search_query": query,
        }

    if resp.status_code >= 400:
        return {
            "result": False,
            "error": True,
            "message": f"OpenSearch HTTP {resp.status_code}",
            "detail": (resp.text or "")[:500],
            "products": [],
            "total": 0,
            "search_query": query,
        }

    try:
        data = resp.json()
    except ValueError:
        return {
            "result": False,
            "error": True,
            "message": "OpenSearch returned non-JSON",
            "products": [],
            "total": 0,
            "search_query": query,
        }

    hits_block = data.get("hits") or {}
    total_raw = hits_block.get("total")
    if isinstance(total_raw, dict):
        total = int(total_raw.get("value") or 0)
    else:
        try:
            total = int(total_raw or 0)
        except (TypeError, ValueError):
            total = 0

    products: list[dict] = []
    for hit in hits_block.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        src = hit.get("_source")
        if not isinstance(src, dict):
            continue
        row = format_os_hit(src)
        row["_score"] = hit.get("_score")
        products.append(row)

    # Relevance gate (no stopword dictionary): every significant query token must hit
    before_n = len(products)
    products = _filter_relevant_hits(products, core_q or query)
    if before_n and not products:
        total = 0

    # Client-side pro_features filter (field is object enabled:false — not searchable)
    if products and (feature_key or feature_value):
        products = [
            p
            for p in products
            if product_matches_feature(
                p, feature_key=feature_key, feature_value=feature_value
            )
        ]
        total = len(products)
        # Cap to normal page size after filtering
        products = products[:OPENSEARCH_SIZE]

    match_meta = _facet_match_meta(
        products,
        color=color,
        size_label=size_label,
        brand=brand,
        category=category,
    )
    if before_n and not products:
        match_meta["hints"] = list(match_meta.get("hints") or []) + [
            "OpenSearch returned rows but none matched the product tokens in the query. "
            "Treat as ZERO results — say clearly nothing matching was found. "
            "Do NOT show product cards. Do NOT invent alternatives as if they matched. "
            "Write a longer natural reply: acknowledge what they asked, say stock/catalog "
            "mein nahi mila, ask one useful clarifying question (style/color/similar type)."
        ]
        match_meta["mode"] = "not_found"
    elif products:
        match_meta["mode"] = "matched"
    else:
        match_meta["mode"] = "not_found"
        match_meta["hints"] = list(match_meta.get("hints") or []) + [
            "Zero catalog hits. Describe clearly that nothing matched; ask what else to try. "
            "No <<<CARDS>>>."
        ]

    feature_filters = collect_feature_filters(products) if products else {
        "groups": [],
        "items": [],
        "description": "",
    }

    return {
        "result": True,
        "total": total if products else 0,
        "page": max(1, int(page or 1)),
        "products": products,
        "search_query": query,
        "product_core_query": core_q,
        "match_meta": match_meta,
        "feature_filters": feature_filters,
        "applied_feature": (
            {"key": feature_key, "value": feature_value}
            if (feature_key or feature_value)
            else None
        ),
        "source": "opensearch",
        "index": OPENSEARCH_INDEX,
    }
