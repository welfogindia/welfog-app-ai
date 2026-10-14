"""Build rich UI card payloads from recent tool results."""

from __future__ import annotations

import json
import re
from typing import Any

from play import is_play_tool, pick_play_ui

IMG_CDN = "https://image.welfog.com/"
OLD_IMG_CDN = "https://d1f02fefkbso7w.cloudfront.net/"
BAD_IMG_PREFIXES = (
    "https://welfog.com/images/",
    "http://welfog.com/images/",
    "https://www.welfog.com/images/",
    "https://welfog.com/",
    "http://welfog.com/",
)


def media_url(path: Any) -> str | None:
    if not path:
        return None
    s = str(path).strip()
    if not s:
        return None
    # Fix wrong prefixes the model/API sometimes invent
    for bad in BAD_IMG_PREFIXES:
        if s.startswith(bad):
            s = s[len(bad) :]
            break
    if s.startswith("http://") or s.startswith("https://"):
        s = s.replace(OLD_IMG_CDN, IMG_CDN).replace(
            OLD_IMG_CDN.replace("https://", "http://"), IMG_CDN
        )
        if s.startswith(IMG_CDN) or "image.welfog.com" in s:
            return s
        if "welfog" not in s.lower():
            return s
        # rewrite any leftover welfog host image paths
        for marker in ("/images/", "/uploads/"):
            if marker in s:
                s = s.split(marker, 1)[-1]
                if marker == "/uploads/":
                    s = "uploads/" + s
                break
        else:
            return s
    return IMG_CDN + s.lstrip("/")


def _web_base() -> str:
    try:
        from config import WELFOG_WEB_BASE

        return (WELFOG_WEB_BASE or "https://welfog.com").rstrip("/")
    except Exception:
        return "https://welfog.com"


def product_page_url(*, slug: Any = None, url: Any = None, product_id: Any = None) -> str | None:
    """Public product URL: /product_details/{pro_id}/{slug}-{pro_id}."""
    base = _web_base()
    pid = str(product_id).strip() if product_id not in (None, "") else ""

    raw_path = ""
    for raw in (url, slug):
        if not raw:
            continue
        s = str(raw).strip()
        if not s:
            continue
        s = s.replace("/product/", "/product_details/", 1)
        m = re.search(r"/product_details/([^?#]+)", s, re.I)
        if m:
            raw_path = m.group(1).strip("/")
        else:
            s2 = s.lstrip("/")
            low = s2.lower()
            if low.startswith("product_details/"):
                raw_path = s2.split("/", 1)[1].split("?")[0]
            elif low.startswith("product/"):
                raw_path = s2[len("product/") :].split("?")[0]
            else:
                raw_path = s2.split("?")[0]
        break

    slug_part = ""
    if raw_path:
        parts = [p for p in raw_path.split("/") if p]
        if len(parts) >= 2 and parts[0].isdigit():
            pid = pid or parts[0]
            slug_part = "/".join(parts[1:])
        else:
            slug_part = "/".join(parts)
            if not pid:
                tail = re.search(r"-(\d+)$", slug_part)
                if tail:
                    pid = tail.group(1)

    if pid and slug_part:
        return f"{base}/product_details/{pid}/{slug_part}"
    if slug_part:
        return f"{base}/product_details/{slug_part}"
    if pid:
        return f"{base}/product_details/{pid}"
    return None


def order_page_url(*, order_id: Any = None, url: Any = None) -> str | None:
    """Public/account order detail URL on welfog.com."""
    if url:
        s = str(url).strip()
        if s.startswith("http://") or s.startswith("https://"):
            # Rewrite legacy purchase_history links
            m = re.search(r"/purchase_history/details/([^/?#]+)", s)
            if m:
                return f"{_web_base()}/account/order_details?id={m.group(1)}"
            return s
    if order_id in (None, ""):
        return None
    oid = str(order_id).strip()
    return f"{_web_base()}/account/order_details?id={oid}"


def _parse_tool_content(content: Any) -> Any:
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except Exception:
            return None
    return None


