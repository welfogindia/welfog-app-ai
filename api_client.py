"""HTTP client for https://welfogapi.welfog.com"""

from __future__ import annotations

import json
from typing import Any

import requests

from config import MAX_TOOL_RESULT_CHARS, REQUEST_TIMEOUT, WELFOG_API_BASE
from session import session


class WelfogAPI:
    def __init__(self, base_url: str = WELFOG_API_BASE):
        self.base_url = base_url.rstrip("/")
        self.http = requests.Session()
        self.http.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": "WelfogAI/1.0",
            }
        )

    def _auth_headers(self) -> dict:
        headers = {}
        if session.access_token:
            headers["Authorization"] = f"Bearer {session.access_token}"
            headers["Cookie"] = f"token={session.access_token}"
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        auth: bool = False,
        trim: bool = True,
    ) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        headers = self._auth_headers() if auth else {}
        try:
            resp = self.http.request(
                method.upper(),
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000], "status_code": resp.status_code}
            if not resp.ok and isinstance(data, dict):
                data.setdefault("http_status", resp.status_code)
            return self._trim(data) if trim else data
        except requests.RequestException as e:
            return {"error": True, "message": str(e)}

    def get(
        self,
        path: str,
        params: dict | None = None,
        auth: bool = False,
        *,
        trim: bool = True,
    ) -> Any:
        return self.request("GET", path, params=params, auth=auth, trim=trim)

    def post(
        self,
        path: str,
        json_body: dict | None = None,
        params: dict | None = None,
        auth: bool = False,
        *,
        trim: bool = True,
    ) -> Any:
        return self.request(
            "POST", path, params=params, json_body=json_body or {}, auth=auth, trim=trim
        )

    def _slim_item(self, item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        nested = item.get("data") if isinstance(item.get("data"), dict) else {}
        prefer = (
            "id", "oid", "pro_id", "pid", "code", "name", "slug", "product_title",
            "product_name", "product_id", "product_slug", "unit_price",
            "purchase_price", "price", "discounted_price", "main_price", "stroked_price",
            "has_discount", "grand_total", "rating", "shop_name", "shop_id",
            "thumbnail_image", "thumb_url", "product_img", "stocks", "current_stock",
            "category_name", "payment_status", "payment_status_string", "payment_type",
            "current_order_status", "date", "created_at",
            "expected_delivery", "question", "answer", "phone", "email",
            "address", "city", "state", "pincode", "message", "color_name", "size", "colors",
            "tracking_code",
        )
        out = {k: item[k] for k in prefer if k in item and item[k] not in (None, "")}
        for k in ("color_name", "size", "colors", "unit_price", "purchase_price", "stock"):
            if k not in out and nested.get(k) not in (None, ""):
                out[k] = nested[k]
        if out:
            return out
        return {
            k: v for k, v in list(item.items())[:15]
            if isinstance(v, (str, int, float, bool)) or v is None
        }

    def _trim(self, data: Any) -> Any:
        text = json.dumps(data, ensure_ascii=False, default=str)
        if len(text) <= MAX_TOOL_RESULT_CHARS:
            return data
        if isinstance(data, dict):
            trimmed = dict(data)
            for key in ("products", "data", "orders", "faqs", "addData", "suggestions", "notifications"):
                if key in trimmed and isinstance(trimmed[key], list):
                    slim = [self._slim_item(x) for x in trimmed[key][:10]]
                    trimmed[key] = slim
                    trimmed["_truncated"] = f"{key} limited/slimmed to first {len(slim)} items"
            text2 = json.dumps(trimmed, ensure_ascii=False, default=str)
            if len(text2) <= MAX_TOOL_RESULT_CHARS:
                return trimmed
            # still too big — drop heavy nested leftovers
            for key in list(trimmed.keys()):
                if key.startswith("_"):
                    continue
                if isinstance(trimmed[key], (dict, list)) and key not in (
                    "products", "data", "orders", "faqs", "addData", "suggestions",
                ):
                    trimmed.pop(key, None)
            text3 = json.dumps(trimmed, ensure_ascii=False, default=str)
            if len(text3) <= MAX_TOOL_RESULT_CHARS:
                return trimmed
            return {
                "truncated": True,
                "preview": text3[: MAX_TOOL_RESULT_CHARS - 200],
                "note": "Response was large; showing preview. Ask for a more specific id/page.",
            }
        return {"truncated": True, "preview": text[: MAX_TOOL_RESULT_CHARS - 100]}


api = WelfogAPI()
