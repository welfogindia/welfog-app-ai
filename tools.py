"""OpenAI function tools that call Welfog APIs."""

from __future__ import annotations

import json
from typing import Any

from api_client import api
from play import PLAY_TOOLS, execute_play_tool, is_play_tool
from session import session

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_login_otp",
            "description": "Send OTP to a customer's phone number for login. Required before any personal account data (orders, cart, profile, wishlist, addresses).",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "10-digit Indian mobile number without +91",
                    }
                },
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_login_otp",
            "description": "Verify OTP and log the user in. Call after send_login_otp when user provides the OTP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "10-digit mobile used for send_login_otp. Optional if already sent."},
                    "otp": {"type": "string", "description": "6-digit OTP"},
                },
                "required": ["otp"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "logout",
            "description": "Clear the current login session.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_status",
            "description": "Check if user is logged in and return session info (user_id, name, phone).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_company_knowledge",
            "description": (
                "Search LIVE Welfog company knowledge (policies, FAQs, refund, shipping, "
                "about brand, bank account rules, support facts). "
                "ALWAYS use this for company/policy questions — do NOT invent facts. "
                "Pass the user's question as query. Returns instruction + context for your answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User question / search text",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results 1–20, default 5",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search Welfog product catalog on OpenSearch index products_v1 "
                "(https://s.welfog.com — same catalog as the website). "
                "YOU understand the user (language, typos, product type, color, size, brand, category, budget, features). "
                "Pass product meaning in `name` (e.g. 'red t shirt'). Pass color/size/brand/category when asked — "
                "they are SECONDARY ranking boosts; product type in `name` always wins (red ball will not beat t-shirt). "
                "Results include unique feature_filters from each product's pro_features (duplicates collapsed). "
                "When user picks a feature filter (e.g. Material: Cotton / Pattern: Solid), pass feature_key + "
                "feature_value and keep the same product `name` — filtering is applied on returned hits. "
                "After results, read match_meta / feature_filters. Never invent products. "
                "size=20, best score first. Multi-item message → one call per item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Search phrase YOU formed from user meaning "
                            "(product type + optional color words, fix typos)"
                        ),
                    },
                    "page": {"type": "integer", "description": "Page number, default 1 (20 per page)"},
                    "min_price": {"type": "number", "description": "Optional minimum unit_price filter"},
                    "max_price": {"type": "number", "description": "Optional maximum unit_price filter"},
                    "color": {
                        "type": "string",
                        "description": "Optional color the user wants (boosts color_name / name)",
                    },
                    "size": {
                        "type": "string",
                        "description": "Optional size the user wants (boosts size keyword)",
                    },
                    "brand": {
                        "type": "string",
                        "description": "Optional brand the user wants (boosts brand / name)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category name if user named one (boosts category_name)",
                    },
                    "feature_key": {
                        "type": "string",
                        "description": (
                            "Optional pro_features key to filter (e.g. Material, Type, Fabric). "
                            "Use when user picks a feature chip or names a feature attribute."
                        ),
                    },
                    "feature_value": {
                        "type": "string",
                        "description": (
                            "Optional pro_features value to filter (e.g. Cotton, Plastic, Soft Case). "
                            "Pair with feature_key when possible."
                        ),
                    },
                    "sort_key": {
                        "type": "string",
                        "description": "Ignored for OpenSearch relevance sort (kept for compatibility)",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "autosuggest",
            "description": "Get product name suggestions for a partial search query.",
            "parameters": {
                "type": "object",
                "properties": {"search": {"type": "string"}},
                "required": ["search"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Get full product details by product slug or id/slug path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Product slug from search results (or product id/slug)",
                    }
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_related_products",
            "description": "Get related products for a product id.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_deals",
            "description": "Fetch today's deals / deals of the day products.",
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_banners",
            "description": "Get homepage/category banners.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "category_id": {"type": "string"},
                    "device": {
                        "type": "string",
                        "description": "mobile | desktop | mobile_app etc.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_faqs",
            "description": "Get Welfog FAQs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shop_details",
            "description": "Get seller/shop details by shop id.",
            "parameters": {
                "type": "object",
                "properties": {"shop_id": {"type": "string"}},
                "required": ["shop_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_pincode_service",
            "description": "Check if Welfog delivers to a pincode / get pincode city-state info.",
            "parameters": {
                "type": "object",
                "properties": {"pincode": {"type": "string"}},
                "required": ["pincode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_reviews",
            "description": "Get reviews for a product id.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_contact",
            "description": (
                "Submit a contact/support message to Welfog after the user provides "
                "name, email, and issue (phone optional) — ideally all in one reply. "
                "Use when user wants to contact Welfog support for any help or query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["name", "email", "message"],
            },
        },
    },
    # ----- Authenticated user tools -----
    {
        "type": "function",
        "function": {
            "name": "get_my_profile",
            "description": "Get logged-in user's profile (name, email, phone, dob, gender, marital_status). Requires login.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_my_profile",
            "description": "Update logged-in user's profile fields EXCEPT phone (phone cannot be changed here). Pass only fields the user wants to change: name, email, dob (YYYY-MM-DD), gender, marital_status. Requires login. Confirm values with user before calling if ambiguous.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "dob": {
                        "type": "string",
                        "description": "Date of birth as YYYY-MM-DD",
                    },
                    "gender": {
                        "type": "string",
                        "description": "e.g. Male / Female / Other",
                    },
                    "marital_status": {
                        "type": "string",
                        "description": "e.g. Single / Married",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": (
                "Add product to cart via /api/crux/addcart. Needs product_id (= pro_id from search). "
                "Prefer also passing stock_id (search data.id / stocks[0].id) and delivery_time_minute "
                "(search duration). Max qty 2. Requires login."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Product pro_id from search/details (NOT postgres row id)",
                    },
                    "quantity": {"type": "integer", "description": "Default 1, max typically 2"},
                    "stock_id": {
                        "type": "integer",
                        "description": "Variant/stock id = Postgres products.id from search data.id or stocks[0].id",
                    },
                    "delivery_time_minute": {
                        "type": "integer",
                        "description": "Delivery duration in minutes from search (duration field)",
                    },
                    "buy_now": {
                        "type": "boolean",
                        "description": "If true, treat as buy-now qty",
                    },
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_cart",
            "description": "Remove one cart line. Needs cart_item_id from get_my_cart (field cart_item_id / id). Requires login.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cart_item_id": {
                        "type": "integer",
                        "description": "Cart row id from get_my_cart",
                    },
                },
                "required": ["cart_item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_cart_quantity",
            "description": "Change quantity of a cart line. Needs cart_item_id from get_my_cart and new quantity. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cart_item_id": {"type": "integer"},
                    "quantity": {"type": "integer"},
                },
                "required": ["cart_item_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_wishlist",
            "description": "Add product to wishlist by product_id. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_wishlist",
            "description": "Remove product from wishlist by product_id. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "select_address",
            "description": "Mark a saved address as selected/default for checkout. Needs address_id from get_my_addresses. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {"address_id": {"type": "integer"}},
                "required": ["address_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_coupon",
            "description": "Apply a coupon code to the logged-in user's cart. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {"coupon_code": {"type": "string"}},
                "required": ["coupon_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_orders",
            "description": "List logged-in user's orders (basic). Prefer get_purchase_history for richer order cards with product title/image/status. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer"},
                    "delivery_status": {"type": "string"},
                    "payment_status": {"type": "string"},
                    "order_id": {
                        "type": "string",
                        "description": "Optional specific order id",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_purchase_history",
            "description": "Order history / my orders. Calls GET /api/v2/purchase-history/{user_id}?user_id={user_id}&page=1. Each item has product_title, product_img, current_order_status, grand_total, date, payment_status_string. ALWAYS use this for orders list. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer"},
                    "delivery_status": {"type": "string"},
                    "payment_status": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": "Full details for ONE order. Calls purchase-history-details + purchase-history-items with user_id. Use when user asks about a specific order id / tracking / kab aayega / detail. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_cart",
            "description": "Get cart items for logged-in user. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cart_summary",
            "description": "Get cart price summary (totals) for logged-in user. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {"payment_type": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_wishlist",
            "description": "Get wishlist products for logged-in user. API GET /api/v2/wishlists/{user_id}. Response items have nested product{name, thumbnail_image, base_price, selling_price}. Requires login.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_addresses",
            "description": "Get saved addresses for logged-in user. Requires login.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_notifications",
            "description": "Get notifications for logged-in user. Requires login.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer"},
                    "year": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_order",
            "description": "Cancel an order for the logged-in user. Requires login. Confirm reason with user first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_snapshot",
            "description": "Get account snapshot via access token (cart count, wishlist count, notifications, address). Requires login.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

TOOLS.extend(PLAY_TOOLS)


def _compact_cart(raw: Any) -> Any:
    """Flatten shops[].cart_items into a simple list for the agent."""
    if isinstance(raw, dict) and (raw.get("error") or raw.get("result") is False):
        return raw
    shops = raw if isinstance(raw, list) else []
    if isinstance(raw, dict):
        shops = raw.get("data") or raw.get("shops") or []
        if not shops and isinstance(raw.get("cart_items"), list):
            shops = [{"name": "Cart", "cart_items": raw["cart_items"]}]
    items = []
    for shop in shops or []:
        if not isinstance(shop, dict):
            continue
        shop_name = shop.get("name") or "Shop"
        for it in shop.get("cart_items") or []:
            if not isinstance(it, dict):
                continue
            items.append(
                {
                    "cart_item_id": it.get("id"),
                    "product_id": it.get("product_id"),
                    "name": it.get("product_name") or it.get("name"),
                    "slug": it.get("slug"),
                    "quantity": it.get("quantity"),
                    "price": it.get("price"),
                    "mrp": it.get("mrp"),
                    "size": it.get("size"),
                    "variation": it.get("variation"),
                    "shop": shop_name,
                    "thumbnail": it.get("product_thumbnail_image"),
                }
            )
    return {"count": len(items), "items": items}


def _need_auth() -> dict | None:
    if not session.is_authenticated:
        return {
            "error": True,
            "needs_login": True,
            "message": "User is not logged in. Ask for phone number, call send_login_otp, then verify_login_otp.",
        }
    return None


def _clean_phone(phone: str) -> str:
    digits = "".join(c for c in str(phone) if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits


def _pick_product(p: dict) -> dict:
    nested = p.get("data") if isinstance(p.get("data"), dict) else {}
    keys = (
        "id",
        "pro_id",
        "pid",
        "name",
        "slug",
        "url",
        "unit_price",
        "purchase_price",
        "price",
        "discounted_price",
        "main_price",
        "stroked_price",
        "selling_price",
        "base_price",
        "new_price",
        "old_price",
        "has_discount",
        "rating",
        "shop_name",
        "shop_id",
        "thumbnail_image",
        "thumbnail_img",
        "thumb_url",
        "product_img",
        "image",
        "stocks",
        "current_stock",
        "category_name",
        "color_name",
        "size",
        "colors",
        "brand",
        "duration",
        "delivery_time",
        "delivery_time_minute",
        "pro_features",
    )
    out = {k: p[k] for k in keys if isinstance(p, dict) and k in p and p[k] not in (None, "")}
    for k in (
        "color_name",
        "size",
        "colors",
        "unit_price",
        "purchase_price",
        "stock",
        "duration",
        "delivery_time",
        "delivery_time_minute",
        "id",
    ):
        if k not in out and nested.get(k) not in (None, ""):
            out[k] = nested[k]
    # Normalize image + price aliases used by today_deal / search / wishlist
    thumb = (
        out.get("thumbnail_image")
        or out.get("thumbnail_img")
        or out.get("thumb_url")
        or out.get("product_img")
        or out.get("image")
    )
    if thumb:
        out["thumbnail_image"] = thumb
        out["thumbnail_img"] = thumb
    sell = (
        out.get("selling_price")
        if out.get("selling_price") not in (None, "")
        else out.get("new_price")
        if out.get("new_price") not in (None, "")
        else out.get("main_price")
        if out.get("main_price") not in (None, "")
        else out.get("discounted_price")
        or out.get("price")
        or out.get("purchase_price")
    )
    mrp = (
        out.get("base_price")
        if out.get("base_price") not in (None, "")
        else out.get("old_price")
        if out.get("old_price") not in (None, "")
        else out.get("stroked_price")
        or out.get("unit_price")
    )
    if sell not in (None, ""):
        out["main_price"] = sell
        out["selling_price"] = sell
        out["new_price"] = sell
    if mrp not in (None, ""):
        out["stroked_price"] = mrp
        out["base_price"] = mrp
        out["old_price"] = mrp
    if not out.get("slug") and out.get("url"):
        out["slug"] = out["url"]

    # pro_id = catalog id for cart product_id
    pro = p.get("pro_id") or p.get("pid") or nested.get("pro_id")
    if pro in (None, "") and p.get("id") not in (None, ""):
        # search API puts pro_id in outer id
        pro = p.get("id")
    # stockId = Postgres row id (search nests it in data.id / stocks[0].id)
    stock_id = None
    stocks = p.get("stocks") or nested.get("stocks")
    if isinstance(stocks, list) and stocks and isinstance(stocks[0], dict):
        stock_id = stocks[0].get("id")
    if stock_id in (None, ""):
        stock_id = nested.get("id")  # search: data.id is PG id
    if stock_id in (None, "") and nested:
        # details sometimes expose product_id as PG id
        stock_id = nested.get("product_id")

    if pro not in (None, ""):
        try:
            pro_int = int(pro)
            out["pro_id"] = pro_int
            out["pid"] = pro_int
            out["id"] = pro_int
            out["product_id"] = pro_int
        except (TypeError, ValueError):
            out["id"] = pro
            out["pro_id"] = pro
            out["product_id"] = pro
    if stock_id not in (None, ""):
        out["stock_id"] = stock_id
        out["stockId"] = stock_id

    # delivery minutes from search duration (or explicit field)
    dur = (
        out.get("delivery_time_minute")
        or out.get("duration")
        or nested.get("duration")
        or nested.get("delivery_time_minute")
        or p.get("duration")
    )
    if dur not in (None, ""):
        try:
            out["delivery_time_minute"] = int(float(dur))
        except (TypeError, ValueError):
            out["delivery_time_minute"] = dur

    if not out and isinstance(p, dict):
        for k, v in list(p.items())[:12]:
            if isinstance(v, (str, int, float, bool)):
                out[k] = v
    return out


def _compact_products(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return raw
    if raw.get("truncated") and isinstance(raw.get("preview"), str):
        # last-resort: try parse preview if client had to truncate hard
        try:
            raw = json.loads(raw["preview"])
        except Exception:
            return raw
    products = raw.get("products") or raw.get("data") or []
    if isinstance(products, dict):
        products = products.get("data") or products.get("products") or []
    if not isinstance(products, list):
        return raw
    # API returns ~20/page; keep enough for ranking, UI later caps ~8 cards
    compact = [_pick_product(p) for p in products[:20] if isinstance(p, dict)]
    out = {
        "result": raw.get("result", True),
        "total": raw.get("total") or raw.get("count_products") or len(products),
        "page": raw.get("page"),
        "products": compact,
        "message": raw.get("message"),
        "meta_truncated": raw.get("_truncated"),
    }
    if isinstance(raw.get("feature_filters"), dict):
        out["feature_filters"] = raw["feature_filters"]
    if raw.get("applied_feature"):
        out["applied_feature"] = raw["applied_feature"]
    return out


def _compact_orders(raw: Any, *, with_tracking: bool = False) -> Any:
    """Keep only fields needed for order cards / tracking UI."""
    if not isinstance(raw, dict):
        return raw
    rows = raw.get("data") or raw.get("orders") or []
    if isinstance(rows, dict):
        rows = rows.get("data") or []
    if not rows and (raw.get("id") or raw.get("oid") or raw.get("product_title") or raw.get("name")):
        rows = [raw]
    if not isinstance(rows, list):
        return raw

    compact = []
    for row in rows[:12]:
        if not isinstance(row, dict):
            continue
        # product name: product_title preferred, else name
        title = row.get("product_title") or row.get("name") or row.get("product_name")
        item = {
            "id": row.get("id") or row.get("oid"),
            "oid": row.get("oid") or row.get("id"),
            "product_id": row.get("product_id"),
            "product_title": title,
            "name": title,
            "product_slug": row.get("product_slug") or row.get("slug"),
            "product_img": row.get("product_img") or row.get("thumbnail_image"),
            "grand_total": row.get("grand_total"),
            "date": row.get("date") or row.get("created_at"),
            "current_order_status": row.get("current_order_status"),
            "payment_status_string": row.get("payment_status_string"),
            "payment_type": row.get("payment_type"),
            "tracking_code": row.get("tracking_code"),
            # intentionally omit delivery_status / delivery_status_string
        }
        if with_tracking or len(rows) == 1:
            item["order_status_detail"] = row.get("order_status_detail")
        compact.append(item)

    return {
        "success": raw.get("success", True),
        "status": raw.get("status", 200),
        "data": compact,
        "meta": raw.get("meta"),
    }


def _compact_wishlist(raw: Any) -> Any:
    """Flatten wishlist API {data:[{id, product:{...}}]} for UI cards."""
    if not isinstance(raw, dict):
        return raw
    rows = raw.get("data") or []
    if not isinstance(rows, list):
        return raw
    products = []
    for row in rows[:18]:
        if not isinstance(row, dict):
            continue
        p = row.get("product") if isinstance(row.get("product"), dict) else None
        if not p:
            continue
        products.append(
            {
                "id": p.get("id"),
                "wishlist_id": row.get("id"),
                "name": p.get("name"),
                "slug": p.get("link") or p.get("slug"),
                "link": p.get("link"),
                "thumbnail_image": p.get("thumbnail_image"),
                "base_price": p.get("base_price"),
                "selling_price": p.get("selling_price"),
                "stock": p.get("stock"),
            }
        )
    return {
        "success": raw.get("success", True),
        "status": raw.get("status", 200),
        "products": products,
        "data": products,
    }


def _first_row(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    rows = raw.get("data")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0]
    if raw.get("id") or raw.get("oid"):
        return raw
    return None


def _fetch_order_full_detail(order_id: str | int, user_id: int | str) -> dict:
    """
    Merge:
      GET /api/v2/purchase-history-details/{id}?user_id=
      GET /api/v2/purchase-history-items/{id}?user_id=
    """
    oid = str(order_id).strip()
    params = {"user_id": user_id}
    details = api.get(
        f"/api/v2/purchase-history-details/{oid}",
        params=params,
        auth=True,
        trim=False,
    )
    items = api.get(
        f"/api/v2/purchase-history-items/{oid}",
        params=params,
        auth=True,
        trim=False,
    )
    detail = _first_row(details) or {}
    item_rows = []
    if isinstance(items, dict) and isinstance(items.get("data"), list):
        item_rows = [r for r in items["data"] if isinstance(r, dict)]
    elif isinstance(items, dict) and items.get("product_name"):
        item_rows = [items]

    first_item = item_rows[0] if item_rows else {}
    product_name = (
        first_item.get("product_name")
        or detail.get("product_title")
        or detail.get("name")
    )
    addr = detail.get("shipping_address") if isinstance(detail.get("shipping_address"), dict) else {}

    return {
        "detail_mode": True,
        "success": True,
        "order": {
            "id": detail.get("id") or detail.get("oid") or oid,
            "oid": detail.get("oid") or detail.get("id") or oid,
            "date": detail.get("date"),
            "current_order_status": detail.get("current_order_status"),
            "grand_total": detail.get("grand_total"),
            "subtotal": detail.get("subtotal"),
            "shipping_cost": detail.get("shipping_cost"),
            "cod_cost": detail.get("cod_cost"),
            "coupon_discount": detail.get("coupon_discount"),
            "tax": detail.get("tax"),
            "payment_type": detail.get("payment_type") or detail.get("payment_mode"),
            "payment_status_string": detail.get("payment_status_string"),
            "payment_status": detail.get("payment_status"),
            "shipping_type_string": detail.get("shipping_type_string"),
            "product_img": detail.get("product_img"),
            "size": detail.get("size") or first_item.get("variation") or first_item.get("size"),
            "color": detail.get("color"),
            "product_name": product_name,
            "quantity": first_item.get("quantity") or 1,
            "unit_price": first_item.get("unit_price") or first_item.get("price"),
            "tracking_code": detail.get("tracking_code"),
            "order_status_detail": detail.get("order_status_detail"),
            "shipping_address": {
                "name": addr.get("name"),
                "phone": addr.get("phone"),
                "email": addr.get("email"),
                "address": addr.get("address"),
                "city": addr.get("city"),
                "state": addr.get("state"),
                "postal_code": addr.get("postal_code"),
                "country": addr.get("country"),
            },
            "items": [
                {
                    "product_id": it.get("product_id"),
                    "product_name": it.get("product_name"),
                    "slug": it.get("slug"),
                    "variation": it.get("variation") or it.get("size"),
                    "unit_price": it.get("unit_price"),
                    "price": it.get("price"),
                    "quantity": it.get("quantity"),
                    "shipping_cost": it.get("shipping_cost"),
                }
                for it in item_rows
            ],
        },
    }


def execute_tool(name: str, args: dict) -> Any:
    args = args or {}
    try:
        return _execute_tool_body(name, args)
    except KeyError as err:
        missing = err.args[0] if err.args else "argument"
        return {
            "error": True,
            "message": f"Missing required argument: {missing}. Ask the user or use an id from the last search/details result.",
        }
    except (TypeError, ValueError) as err:
        return {"error": True, "message": f"Invalid tool arguments: {err}"}


def _execute_tool_body(name: str, args: dict) -> Any:
    if is_play_tool(name):
        return execute_play_tool(name, args)

    if name == "send_login_otp":
        phone = _clean_phone(args.get("phone", ""))
        if len(phone) != 10:
            return {"error": True, "message": "Phone must be a 10-digit Indian number"}
        result = api.get("/api/v2/buyerverifynumber", params={"phone": phone})
        ok = False
        if isinstance(result, dict):
            msg = str(result.get("message") or "").lower()
            ok = (
                result.get("return") is True
                or result.get("result") in (True, "true", "True")
                or "otp" in msg
                or "successfully" in msg
            )
        if ok:
            session.phone = phone
            session.otp_pending = True
        return {
            "ok": ok,
            "phone": phone,
            "api_response": result,
            "next_step": "Ask user for the OTP, then call verify_login_otp",
        }

    if name == "verify_login_otp":
        phone = _clean_phone(args.get("phone") or session.phone or "")
        otp = str(args.get("otp", "")).strip()
        if not phone or not otp:
            return {"error": True, "message": "phone and otp are required"}
        result = api.get(
            "/api/v2/usercheckVerifyOtp",
            params={"phone": phone, "otp": otp, "web": "false"},
        )
        if isinstance(result, dict) and result.get("result") is True and result.get("access_token"):
            session.set_from_login(result)
            return {
                "ok": True,
                "message": result.get("message"),
                "user": result.get("user"),
                "session": session.summary(),
            }
        return {"ok": False, "api_response": result}

    if name == "logout":
        session.clear()
        return {"ok": True, "message": "Logged out"}

    if name == "get_session_status":
        return session.summary()

    if name == "search_company_knowledge":
        from aidata_search import search_company_knowledge as _aidata_search

        q = str(args.get("query") or "").strip()
        lim = int(args.get("limit") or 5)
        data = _aidata_search(q, limit=lim)
        # Compact payload for Gemini — instruction + context are the main fields
        return {
            "ok": data.get("ok"),
            "found": data.get("found"),
            "instruction": data.get("instruction"),
            "context": data.get("context"),
            "results": data.get("results") or [],
            "error": data.get("error"),
            "note": (
                "Answer using instruction + context only. "
                "If found=0, say you do not have enough company information — do not invent."
            ),
        }

    if name == "search_products":
        import re

        from opensearch_products import search_products_os

        # Direct OpenSearch products_v1 — AI forms meaning; no REST /products/search.
        raw_name = re.sub(r"\s+", " ", str(args.get("name") or "").strip())
        color_arg = re.sub(r"\s+", " ", str(args.get("color") or "").strip()) or None
        size_arg = re.sub(r"\s+", " ", str(args.get("size") or "").strip()) or None
        brand_arg = re.sub(r"\s+", " ", str(args.get("brand") or "").strip()) or None
        category_arg = re.sub(r"\s+", " ", str(args.get("category") or "").strip()) or None
        feature_key_arg = re.sub(r"\s+", " ", str(args.get("feature_key") or "").strip()) or None
        feature_value_arg = re.sub(r"\s+", " ", str(args.get("feature_value") or "").strip()) or None

        # Chip click: "Filter sneakers by Color: White" / "Filter by Pattern: Solid"
        m_filt = re.match(
            r"(?i)^(?:filter\s+)?(.+?)\s+by\s+(.+?)\s*:\s*(.+)$",
            raw_name,
        )
        if not m_filt:
            m_filt = re.match(r"(?i)^filter\s+by\s+(.+?)\s*:\s*(.+)$", raw_name)
            if m_filt:
                if not feature_key_arg:
                    feature_key_arg = m_filt.group(1).strip()
                if not feature_value_arg:
                    feature_value_arg = m_filt.group(2).strip()
                raw_name = ""
        elif m_filt:
            prod_bit = m_filt.group(1).strip()
            if prod_bit.lower() != "filter":
                raw_name = re.sub(r"(?i)^filter\s+", "", prod_bit).strip() or prod_bit
            else:
                raw_name = ""
            if not feature_key_arg:
                feature_key_arg = m_filt.group(2).strip()
            if not feature_value_arg:
                feature_value_arg = m_filt.group(3).strip()

        # Map Color/Size feature chips onto existing color/size search args
        fk_l = (feature_key_arg or "").lower()
        if feature_value_arg and fk_l in ("color", "colour", "colors") and not color_arg:
            color_arg = feature_value_arg
        if feature_value_arg and fk_l in ("size", "sizes") and not size_arg:
            size_arg = feature_value_arg
        clean_name = raw_name
        # If AI passed color separately and left it out of name, fold into text query too
        if color_arg and color_arg.lower() not in clean_name.lower():
            clean_name = f"{color_arg} {clean_name}".strip()

        generic = {
            "product",
            "products",
            "item",
            "items",
            "samaan",
            "cheez",
            "option",
            "options",
            "stuff",
            "goods",
            "category",
            "categories",
            "categor",
            "list",
            "listed",
            "welfog",
            "website",
            "site",
            "all",
            "see",
            "show",
            "want",
            "available",
        }
        tokens = {t for t in clean_name.lower().split() if t}
        if not clean_name.strip() or tokens <= generic:
            return {
                "error": True,
                "needs_clarification": True,
                "message": (
                    "Search query is too vague or is a category-list ask, not a product. "
                    "If user asked for categories, list categories in text only — do NOT show products. "
                    "Otherwise ask which product/category they want, then search again."
                ),
                "search_query": clean_name,
            }

        out = search_products_os(
            query=clean_name,
            page=int(args.get("page") or 1),
            color=color_arg,
            size_label=size_arg,
            brand=brand_arg,
            category=category_arg,
            feature_key=feature_key_arg,
            feature_value=feature_value_arg,
            min_price=args.get("min_price"),
            max_price=args.get("max_price"),
        )
        compact = _compact_products(out) if isinstance(out, dict) and not out.get("error") else out
        if isinstance(compact, dict):
            compact["search_query"] = clean_name
            if isinstance(out, dict):
                if out.get("product_core_query"):
                    compact["product_core_query"] = out["product_core_query"]
                if out.get("match_meta"):
                    compact["match_meta"] = out["match_meta"]
            if raw_name and raw_name.lower() != clean_name.lower():
                compact["search_query_original"] = raw_name
            if color_arg:
                compact["color"] = color_arg
            if size_arg:
                compact["size"] = size_arg
            if brand_arg:
                compact["brand"] = brand_arg
            if category_arg:
                compact["category"] = category_arg
            if feature_key_arg:
                compact["feature_key"] = feature_key_arg
            if feature_value_arg:
                compact["feature_value"] = feature_value_arg
            total = compact.get("total") or 0
            products = compact.get("products") or []
            meta = compact.get("match_meta") or {}
            hints = meta.get("hints") or []
            if total == 0 or not products:
                mode = (meta.get("mode") or "not_found")
                compact["mode"] = mode
                compact["note"] = (
                    "NOT FOUND — zero relevant products. Write a LONGER natural reply "
                    "(several sentences) in the user's language: clearly say the asked item "
                    "was not found, explain briefly, ask how to refine (similar type/color/budget). "
                    "Do NOT output <<<CARDS>>>. Do NOT invent products or show unrelated SKUs. "
                    + " ".join(hints)
                )
            else:
                compact["mode"] = meta.get("mode") or "matched"
                hint_txt = " ".join(hints) if hints else ""
                ff = compact.get("feature_filters") or {}
                ff_n = len((ff.get("items") or [])) if isinstance(ff, dict) else 0
                compact["note"] = (
                    "MATCHED results. Write a longer DESCRIBE intro (2–5 sentences) about what "
                    "you are showing, then <<<CARDS>>>, then 1–2 natural follow-up questions. "
                    "If match_meta hints say color/size missing, describe those as suggestions / "
                    "other options — never claim exact match. Never invent SKUs. "
                    f"UI shows unique feature_filters below cards ({ff_n} options) — mention "
                    "user can tap a feature to narrow results; do NOT dump the full feature list in text. "
                    "If user later picks a feature, re-call search_products with same name + feature_key/feature_value. "
                    + hint_txt
                )
        return compact

    if name == "autosuggest":
        return api.get("/api/v2/autosuggest", params={"search": args["search"]})

    if name == "get_product_details":
        slug = str(args["slug"]).lstrip("/")
        raw = api.get(f"/api/product_details/{slug}")
        if isinstance(raw, dict):
            data = raw.get("data") or raw.get("product") or raw
            if isinstance(data, dict):
                return {
                    "result": raw.get("result", True),
                    "product": _pick_product(data)
                    | {
                        k: data[k]
                        for k in (
                            "description",
                            "short_description",
                            "colors",
                            "size",
                            "varient",
                            "shipping_cost",
                            "delivery_time",
                        )
                        if k in data
                    },
                }
        return raw

    if name == "get_related_products":
        pid = args.get("product_id")
        if pid in (None, ""):
            return {
                "error": True,
                "message": "product_id required. Pick an id from search_products / get_product_details first.",
            }
        return _compact_products(api.get(f"/api/v2/products/related/{pid}"))

    if name == "get_today_deals":
        return _compact_products(api.get("/api/today_deal", params={"page": args.get("page") or 1}))

    if name == "get_banners":
        params = {}
        if args.get("type"):
            params["type"] = args["type"]
        if args.get("category_id"):
            params["category_id"] = args["category_id"]
        params["device"] = args.get("device") or "mobile"
        return api.get("/api/v2/banner/banner", params=params)

    if name == "get_faqs":
        return api.get("/api/v2/faqs")

    if name == "get_shop_details":
        return api.get(f"/api/v2/shops/details/{args['shop_id']}")

    if name == "check_pincode_service":
        pin = str(args["pincode"]).strip()
        info = api.get("/api/v2/pincode/info", params={"pincode": pin})
        delhivery = api.get(f"/api/v2/delhivery_api/{pin}")
        return {"pincode_info": info, "delhivery": delhivery}

    if name == "get_product_reviews":
        pid = args.get("product_id")
        if pid in (None, ""):
            return {"error": True, "message": "product_id required"}
        return api.get(f"/api/v2/reviews/product_review/{pid}")

    if name == "submit_contact":
        return api.post(
            "/api/contact",
            json_body={
                "name": args["name"],
                "email": args["email"],
                "phone": args.get("phone") or "",
                "message": args["message"],
            },
        )

    # Auth-required
    blocked = _need_auth()
    if blocked and name in {
        "get_my_profile",
        "update_my_profile",
        "get_my_orders",
        "get_purchase_history",
        "get_order_details",
        "get_my_cart",
        "get_cart_summary",
        "add_to_cart",
        "remove_from_cart",
        "update_cart_quantity",
        "get_my_wishlist",
        "add_to_wishlist",
        "remove_from_wishlist",
        "get_my_addresses",
        "select_address",
        "apply_coupon",
        "get_my_notifications",
        "cancel_order",
        "get_user_snapshot",
    }:
        return blocked

    uid = session.user_id

    if name == "get_my_profile":
        return api.get(f"/api/v2/profile/{uid}", auth=True)

    if name == "update_my_profile":
        # Phone is intentionally never updated via this tool.
        # Production profile/update used to SET every column; omitted fields became NULL.
        # Always merge with current profile so one-field edits keep name/email/etc.
        current: dict[str, Any] = {}
        existing = api.get(f"/api/v2/profile/{uid}", auth=True)
        if isinstance(existing, dict) and isinstance(existing.get("data"), dict):
            current = existing["data"]

        body: dict[str, Any] = {"id": uid, "password": ""}
        for key in ("name", "email", "dob", "gender", "marital_status"):
            cur = current.get(key)
            if cur is not None and str(cur).strip() != "":
                body[key] = str(cur).strip()
        # Session name as fallback if DB name was already wiped by a bad prior update
        if not body.get("name") and session.user_name:
            body["name"] = str(session.user_name).strip()

        changed_keys: list[str] = []
        for key in ("name", "email", "dob", "gender", "marital_status"):
            val = args.get(key)
            if val is not None and str(val).strip() != "":
                body[key] = str(val).strip()
                changed_keys.append(key)

        if not changed_keys:
            return {
                "error": True,
                "message": "Provide at least one field to update (name, email, dob, gender, marital_status). Phone cannot be changed here.",
            }

        result = api.post("/api/v2/profile/update", json_body=body, auth=True)
        # Refresh profile for UI + session
        profile = api.get(f"/api/v2/profile/{uid}", auth=True)
        if isinstance(profile, dict) and isinstance(profile.get("data"), dict):
            data = profile["data"]
            if data.get("name"):
                session.user_name = data.get("name")
            if data.get("email"):
                session.user_email = data.get("email")
        return {
            "ok": isinstance(result, dict) and result.get("result") is True,
            "updated_fields": changed_keys,
            "update_response": result,
            "profile": profile,
            "note": "Only requested fields were changed; other profile fields were preserved. Phone cannot be changed via this tool.",
        }

    if name == "get_my_orders":
        # Exact API: /api/v2/purchase-history/{user_id}?user_id=&page=
        params = {"user_id": uid, "page": args.get("page") or 1}
        if args.get("delivery_status"):
            params["delivery_status"] = args["delivery_status"]
        if args.get("payment_status"):
            params["payment_status"] = args["payment_status"]
        raw = api.get(
            f"/api/v2/purchase-history/{uid}",
            params=params,
            auth=True,
            trim=False,
        )
        oid = args.get("order_id")
        if oid and isinstance(raw, dict) and isinstance(raw.get("data"), list):
            want = str(oid)
            raw = {
                **raw,
                "data": [
                    r
                    for r in raw["data"]
                    if str(r.get("id") or r.get("oid") or "") == want
                ],
            }
        return _compact_orders(raw, with_tracking=bool(oid))

    if name == "get_purchase_history":
        # https://welfogapi.welfog.com/api/v2/purchase-history/{user_id}?user_id=&page=1
        params = {"user_id": uid, "page": args.get("page") or 1}
        if args.get("delivery_status"):
            params["delivery_status"] = args["delivery_status"]
        if args.get("payment_status"):
            params["payment_status"] = args["payment_status"]
        return _compact_orders(
            api.get(
                f"/api/v2/purchase-history/{uid}",
                params=params,
                auth=True,
                trim=False,
            ),
            with_tracking=False,
        )

    if name == "get_order_details":
        return _fetch_order_full_detail(args["order_id"], uid)

    if name == "get_my_cart":
        body = {
            "user_latitude": args.get("latitude"),
            "user_longitude": args.get("longitude"),
        }
        raw = api.post(f"/api/v2/carts/{uid}", json_body=body, auth=True, trim=False)
        return _compact_cart(raw)

    if name == "get_cart_summary":
        params = {}
        if args.get("payment_type"):
            params["payment_type"] = args["payment_type"]
        return api.get(f"/api/v2/cart-summary/{uid}", params=params, auth=True)

    if name == "add_to_cart":
        raw_pid = args.get("product_id") or args.get("pro_id") or args.get("id")
        if raw_pid in (None, ""):
            return {
                "error": True,
                "message": "product_id (pro_id) required from search/details before add_to_cart",
            }
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            return {"error": True, "message": f"Invalid product_id: {raw_pid}"}

        qty = int(args.get("quantity") or 1)
        if qty < 1:
            qty = 1
        if qty > 2:
            qty = 2

        stock_id = args.get("stock_id") or args.get("stockId")
        delivery_min = args.get("delivery_time_minute")

        # Website payload needs stockId (PG row id) + delivery minutes — resolve from search if missing
        if stock_id in (None, "") or delivery_min in (None, "", 0, "0"):
            try:
                looked = api.get(
                    "/api/v2/products/search",
                    params={"name": str(pid), "page": 1},
                    trim=False,
                )
                rows = []
                if isinstance(looked, dict):
                    rows = looked.get("products") or looked.get("data") or []
                    if isinstance(rows, dict):
                        rows = rows.get("data") or rows.get("products") or []
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        picked = _pick_product(row)
                        if int(picked.get("pro_id") or picked.get("id") or 0) != pid:
                            continue
                        if stock_id in (None, ""):
                            stock_id = picked.get("stock_id") or picked.get("stockId")
                        if delivery_min in (None, "", 0, "0"):
                            delivery_min = picked.get("delivery_time_minute") or picked.get(
                                "duration"
                            )
                        break
            except Exception as err:
                print(f"[cart] lookup failed: {err}")

        if stock_id in (None, ""):
            return {
                "error": True,
                "message": (
                    "stockId missing for this product. Call get_product_details or search again, "
                    "then pass stock_id from the product (Postgres id / stocks[0].id)."
                ),
                "product_id": pid,
            }

        try:
            delivery_min_i = int(float(delivery_min or 0))
        except (TypeError, ValueError):
            delivery_min_i = 0
        if delivery_min_i <= 0:
            delivery_min_i = 1440  # 1 day fallback so API gets a real value

        temp_uid = session.ensure_temp_user_id()
        # Match website / Postman body (strings + buy_now + temp_userId + stockId)
        payload: dict[str, Any] = {
            "user_id": str(uid),
            "product_id": str(pid),
            "buy_now": bool(args.get("buy_now")) if args.get("buy_now") is not None else False,
            "quantity": str(qty),
            "stockId": str(stock_id),
            "temp_userId": str(temp_uid),
            "delivery_time_minute": str(delivery_min_i),
        }
        print(f"[cart] addcart payload={payload}")
        result = api.post("/api/crux/addcart", json_body=payload, auth=True, trim=False)
        print(f"[cart] addcart response={result}")
        ok = isinstance(result, dict) and result.get("result") is True
        cart = None
        cart_err = None
        try:
            cart = _compact_cart(
                api.post(
                    f"/api/v2/carts/{uid}",
                    json_body={"user_latitude": None, "user_longitude": None},
                    auth=True,
                    trim=False,
                )
            )
        except Exception as err:
            cart_err = str(err)
        if not ok:
            msg = (
                (result or {}).get("message")
                if isinstance(result, dict)
                else "Add to cart failed"
            )
            return {
                "error": True,
                "ok": False,
                "message": msg or "Add to cart failed",
                "add_response": result,
                "payload_sent": payload,
                "hint": (
                    "Payload must include product_id (pro_id), stockId (PG id), "
                    "temp_userId, delivery_time_minute — same as website."
                ),
            }
        out: dict[str, Any] = {
            "ok": True,
            "message": (result or {}).get("message") or "Product added to cart",
            "add_response": result,
            "product_id": pid,
            "stockId": stock_id,
        }
        if cart is not None:
            out["cart"] = cart
        if cart_err:
            out["cart_refresh_error"] = cart_err
        return out

    if name == "remove_from_cart":
        result = api.post(
            "/api/v2/carts",
            json_body={"id": int(args["cart_item_id"])},
            auth=True,
        )
        cart = _compact_cart(
            api.post(f"/api/v2/carts/{uid}", json_body={}, auth=True, trim=False)
        )
        return {"remove_response": result, "cart": cart}

    if name == "update_cart_quantity":
        result = api.post(
            "/api/v2/carts/change-quantity",
            json_body={
                "id": int(args["cart_item_id"]),
                "quantity": int(args["quantity"]),
            },
            auth=True,
        )
        cart = _compact_cart(
            api.post(f"/api/v2/carts/{uid}", json_body={}, auth=True, trim=False)
        )
        return {"update_response": result, "cart": cart}

    if name == "get_my_wishlist":
        return _compact_wishlist(
            api.get(f"/api/v2/wishlists/{uid}", auth=True, trim=False)
        )

    if name == "add_to_wishlist":
        if args.get("product_id") in (None, ""):
            return {"error": True, "message": "product_id required"}
        result = api.get(
            "/api/v2/wishlists-add-product",
            params={
                "product_id": int(args["product_id"]),
                "user_id": uid,
                "islogin": "true",
            },
            auth=True,
        )
        return {"add_response": result}

    if name == "remove_from_wishlist":
        if args.get("product_id") in (None, ""):
            return {"error": True, "message": "product_id required"}
        result = api.get(
            "/api/v2/wishlists-remove-product",
            params={
                "product_id": int(args["product_id"]),
                "user_id": uid,
            },
            auth=True,
        )
        return {"remove_response": result}

    if name == "get_my_addresses":
        return api.get(f"/api/v2/allAddress/{uid}", params={"id": uid}, auth=True)

    if name == "select_address":
        return api.get(
            f"/api/v2/selectAnAddress/{int(args['address_id'])}",
            params={"user_id": uid},
            auth=True,
        )

    if name == "apply_coupon":
        return api.post(
            "/api/v2/coupon-apply",
            json_body={
                "user_id": uid,
                "coupon_code": str(args["coupon_code"]).strip(),
            },
            auth=True,
        )

    if name == "get_my_notifications":
        params: dict[str, Any] = {"user_id": uid, "all_months": "true"}
        if args.get("month"):
            params["month"] = args["month"]
        if args.get("year"):
            params["year"] = args["year"]
        return api.get("/api/notifications", params=params, auth=True)

    if name == "cancel_order":
        return api.post(
            "/api/v2/cancel_order",
            json_body={
                "order_id": args["order_id"],
                "reason": args.get("reason") or "cancelled by customer via Welfog AI",
                "phone": session.phone,
                "customer_name": session.user_name or "User",
            },
            auth=True,
        )

    if name == "get_user_snapshot":
        return api.post(
            "/api/v2/get-user-by-access_token",
            json_body={"access_token": session.access_token, "userId": uid},
            auth=True,
        )

    return {"error": True, "message": f"Unknown tool: {name}"}