def _money(v: Any) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, str):
        cleaned = (
            v.replace("Rs.", "")
            .replace("Rs", "")
            .replace("₹", "")
            .replace(",", "")
            .strip()
        )
        try:
            n = float(cleaned)
        except Exception:
            return v if v.startswith("₹") else f"₹{cleaned}" if cleaned else None
        v = n
    try:
        n = float(v)
        if n == int(n):
            return f"₹{int(n)}"
        return f"₹{n:.2f}"
    except Exception:
        s = str(v)
        return s if s.startswith("₹") else f"₹{s}"


def _status_tone(status: str | None) -> str:
    s = (status or "").lower().strip()
    if not s:
        return "neutral"
    # check negatives first (unpaid contains "paid")
    if any(x in s for x in ("unpaid", "cancel", "fail", "reject", "banned", "refund")):
        return "bad"
    if any(x in s for x in ("hold", "pending", "process", "ship", "dispatch", "return", "rto", "placed", "out for", "confirm")):
        return "warn"
    if any(x in s for x in ("deliver", "complete", "success", "paid", "active")):
        return "ok"
    return "neutral"


def _order_status_label(row: dict) -> str | None:
    """Only human current_order_status — never delivery_status / delivery_status_string."""
    cur = row.get("current_order_status")
    if cur not in (None, ""):
        return str(cur)
    # If missing, use last completed tracking step title (not delivery_status)
    steps = _extract_tracking(row)
    done = [s for s in steps if s.get("done")]
    if done:
        return done[-1].get("title")
    return None


def _extract_tracking(row: dict) -> list[dict]:
    detail = row.get("order_status_detail")
    if not isinstance(detail, dict):
        return []
    order_status = detail.get("order_status") or {}
    flow = order_status.get("order_flow") if isinstance(order_status, dict) else None
    if not isinstance(flow, dict):
        return []

    steps = []
    for key, step in flow.items():
        if not isinstance(step, dict):
            continue
        title = step.get("title") or key.replace("_", " ").title()
        done = bool(step.get("status"))
        date = step.get("date")
        date_str = None
        if date:
            try:
                # 2026-04-23T05:59:05.000Z -> readable
                d = str(date).replace("Z", "").split("T")
                date_str = d[0] if d else str(date)[:10]
            except Exception:
                date_str = str(date)[:16]
        steps.append(
            {
                "key": key,
                "title": title,
                "done": done,
                "date": date_str,
                "reason": step.get("reason"),
            }
        )
    return steps


def _format_address_line(addr: dict) -> str:
    parts = [
        addr.get("address"),
        addr.get("city"),
        addr.get("state"),
        addr.get("postal_code"),
        addr.get("country"),
    ]
    return ", ".join(str(p) for p in parts if p)


def _pick_order_detail(data: dict) -> list[dict]:
    """Full order detail card from merged details + items APIs."""
    order = data.get("order") if isinstance(data.get("order"), dict) else None
    if not order:
        # fallback: treat as list row
        rows = _pick_orders(data, with_tracking=True)
        return rows

    addr = order.get("shipping_address") if isinstance(order.get("shipping_address"), dict) else {}
    status = _order_status_label(order)
    payment = order.get("payment_status_string") or (
        str(order.get("payment_status")).title()
        if order.get("payment_status") in ("paid", "unpaid")
        else None
    )
    items = order.get("items") if isinstance(order.get("items"), list) else []
    product_name = order.get("product_name") or (
        items[0].get("product_name") if items else None
    )
    qty = order.get("quantity") or (items[0].get("quantity") if items else 1)
    size = order.get("size") or (items[0].get("variation") if items else None)
    unit = order.get("unit_price") or (items[0].get("unit_price") if items else None)

    return [
        {
            "type": "order_detail",
            "order_id": order.get("id") or order.get("oid"),
            "date": order.get("date"),
            "status": status,
            "status_tone": _status_tone(status),
            "total": _money(order.get("grand_total")),
            "payment_type": order.get("payment_type"),
            "payment_status": payment,
            "payment_tone": _status_tone(str(payment) if payment else None),
            "shipping_type": order.get("shipping_type_string"),
            "image": media_url(order.get("product_img")),
            "product_name": product_name,
            "size": size,
            "color": order.get("color"),
            "quantity": qty,
            "unit_price": _money(unit),
            "line_total": _money(order.get("grand_total")),
            "costs": {
                "subtotal": _money(order.get("subtotal")),
                "shipping": _money(order.get("shipping_cost")),
                "cod": _money(order.get("cod_cost")),
                "coupon": _money(order.get("coupon_discount")),
                "tax": _money(order.get("tax")),
                "total": _money(order.get("grand_total")),
            },
            "address": {
                "name": addr.get("name"),
                "phone": addr.get("phone"),
                "email": addr.get("email") or "",
                "line": _format_address_line(addr),
            },
            "tracking": _extract_tracking(order),
            "tracking_code": order.get("tracking_code"),
            "href": order_page_url(order_id=order.get("id") or order.get("oid")),
            "product_href": product_page_url(
                slug=order.get("product_slug") or order.get("slug"),
                product_id=order.get("product_id"),
            ),
        }
    ]


