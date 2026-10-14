"""Dynamic APIs from admin registry → OpenAI tools + executor."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from config import REQUEST_TIMEOUT
from db import get_api_by_tool, list_apis
from session import session


def _parse_json(raw: str | None, default: Any):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _fill_template(text: str, args: dict) -> str:
    """Replace {user_id}, {access_token}, {phone}, and {arg_name} placeholders."""
    mapping = {
        "user_id": session.user_id or "",
        "access_token": session.access_token or "",
        "phone": session.phone or "",
        "user_name": session.user_name or "",
    }
    mapping.update({k: ("" if v is None else v) for k, v in (args or {}).items()})

    def repl(m):
        key = m.group(1)
        return str(mapping.get(key, m.group(0)))

    return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, text)


def build_dynamic_tools() -> list[dict]:
    tools = []
    for api in list_apis(active_only=True):
        params_schema = _parse_json(api.get("query_params_json"), [])
        properties = {}
        required = []
        if isinstance(params_schema, list):
            for p in params_schema:
                if not isinstance(p, dict) or not p.get("name"):
                    continue
                name = p["name"]
                properties[name] = {
                    "type": p.get("type") or "string",
                    "description": p.get("description") or name,
                }
                if p.get("required"):
                    required.append(name)
        elif isinstance(params_schema, dict):
            # allow raw JSON schema object
            properties = params_schema.get("properties") or {}
            required = params_schema.get("required") or []

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": api["tool_name"],
                    "description": api["description"]
                    + (f" Hint: {api['response_hint']}" if api.get("response_hint") else ""),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return tools


def execute_dynamic_api(tool_name: str, args: dict) -> Any:
    api = get_api_by_tool(tool_name)
    if not api:
        return {"error": True, "message": f"Unknown registered API tool: {tool_name}"}

    args = args or {}
    if api.get("auth_mode") == "bearer_session" and not session.is_authenticated:
        return {
            "error": True,
            "needs_login": True,
            "message": "Login required (OTP) before calling this API.",
        }

    url = _fill_template(api["url"], args)
    method = (api.get("method") or "GET").upper()
    headers = _parse_json(api.get("headers_json"), {}) or {}
    if not isinstance(headers, dict):
        headers = {}
    headers.setdefault("Accept", "application/json")
    headers.setdefault("X-Requested-With", "XMLHttpRequest")

    if api.get("auth_mode") == "bearer_session" and session.access_token:
        headers["Authorization"] = f"Bearer {session.access_token}"
        headers["Cookie"] = f"token={session.access_token}"

    # Build query from declared params + leftover args
    query: dict[str, Any] = {}
    params_schema = _parse_json(api.get("query_params_json"), [])
    if isinstance(params_schema, list):
        for p in params_schema:
            if isinstance(p, dict) and p.get("name") in args:
                query[p["name"]] = args[p["name"]]

    body = None
    body_tpl = _parse_json(api.get("body_template_json"), None)
    if method in ("POST", "PUT", "PATCH"):
        if isinstance(body_tpl, dict):
            body = json.loads(_fill_template(json.dumps(body_tpl), args))
        else:
            body = args

    try:
        resp = requests.request(
            method,
            url,
            params=query or None,
            json=body if body is not None else None,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:4000], "status_code": resp.status_code}
        if isinstance(data, dict):
            data.setdefault("http_status", resp.status_code)
            if api.get("response_hint"):
                data["_hint"] = api["response_hint"]
        return data
    except requests.RequestException as e:
        return {"error": True, "message": str(e)}