def _pick_orders(data: dict, *, with_tracking: bool = False) -> list[dict]:
    rows = (
        data.get("data")
        or data.get("orders")
        or []
    )
    if isinstance(rows, dict):
        rows = rows.get("data") or rows.get("orders") or []
    # single order object
    if not rows and (data.get("id") or data.get("oid") or data.get("product_title")):
        rows = [data]
    if not isinstance(rows, list):
        return []

    # auto tracking for single-order payloads
    if len(rows) == 1:
        with_tracking = True

    cards = []
    for row in rows[:12]:
        if not isinstance(row, dict):
            continue
        oid = row.get("id") or row.get("oid") or row.get("order_id") or row.get("code")
        total = row.get("grand_total") or row.get("total") or row.get("amount")
        status = _order_status_label(row)
        payment = row.get("payment_status_string") or None
        # Only show paid/unpaid label strings — not raw codes if string missing
        if not payment and row.get("payment_status") in ("paid", "unpaid"):
            payment = str(row.get("payment_status")).title()
        title = (
            row.get("product_title")
            or row.get("name")
            or row.get("product_name")
            or None
        )
        img_path = row.get("product_img") or row.get("thumbnail_image") or row.get("img")

        tracking = _extract_tracking(row) if with_tracking else []
        cards.append(
            {
                "type": "order",
                "order_id": oid,
                "product_id": row.get("product_id"),
                "title": title,
                "total": _money(total),
                "status": status,
                "status_tone": _status_tone(status),
                "payment_status": payment,
                "payment_tone": _status_tone(str(payment) if payment else None),
                "payment_type": row.get("payment_type"),
                "date": row.get("date") or row.get("created_at"),
                "image": media_url(img_path),
                "slug": row.get("product_slug"),
                "href": order_page_url(order_id=oid),
                "product_href": product_page_url(
                    slug=row.get("product_slug"),
                    product_id=row.get("product_id"),
                ),
                "tracking": tracking,
                "tracking_code": row.get("tracking_code"),
            }
        )
    return cards


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, str):
        cleaned = (
            v.replace("Rs.", "")
            .replace("Rs", "")
            .replace("₹", "")
            .replace(",", "")
            .strip()
        )
        try:
            return float(cleaned)
        except Exception:
            return None
    try:
        return float(v)
    except Exception:
        return None


def _fmt_size(size: Any) -> str | None:
    if size is None or size == "":
        return None
    if isinstance(size, list):
        parts = [str(x).strip() for x in size if str(x).strip()]
        return ", ".join(parts[:6]) if parts else None
    s = str(size).strip()
    if not s:
        return None
    # JSON array string
    if s.startswith("["):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                parts = [str(x).strip() for x in arr if str(x).strip()]
                return ", ".join(parts[:6]) if parts else None
        except Exception:
            pass
    return s.replace("|", ", ")


def _display_brand(value: Any) -> str | None:
    """Show real brand only — hide empty / placeholder 'No Brand'."""
    if value in (None, ""):
        return None
    s = str(value).strip()
    if not s:
        return None
    norm = re.sub(r"[\s\-_/]+", "", s.lower())
    if norm in {"nobrand", "nobrands", "na", "n/a", "none", "null", "undefined"}:
        return None
    return s


def _price_block(row: dict) -> dict:
    nested = row.get("data") if isinstance(row.get("data"), dict) else {}
    # Wishlist: selling/base | Search: main/stroked | Deals: new/old
    selling = _num(
        row.get("selling_price")
        if row.get("selling_price") is not None
        else row.get("new_price")
        if row.get("new_price") is not None
        else row.get("main_price")
        if row.get("main_price") is not None
        else row.get("discounted_price")
        or row.get("price")
        or nested.get("purchase_price")
        or nested.get("new_price")
    )
    mrp = _num(
        row.get("base_price")
        if row.get("base_price") is not None
        else row.get("old_price")
        if row.get("old_price") is not None
        else row.get("stroked_price")
        or row.get("unit_price")
        or nested.get("unit_price")
        or nested.get("old_price")
    )
    has_discount = bool(row.get("has_discount"))
    if selling is None and mrp is not None:
        selling = mrp
    if mrp is None:
        mrp = selling

    off = None
    if selling is not None and mrp is not None and mrp > selling:
        has_discount = True
        off = int(round((mrp - selling) / mrp * 100))
        if off <= 0:
            has_discount = False
            off = None

    return {
        "price": _money(selling),
        "mrp": _money(mrp) if has_discount and mrp and selling is not None and mrp > selling else None,
        "off_percent": off,
        "has_discount": bool(has_discount and off),
    }


def _normalize_product_row(row: dict) -> dict:
    """Flatten wishlist {id, product:{...}} and similar nested shapes."""
    if not isinstance(row, dict):
        return {}
    if isinstance(row.get("product"), dict):
        p = dict(row["product"])
        p["_wishlist_id"] = row.get("id")
        return p
    return row


def _pick_products(data: dict) -> list[dict]:
    rows = data.get("products") or data.get("data") or []
    if isinstance(rows, dict):
        rows = rows.get("data") or rows.get("products") or []
    if not isinstance(rows, list):
        return []

    cards = []
    for raw in rows[:20]:
        if not isinstance(raw, dict):
            continue
        row = _normalize_product_row(raw)
        if not row:
            continue
        nested = row.get("data") if isinstance(row.get("data"), dict) else {}
        pricing = _price_block(row)
        color = row.get("color_name") or nested.get("color_name") or row.get("colors") or nested.get("colors")
        if isinstance(color, list):
            color = ", ".join(str(c) for c in color[:4] if c)
        size = _fmt_size(row.get("size") or nested.get("size"))
        name = (row.get("name") or row.get("product_name") or "").strip() or "Product"
        img_raw = (
            row.get("thumbnail_image")
            or row.get("thumbnail_img")
            or row.get("thumb_url")
            or row.get("product_img")
            or row.get("image")
            or nested.get("thumbnail_image")
            or nested.get("thumbnail_img")
        )
        pid = row.get("pro_id") or row.get("pid") or row.get("product_id") or row.get("id")
        nested = row.get("data") if isinstance(row.get("data"), dict) else {}
        stock_id = (
            row.get("stock_id")
            or row.get("stockId")
            or nested.get("id")
        )
        if stock_id in (None, ""):
            stocks = row.get("stocks")
            if isinstance(stocks, list) and stocks and isinstance(stocks[0], dict):
                stock_id = stocks[0].get("id")
        delivery_min = (
            row.get("delivery_time_minute")
            or row.get("duration")
            or nested.get("duration")
            or nested.get("delivery_time_minute")
        )
        cards.append(
            {
                "type": "product",
                "id": pid,
                "wishlist_id": row.get("_wishlist_id"),
                "name": name,
                "slug": row.get("slug") or row.get("link") or row.get("url"),
                "href": product_page_url(
                    slug=row.get("slug") or row.get("link"),
                    url=row.get("url"),
                    product_id=pid,
                ),
                "price": pricing["price"],
                "mrp": pricing["mrp"],
                "off_percent": pricing["off_percent"],
                "has_discount": pricing["has_discount"],
                "color": str(color).strip() if color not in (None, "") else None,
                "size": size,
                "shop": _display_brand(row.get("shop_name") or row.get("brand")),
                "image": media_url(img_raw),
                "stock": row.get("stock") or row.get("current_stock") or nested.get("stock"),
                "stock_id": stock_id,
                "delivery_time_minute": delivery_min,
            }
        )
    return cards


def _pick_addresses(data: dict) -> list[dict]:
    rows = data.get("addData") or data.get("data") or data.get("addresses") or []
    if not isinstance(rows, list):
        return []
    cards = []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        parts = [
            row.get("address"),
            row.get("area"),
            row.get("city"),
            row.get("state"),
            row.get("postal_code") or row.get("pincode"),
        ]
        line = ", ".join(str(p) for p in parts if p)
        cards.append(
            {
                "type": "address",
                "name": row.get("name") or row.get("address_name") or "Address",
                "phone": row.get("phone"),
                "line": line,
                "default": bool(row.get("using_this") or row.get("set_default")),
            }
        )
    return cards


def _pick_profile(data: dict) -> list[dict]:
    user = data.get("data") or data.get("user") or data
    if not isinstance(user, dict):
        return []
    if not any(user.get(k) for k in ("name", "phone", "email", "id")):
        return []
    return [
        {
            "type": "profile",
            "name": user.get("name") or "User",
            "phone": user.get("phone"),
            "email": user.get("email"),
            "id": user.get("id"),
            "gender": user.get("gender"),
            "dob": user.get("dob"),
            "marital_status": user.get("marital_status"),
        }
    ]


ORDER_TOOLS = {
    "get_my_orders",
    "get_purchase_history",
    "get_order_details",
}
PRODUCT_TOOLS = {
    "search_products",
    "get_today_deals",
    "get_related_products",
    "get_product_details",
    "get_my_wishlist",
    "add_to_wishlist",
}
# Browse helpers — hide these cards when the turn is really login / cart action
BROWSE_ONLY_PRODUCT_TOOLS = {
    "search_products",
    "get_today_deals",
    "get_related_products",
    "get_product_details",
}
ACTION_TURN_TOOLS = {
    "send_login_otp",
    "verify_login_otp",
    "add_to_cart",
    "remove_from_cart",
    "update_cart_quantity",
    "apply_coupon",
    "add_to_wishlist",
    "remove_from_wishlist",
}
ADDRESS_TOOLS = {"get_my_addresses", "select_address"}
PROFILE_TOOLS = {
    "get_my_profile",
    "update_my_profile",
    "get_user_snapshot",
    "verify_login_otp",
}
CART_TOOLS = {
    "get_my_cart",
    "get_cart_summary",
    "add_to_cart",
    "remove_from_cart",
    "update_cart_quantity",
    "apply_coupon",
}

def extract_ui_from_history(history: list[dict]) -> list[dict]:
    """Scan the latest assistant turn's tool results and build UI cards."""
    last_user_idx = None
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") == "user":
            last_user_idx = i
            break
    if last_user_idx is None:
        return []

    pending_names: list[str] = []
    cards: list[dict] = []
    browse_products: list[dict] = []
    seen_types: set[str] = set()
    used_tools: set[str] = set()
    asst_bits: list[str] = []

    def _push(batch: list[dict], *, browse: bool = False) -> None:
        target = browse_products if browse else cards
        for c in batch:
            key = f"{c.get('type')}:{c.get('order_id') or c.get('id') or c.get('name') or c.get('title')}"
            if key in seen_types:
                continue
            seen_types.add(key)
            target.append(c)

    for msg in history[last_user_idx + 1 :]:
        role = msg.get("role")
        if role == "assistant":
            if msg.get("content"):
                asst_bits.append(str(msg.get("content") or ""))
            if msg.get("tool_calls"):
                pending_names = [
                    (tc.get("function") or {}).get("name") or ""
                    for tc in msg["tool_calls"]
                ]
            continue
        if role == "tool":
            name = pending_names.pop(0) if pending_names else ""
            used_tools.add(name)
            data = _parse_tool_content(msg.get("content"))
            if not isinstance(data, dict) or data.get("error") or data.get("needs_login"):
                continue

            batch: list[dict] = []
            if name in ORDER_TOOLS:
                if name == "get_order_details" or data.get("detail_mode"):
                    batch = _pick_order_detail(data)
                else:
                    batch = _pick_orders(
                        data,
                        with_tracking=False,
                    )
                if not batch and (data.get("id") or data.get("oid") or data.get("product_title")):
                    batch = _pick_orders({"data": [data]}, with_tracking=True)
                _push(batch)
            elif name in PRODUCT_TOOLS:
                if name == "get_product_details":
                    prod = data.get("product") or data.get("data") or data
                    if isinstance(prod, dict):
                        batch = _pick_products({"products": [prod]})
                else:
                    batch = _pick_products(data)
                _push(batch, browse=name in BROWSE_ONLY_PRODUCT_TOOLS)
                # Unique pro_feature filters under product cards (search only)
                if name == "search_products":
                    ff = data.get("feature_filters") if isinstance(data.get("feature_filters"), dict) else None
                    groups = (ff or {}).get("groups") or []
                    if groups:
                        _push(
                            [
                                {
                                    "type": "feature_filters",
                                    "title": "Filter by features",
                                    "description": (
                                        "Inme se feature choose karke results narrow kar sakte ho "
                                        "(same feature ek baar hi dikhaya gaya hai)."
                                    ),
                                    "groups": groups,
                                    "base_query": data.get("search_query")
                                    or data.get("product_core_query")
                                    or "",
                                    "applied": data.get("applied_feature"),
                                }
                            ],
                            browse=True,
                        )
            elif name in ADDRESS_TOOLS:
                _push(_pick_addresses(data))
            elif name in PROFILE_TOOLS:
                if name == "verify_login_otp" and data.get("user"):
                    batch = _pick_profile({"data": data["user"]})
                elif name == "update_my_profile" and isinstance(data.get("profile"), dict):
                    batch = _pick_profile(data["profile"])
                else:
                    batch = _pick_profile(data)
                _push(batch)
            elif name in CART_TOOLS:
                cart_data = data.get("cart") if isinstance(data.get("cart"), dict) else data
                items = []
                if isinstance(cart_data, dict):
                    items = cart_data.get("items") or []
                if items:
                    fake_rows = []
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        fake_rows.append(
                            {
                                "id": it.get("product_id"),
                                "name": it.get("name") or "Cart item",
                                "thumbnail_image": it.get("thumbnail"),
                                "purchase_price": it.get("price"),
                                "unit_price": it.get("mrp"),
                                "size": it.get("size"),
                                "shop_name": it.get("shop"),
                            }
                        )
                    batch = _pick_products({"products": fake_rows})
                    for c in batch:
                        c["from_cart"] = True
                if not batch and name in ("get_my_cart", "get_cart_summary"):
                    batch = _pick_products(data)
                    for c in batch:
                        c["from_cart"] = True
                # remove/add/update: never scrape random products from nested API payloads
                if not batch and name in (
                    "remove_from_cart",
                    "add_to_cart",
                    "update_cart_quantity",
                    "apply_coupon",
                ):
                    batch = []
                if not batch:
                    if any(k in data for k in ("grand_total", "sub_total", "total")):
                        batch = [
                            {
                                "type": "summary",
                                "title": "Cart summary",
                                "rows": [
                                    {
                                        "label": k.replace("_", " ").title(),
                                        "value": _money(v) or str(v),
                                    }
                                    for k, v in data.items()
                                    if k
                                    in (
                                        "sub_total",
                                        "shipping",
                                        "tax",
                                        "discount",
                                        "grand_total",
                                        "total",
                                        "coupon_applied",
                                    )
                                    and v not in (None, "")
                                ],
                            }
                        ]
                _push(batch)
            elif is_play_tool(name):
                _push(pick_play_ui(name, data))

    # Login / cart-action turns: don't re-dump browse search carousels
    asst_text = " ".join(asst_bits).lower()
    asking_login = any(
        s in asst_text
        for s in (
            "otp bhej",
            "send otp",
            "verify otp",
            "10-digit",
            "10 digit",
            "mobile number",
            "phone number",
            "login karna",
            "log in",
            "sign in",
        )
    ) or (
        ("otp" in asst_text)
        and any(x in asst_text for x in ("mobile", "phone", "number", "login", "verify"))
    )
    action_turn = bool(used_tools & ACTION_TURN_TOOLS) or asking_login
    if not action_turn:
        cards.extend(browse_products)

    # Hide profile card when showing orders/products (keeps UI clean)
    if any(c.get("type") in ("order", "order_detail", "product") for c in cards):
        cards = [c for c in cards if c.get("type") != "profile"]

    user_query = _to_text(history[last_user_idx].get("content"))
    cards = _rank_products_for_user(cards, user_query)

    # Keep feature filter block even when product list is capped
    return cards[:20]


def _to_text(val: Any) -> str:
    """Safely extracts plain string from either str or multimodal content list."""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        parts = []
        for part in val:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(parts).strip()
    return str(val or "")


def _rank_products_for_user(cards: list[dict], user_query: Any) -> list[dict]:
    """Keep OpenSearch/API relevance order (same as website). Dedupe + cap only."""
    products = [c for c in cards if c.get("type") == "product"]
    others = [c for c in cards if c.get("type") != "product"]
    ranked = _dedupe_product_variants(products, _to_text(user_query))[:8]
    for i, item in enumerate(ranked):
        item = ranked[i] = dict(item)
        item.pop("_score", None)
        item["featured"] = i < 2
    # Keep feature_filters after products
    feature_blocks = [c for c in others if c.get("type") == "feature_filters"]
    rest = [c for c in others if c.get("type") != "feature_filters"]
    return ranked + feature_blocks + rest


def _token_in_text(hay: str, key: str) -> bool:
    """Word-boundary match so short tokens don't match inside longer words."""
    import re

    key = (key or "").strip().lower()
    if not key:
        return False
    pattern = re.escape(key).replace(r"\ ", r"[\s\-]+")
    return bool(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", hay.lower()))


def normalize_product_query(text: Any) -> str:
    """Whitespace-only normalize. AI forms meaning — no static filler/keyword maps."""
    import re

    raw = _to_text(text).strip()
    if not raw:
        return raw
    return re.sub(r"\s+", " ", raw).strip()


def detect_phrase_intent(_text: str) -> dict | None:
    """Deprecated — no static phrase maps. AI + token relevance handle meaning."""
    return None


def split_browse_queries(text: Any) -> list[str]:
    """Split multi-item asks on and/aur/&/+ only — NOT bare commas (size/color lists)."""
    import re

    raw = _to_text(text).strip()
    if not raw:
        return []

    chunks = re.split(r"\s*(?:\band\b|\baur\b|&|\+)\s*", raw, flags=re.I)
    out: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        chunk = normalize_product_query(chunk)
        if not chunk or len(chunk) < 2:
            continue
        key = chunk.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(chunk)
    if not out:
        q = normalize_product_query(raw)
        if q:
            out = [q]
    return out[:6]


def product_relevance_score(product: dict, query: Any) -> float:
    """Token overlap helper (optional). Prefer API order for display ranking."""
    import re

    q = (normalize_product_query(query) or _to_text(query) or "").lower()
    q_tokens = {t for t in re.findall(r"[a-z0-9]+", q) if len(t) >= 2}
    if not q_tokens:
        return 0.0
    name = (product.get("name") or "").lower()
    color = (product.get("color") or "").lower()
    hay = f"{name} {color}"
    hay_tokens = set(re.findall(r"[a-z0-9]+", hay))
    overlap = 0.0
    for t in q_tokens:
        if _token_in_text(hay, t) or t in hay_tokens:
            overlap += 2.0 if len(t) >= 3 else 1.0
        elif t.endswith("s") and t[:-1] in hay_tokens:
            overlap += 1.5
        elif f"{t}s" in hay_tokens:
            overlap += 1.5
    if overlap <= 0:
        return 0.0
    return overlap


def _rank_products_by_query(cards: list[dict], query: Any) -> list[dict]:
    """Preserve API order — OpenSearch already ranked by relevance like the website."""
    return _rank_products_for_user(cards, query)


def _dedupe_product_variants(products: list[dict], query: Any = "") -> list[dict]:
    """Collapse same product shown once per size into one card (prefer matching size)."""
    import re

    if len(products) <= 1:
        return products
    q = (_to_text(query) or "").lower()
    size_re = re.compile(r"\b(xxxl|xxl|xl|xs|xxs|2xl|3xl|4xl|s|m|l)\b", re.I)
    want_sizes = size_re.findall(q)

    def base_key(p: dict) -> str:
        name = (p.get("name") or "").lower()
        slug = (p.get("slug") or "").lower()
        base = name or slug
        base = re.sub(
            r"[-_\s]?(xxxl|xxl|xl|xs|xxs|2xl|3xl|4xl|freesize|free size|\b[sml]\b)",
            " ",
            base,
            flags=re.I,
        )
        base = re.sub(r"\s+", " ", base).strip()
        return base[:80] or str(p.get("id") or slug or id(p))

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for p in products:
        k = base_key(p)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(p)

    out: list[dict] = []
    for k in order:
        items = groups[k]
        if len(items) == 1:
            out.append(items[0])
            continue
        picked = None
        if want_sizes:
            for p in items:
                size = (p.get("size") or "").lower()
                name = (p.get("name") or "").lower()
                if any(sz.lower() in size or sz.lower() in name for sz in want_sizes):
                    picked = p
                    break
        out.append(picked or items[0])
    return out


def strip_product_id_dumps(text: str) -> str:
    """Remove raw product id arrays the model sometimes dumps into chat text."""
    if not text:
        return text

    import re

    marker = "<<<CARDS>>>"
    text = text.replace(marker, "\x00CARDS\x00")

    # [2619217, 2619412, 2619411] or glued <<<CARDS>>>[…]
    text = re.sub(r"\[\s*\d{5,}(?:\s*,\s*\d{5,})*\s*\]", "", text)
    # Lines that are only comma-separated long ids
    text = re.sub(r"(?m)^\s*\d{5,}(?:\s*,\s*\d{5,})+\s*$", "", text)
    # product_id: 2619217 / id=2619217
    text = re.sub(
        r"(?i)\b(?:product[_\s-]?ids?|pro[_\s-]?ids?|stock[_\s-]?ids?|ids?)\s*[:=]\s*[\d,\s]+",
        "",
        text,
    )
    text = text.replace("\x00CARDS\x00", marker)
    # Category labels left empty after id wipe (Shoes: / T-shirts:)
    text = re.sub(r"(?mi)^\s*[A-Za-z][\w &+\-/]{0,48}:\s*$", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def strip_redundant_lists(text: str) -> str:
    """Clean assistant text: drop image markdown/URLs and noisy product/order dumps.

    Only strips catalog-like dumps (prices / order markers). Keeps normal FAQ
    explanations, numbered how-to lists, and feature bullets.
    """
    if not text:
        return text

    import re

    text = strip_product_id_dumps(text)

    # Remove markdown images and bare image URLs — UI cards show photos
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(
        r"https?://(?:image\.welfog\.com|d1f02fefkbso7w\.cloudfront\.net|welfog\.com)[^\s)]+",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    lines = text.splitlines()
    # If lots of **Order ID** / **Total** style lines, keep only preamble
    marker_hits = sum(
        1
        for ln in lines
        if any(
            x in ln.lower()
            for x in ("**order id**", "**total**", "**delivery", "**payment", "order id:")
        )
    )
    # Product catalogs only — require price/size signals (do NOT count plain FAQ lists)
    price_re = re.compile(r"₹|\brs\.?\s*\d", re.I)
    catalog_hits = sum(
        1
        for ln in lines
        if (
            re.match(r"^\s*\d+[\.\)]\s+", ln)
            and price_re.search(ln)
        )
        or (
            re.match(r"^\s*#{1,3}\s+", ln.strip())
            and price_re.search(ln)
        )
        or (price_re.search(ln) and len(ln) < 160)
    )
    if marker_hits >= 3 or catalog_hits >= 2:
        kept = []
        for ln in lines:
            low = ln.lower().strip()
            if any(
                x in low
                for x in (
                    "**order id**",
                    "**total**",
                    "**delivery",
                    "**payment",
                    "- **",
                    "order id:",
                    "![image]",
                )
            ):
                continue
            # Drop numbered/heading lines only when they look like priced products
            if re.match(r"^\s*\d+[\.\)]\s+", ln.strip()) and price_re.search(ln):
                continue
            if re.match(r"^\s*#{1,3}\s+", ln.strip()) and price_re.search(ln):
                continue
            if price_re.search(ln) and len(ln) < 160:
                continue
            if (
                re.match(r"^\s*[-*]\s+", ln.strip())
                and price_re.search(ln)
                and len(ln) < 180
            ):
                continue
            kept.append(ln)
        cleaned = "\n".join(kept).strip()
        return cleaned
    return text
