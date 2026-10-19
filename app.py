"""Flask backend for Welfog AI chat UI + admin panel."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request

from admin_routes import admin_bp
from agent import WelfogAgent
from config import SECRET_KEY
from formatter import extract_ui_from_history, strip_redundant_lists
from session import (
    bind_thread_session,
    commit_session,
    reset_thread_session,
    session as global_session,
    snapshot_session,
    unbind_thread_session,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.register_blueprint(admin_bp)

# chat_id -> { agent, title, updated_at, messages }
_chats: dict[str, dict] = {}
_lock = threading.Lock()


def _safe_db(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"[db] {fn.__name__} failed: {e}")
        return None


def _persist_session(chat_id: str, title: str | None = None):
    from db import upsert_chat_session

    _safe_db(
        upsert_chat_session,
        chat_id,
        title=title,
        visitor_key=global_session.ensure_visitor_key(),
        user_phone=global_session.phone,
        user_id=global_session.user_id,
        user_name=global_session.user_name,
    )


def _identity() -> dict:
    return {
        "user_id": global_session.user_id,
        "phone": str(global_session.phone or "").strip(),
        "name": global_session.user_name,
        "visitor_key": global_session.ensure_visitor_key(),
    }


def _uid_set(value) -> bool:
    return value not in (None, "", 0, "0")


def _same_uid(a, b) -> bool:
    if not _uid_set(a) or not _uid_set(b):
        return False
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _owns_row(row: dict | None) -> bool:
    if not row:
        return False
    ident = _identity()
    uid = row.get("owner_user_id")
    if uid in (None, "", 0):
        uid = row.get("user_id")
    phone = str(row.get("owner_phone") or row.get("user_phone") or "").strip()
    visitor = str(row.get("owner_visitor_key") or row.get("visitor_key") or "").strip()
    # Logged-in user must not inherit another account's chats just because
    # the WebView still has the previous visitor_key cookie.
    if _uid_set(ident["user_id"]) and _uid_set(uid) and not _same_uid(ident["user_id"], uid):
        return False
    # If phone numbers are set and different, never allow access across different users
    if ident["phone"] and phone and ident["phone"] != phone:
        return False
    if _same_uid(ident["user_id"], uid):
        return True
    if ident["phone"] and phone and ident["phone"] == phone:
        return True
    if ident["visitor_key"] and visitor and ident["visitor_key"] == visitor:
        return True
    return False


def _apply_app_login(
    token: str,
    uid,
    *,
    name: str = "",
    phone: str = "",
    email: str = "",
    force_new: bool = True,
) -> dict | None:
    """Verify shop token and bind it to this AI browser session."""
    token = str(token or "").strip()
    if not token or uid in (None, "", 0, "0", "guest", "null", "none"):
        return None
    current = str(global_session.user_id or "")
    incoming = str(uid)
    if (
        not force_new
        and global_session.is_authenticated
        and current == incoming
        and str(global_session.access_token or "") == token
    ):
        return global_session.summary()

    from api_client import api

    # Pass token explicitly so verification does not depend on unverified global_session
    snap = api.post(
        "/api/v2/get-user-by-access_token",
        json_body={"access_token": token, "userId": uid},
        token=token,
    )

    verified = False
    snap_data: dict = {}
    if isinstance(snap, dict):
        if snap.get("result") is True or snap.get("status") in (200, "200"):
            verified = True
        inner = snap.get("data") if isinstance(snap.get("data"), dict) else (snap.get("user") if isinstance(snap.get("user"), dict) else snap)
        if isinstance(inner, dict):
            snap_data = inner
            if inner.get("id") or inner.get("user_id"):
                verified = True

    if not verified:
        print(f"[auth] app-login verification failed for uid={uid}: {snap}")
        return None

    user_id = snap_data.get("id") or snap_data.get("user_id") or uid
    resolved_name = str(snap_data.get("name") or name or "").strip()
    resolved_email = str(snap_data.get("email") or email or "").strip()
    resolved_phone = str(snap_data.get("phone") or phone or "").strip()

    payload = {
        "access_token": token,
        "user": {
            "id": user_id,
            "name": resolved_name,
            "email": resolved_email,
            "phone": resolved_phone,
        },
    }
    switch = _uid_set(current) and not _same_uid(current, user_id)
    if force_new or switch or not global_session.is_authenticated:
        global_session.replace_from_app_login(payload)
    else:
        global_session.set_from_login(payload)
    commit_session()
    print(f"[auth] app-login success user_id={user_id} phone={resolved_phone} new_session={force_new or switch}")
    return global_session.summary()


def _login_error():
    return jsonify({"error": "login_required", "message": "Login with phone OTP first"}), 401


def _forbidden():
    return jsonify({"error": "forbidden", "message": "This chat belongs to another account"}), 403


def _stamp_owner(chat: dict) -> dict:
    ident = _identity()
    chat["owner_user_id"] = ident["user_id"]
    chat["owner_phone"] = ident["phone"]
    chat["owner_name"] = ident["name"]
    chat["owner_visitor_key"] = ident["visitor_key"]
    return chat


def _hydrate_chat_from_db(chat_id: str, sess: dict) -> dict:
    from db import get_chat_messages

    msgs = get_chat_messages(chat_id)
    agent = WelfogAgent()
    memory_msgs = []
    for m in msgs:
        memory_msgs.append(
            {
                "role": m["role"],
                "content": m["content"],
                "images": m.get("images") or ([m.get("image")] if m.get("image") else []),
                "image": m.get("image") or (m.get("images")[0] if m.get("images") else None),
                "ui": m.get("ui") or [],
                "ts": str(m.get("created_at") or ""),
            }
        )
        if m["role"] in ("user", "assistant"):
            agent.history.append({"role": m["role"], "content": m["content"]})
    chat = {
        "agent": agent,
        "title": sess.get("title") or "Chat",
        "updated_at": time.time(),
        "created_at": time.time(),
        "messages": memory_msgs,
        "owner_user_id": sess.get("user_id"),
        "owner_phone": sess.get("user_phone"),
        "owner_name": sess.get("user_name"),
        "owner_visitor_key": sess.get("visitor_key"),
    }
    with _lock:
        _chats[chat_id] = chat
    return chat


def _get_or_create_chat(chat_id: str | None = None) -> tuple[str, dict]:
    global_session.ensure_visitor_key()

    with _lock:
        if chat_id and chat_id in _chats:
            chat = _chats[chat_id]
            if not _owns_row(chat):
                raise PermissionError("forbidden")
            return chat_id, chat

    if chat_id:
        from db import get_chat_session

        sess = _safe_db(get_chat_session, chat_id)
        if sess:
            if not _owns_row(sess):
                raise PermissionError("forbidden")
            return chat_id, _hydrate_chat_from_db(chat_id, sess)

    new_id = uuid.uuid4().hex
    chat = _stamp_owner(
        {
            "agent": WelfogAgent(),
            "title": "New chat",
            "updated_at": time.time(),
            "created_at": time.time(),
            "messages": [],
        }
    )
    with _lock:
        _chats[new_id] = chat
    return new_id, chat


def _persist_message(chat_id: str, role: str, content: str, ui=None, images: list[str] | None = None, image: str | None = None):
    from db import add_chat_message

    img_list = images if images is not None else ([image] if image else [])
    meta = None
    if img_list:
        meta = {"images": img_list, "image": img_list[0]}
    _safe_db(add_chat_message, chat_id, role, content, ui, meta)


@app.before_request
def _ensure_db():
    if getattr(app, "_db_ready", False):
        return
    try:
        from db import init_db

        init_db()
        app._db_ready = True
        print("[db] my_ai ready")
    except Exception as e:
        print(f"[db] init failed (chat still works in-memory): {e}")
        app._db_ready = False


def _extract_request_auth() -> tuple[str, str, str, str, str, bool]:
    """Extract auth from headers, query params, or bearer tokens."""
    token = (
        request.headers.get("X-Welfog-Access-Token")
        or request.headers.get("X-Access-Token")
        or ""
    ).strip()
    if not token:
        auth_hdr = (request.headers.get("Authorization") or "").strip()
        if auth_hdr.lower().startswith("bearer "):
            token = auth_hdr[7:].strip()

    uid = (
        request.headers.get("X-Welfog-User-Id")
        or request.headers.get("X-User-Id")
        or request.headers.get("X-UserId")
        or ""
    ).strip()

    name = (request.headers.get("X-Welfog-Name") or request.headers.get("X-User-Name") or "").strip()
    phone = (request.headers.get("X-Welfog-Phone") or request.headers.get("X-User-Phone") or "").strip()
    email = (request.headers.get("X-Welfog-Email") or request.headers.get("X-User-Email") or "").strip()
    reset = (request.headers.get("X-Welfog-Reset-Session") or "").strip() == "1"

    # Fallback to query parameters (in case mobile WebViews drop headers on redirect)
    if not token:
        token = (
            request.args.get("token")
            or request.args.get("access_token")
            or request.args.get("auth_token")
            or request.args.get("authToken")
            or ""
        ).strip()
    if not uid:
        uid = (
            request.args.get("user_id")
            or request.args.get("userId")
            or request.args.get("uid")
            or request.args.get("id")
            or ""
        ).strip()
    if not name:
        name = (request.args.get("name") or request.args.get("user_name") or request.args.get("userName") or "").strip()
    if not phone:
        phone = (request.args.get("phone") or request.args.get("user_phone") or request.args.get("mobile") or "").strip()
    if not email:
        email = (request.args.get("email") or request.args.get("user_email") or "").strip()
    if not reset:
        reset = str(request.args.get("reset") or request.args.get("force_new") or "").strip().lower() in ("1", "true")

    return token, uid, name, phone, email, reset


@app.before_request
def _flutter_embed_login():
    """Flutter WebView sends auth headers or query params so the page
    boots as the current app user instead of an old leftover cookie."""
    token, uid, name, phone, email, reset = _extract_request_auth()

    # Guest or explicit logout from app
    if uid in ("guest", "logout", "0", 0):
        if global_session.is_authenticated:
            global_session.clear()
            commit_session()
        return

    if not token or not uid:
        return

    _apply_app_login(
        token,
        uid,
        name=name,
        phone=phone,
        email=email,
        force_new=reset,
    )


@app.teardown_request
def _teardown_request_cleanup(exception=None):
    reset_thread_session()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/auth/me")
def auth_me():
    return jsonify(global_session.summary())


@app.route("/api/auth/app-login", methods=["GET", "POST"])
def auth_app_login():
    """Flutter account login. Supports both JSON POST and GET query parameters."""
    data = {}
    if request.method == "POST":
        data = request.get_json(silent=True) or {}

    token, uid, name, phone, email, reset = _extract_request_auth()
    if not token and data:
        token = str(data.get("access_token") or data.get("token") or "").strip()
    if not uid and data:
        uid = data.get("user_id") or data.get("userId") or data.get("uid")
    if not name and data:
        name = str(data.get("name") or "")
    if not phone and data:
        phone = str(data.get("phone") or "")
    if not email and data:
        email = str(data.get("email") or "")
    force_new = data.get("force_new_session") if (data and "force_new_session" in data) else True

    summary = _apply_app_login(
        token,
        uid,
        name=name,
        phone=phone,
        email=email,
        force_new=bool(force_new or reset),
    )
    if not summary:
        err = "missing_credentials" if not token or uid in (None, "", 0, "0", "guest") else "invalid_token"
        code = 400 if err == "missing_credentials" else 401
        return jsonify({"ok": False, "authenticated": False, "error": err}), code
    return jsonify({"ok": True, "session": summary})


@app.route("/api/auth/sync", methods=["GET", "POST"])
def auth_sync():
    """Lightweight sync endpoint for mobile apps."""
    return auth_app_login()


@app.post("/api/auth/send-otp")
def auth_send_otp():
    from tools import execute_tool

    data = request.get_json(silent=True) or {}
    result = execute_tool("send_login_otp", {"phone": data.get("phone", "")})
    return jsonify(result if isinstance(result, dict) else {"ok": False})


@app.post("/api/auth/verify-otp")
def auth_verify_otp():
    from tools import execute_tool

    data = request.get_json(silent=True) or {}
    result = execute_tool(
        "verify_login_otp",
        {"phone": data.get("phone", ""), "otp": data.get("otp", "")},
    )
    return jsonify(result if isinstance(result, dict) else {"ok": False})


@app.post("/api/chat/new")
def new_chat():
    try:
        chat_id, chat = _get_or_create_chat()
    except PermissionError:
        return _forbidden()
    return jsonify(
        {
            "chat_id": chat_id,
            "title": chat["title"],
            "created_at": chat["created_at"],
            "session": global_session.summary(),
        }
    )


@app.get("/api/chats")
def list_chats():
    global_session.ensure_visitor_key()
    items = []
    seen = set()
    try:
        from db import list_user_chat_sessions

        rows = list_user_chat_sessions(
            user_id=global_session.user_id if global_session.is_authenticated else None,
            phone=global_session.phone if global_session.is_authenticated else None,
            visitor_key=global_session.ensure_visitor_key(),
            limit=80,
        )
        for r in rows or []:
            cid = r.get("id")
            if not cid:
                continue
            if not _owns_row(r):
                continue
            if int(r.get("message_count") or 0) <= 0:
                continue
            seen.add(cid)
            upd = r.get("updated_at")
            cr = r.get("created_at")
            items.append(
                {
                    "chat_id": cid,
                    "title": r.get("title") or "New chat",
                    "updated_at": upd.timestamp() if hasattr(upd, "timestamp") else time.time(),
                    "created_at": cr.timestamp() if hasattr(cr, "timestamp") else time.time(),
                    "message_count": int(r.get("message_count") or 0),
                }
            )
    except Exception as e:
        print(f"[db] list_user_chat_sessions failed: {e}")
    with _lock:
        for cid, c in _chats.items():
            if cid in seen or not _owns_row(c):
                continue
            if not (c.get("messages") or []):
                continue
            items.append(
                {
                    "chat_id": cid,
                    "title": c.get("title") or "New chat",
                    "updated_at": c.get("updated_at") or 0,
                    "created_at": c.get("created_at") or 0,
                    "message_count": len(c.get("messages") or []),
                }
            )
    items = [x for x in items if int(x.get("message_count") or 0) > 0]
    items.sort(key=lambda x: x["updated_at"] or 0, reverse=True)
    return jsonify({"chats": items, "session": global_session.summary()})


@app.get("/api/chat/<chat_id>")
def get_chat(chat_id: str):
    global_session.ensure_visitor_key()
    with _lock:
        chat = _chats.get(chat_id)
    if chat:
        if not _owns_row(chat):
            return _forbidden()
        return jsonify(
            {
                "chat_id": chat_id,
                "title": chat["title"],
                "messages": chat["messages"],
                "session": global_session.summary(),
            }
        )

    try:
        from db import get_chat_session

        sess = get_chat_session(chat_id)
        if not sess:
            return jsonify({"error": "Chat not found"}), 404
        if not _owns_row(sess):
            return _forbidden()
        chat = _hydrate_chat_from_db(chat_id, sess)
        return jsonify(
            {
                "chat_id": chat_id,
                "title": chat.get("title") or "Chat",
                "messages": chat.get("messages") or [],
                "session": global_session.summary(),
            }
        )
    except Exception:
        return jsonify({"error": "Chat not found"}), 404


@app.delete("/api/chat/<chat_id>")
@app.post("/api/chat/<chat_id>/delete")
def delete_chat(chat_id: str):
    global_session.ensure_visitor_key()
    with _lock:
        mem = _chats.get(chat_id)
    if mem and not _owns_row(mem):
        return _forbidden()
    if not mem:
        from db import get_chat_session

        sess = _safe_db(get_chat_session, chat_id)
        if sess and not _owns_row(sess):
            return _forbidden()
    with _lock:
        _chats.pop(chat_id, None)
    try:
        from db import delete_chat_session

        delete_chat_session(chat_id)
    except Exception as e:
        print(f"[db] delete_chat_session failed: {e}")
    return jsonify({"ok": True})


@app.post("/api/chat/<chat_id>/rename")
def rename_chat(chat_id: str):
    global_session.ensure_visitor_key()
    data = request.get_json(silent=True) or {}
    new_title = (data.get("title") or "").strip()[:100]
    if not new_title:
        return jsonify({"error": "Title required"}), 400
    with _lock:
        mem = _chats.get(chat_id)
        if mem:
            if not _owns_row(mem):
                return _forbidden()
            mem["title"] = new_title
    if not mem:
        from db import get_chat_session
        sess = _safe_db(get_chat_session, chat_id)
        if sess and not _owns_row(sess):
            return _forbidden()
    try:
        from db import upsert_chat_session
        _safe_db(upsert_chat_session, chat_id, title=new_title)
    except Exception as e:
        print(f"[db] rename_chat error: {e}")
    return jsonify({"ok": True, "title": new_title})


TOOL_STATUS_LABELS = {
    "search_products": "Searching products…",
    "get_today_deals": "Finding today's deals…",
    "get_related_products": "Finding similar products…",
    "get_product_details": "Checking product details…",
    "get_my_orders": "Fetching your orders…",
    "get_purchase_history": "Loading order history…",
    "get_order_details": "Opening order details…",
    "get_my_profile": "Loading your profile…",
    "update_my_profile": "Updating your profile…",
    "add_to_cart": "Adding to cart…",
    "get_cart": "Checking your cart…",
    "update_cart_quantity": "Updating cart…",
    "remove_from_cart": "Updating cart…",
    "send_login_otp": "Sending OTP…",
    "verify_login_otp": "Verifying OTP…",
    "send_otp": "Sending OTP…",
    "verify_otp": "Verifying OTP…",
    "search_company_knowledge": "Checking Welfog help…",
    "get_my_wishlist": "Opening wishlist…",
    "add_to_wishlist": "Updating wishlist…",
    "get_my_addresses": "Loading addresses…",
    "get_my_notifications": "Checking notifications…",
    "cancel_order": "Cancelling order…",
    "apply_coupon": "Applying coupon…",
    "get_session_status": "Checking login…",
    "get_user_snapshot": "Loading account…",
    "play_get_my_profile": "Loading your Play profile…",
    "play_update_my_profile": "Updating Play profile…",
    "play_get_my_reels": "Loading your Play reels…",
    "play_search": "Searching Play…",
    "play_get_feed": "Loading Play reels…",
    "play_get_user_profile": "Loading Play profile…",
}


def _tool_status_label(fn: str) -> str:
    if fn in TOOL_STATUS_LABELS:
        return TOOL_STATUS_LABELS[fn]
    nice = (fn or "task").replace("_", " ").strip()
    return f"Working on {nice}…"


def _agent_error_reply(exc: Exception) -> str:
    """Customer-facing text only — never leak keys, quota, or Gemini config."""
    print(f"[chat] agent failed: {exc}")
    err = str(exc).lower()
    from image import get_safety_error_reply, is_safety_error

    if is_safety_error(err):
        return get_safety_error_reply()

    # Any Gemini/AI outage → soft maintenance-style reply
    if any(
        x in err
        for x in (
            "429",
            "quota",
            "rate",
            "prepayment",
            "credits are depleted",
            "resource_exhausted",
            "billing",
            "401",
            "403",
            "api key",
            "permission",
            "gemini",
            "openai",
            "timeout",
            "timed out",
            "connection",
        )
    ):
        return (
            "We're currently under a short maintenance. "
            "Please try again after some time — we'll be right back for you."
        )
    return (
        "Something went wrong on our side. "
        "Please try again after some time."
    )


CARD_SPLIT_MARKER = "<<<CARDS>>>"


def _looks_like_category_overview(user_text: str) -> bool:
    """True when user wants the site's category list — not product SKUs."""
    t = (user_text or "").strip().lower()
    if not t:
        return False
    # Explicit category-catalog asks (text answer only; no product cards)
    phrases = (
        "all categor",
        "all category",
        "categories list",
        "category list",
        "list of categor",
        "list all categor",
        "listed categor",
        "category listed",
        "categories listed",
        "categories on",
        "category on welfog",
        "categories on welfog",
        "saari categor",
        "saari category",
        "sari categor",
        "sari category",
        "categories dikhao",
        "category dikhao",
        "categor dikhao",
        "kya kya categor",
        "categories kya",
        "category kya",
        "categor kya",
        "kya categories",
        "what categories",
        "which categories",
        "available categor",
        "welfog categor",
        "pe categor",
        "par categor",
        "mein categor",
        "me categor",
    )
    if any(p in t for p in phrases):
        return True
    # Short meta asks: "categories?", "category list?"
    import re

    toks = re.findall(r"[a-z0-9]+", t)
    meta = {
        "category",
        "categories",
        "categor",
        "list",
        "listed",
        "all",
        "see",
        "show",
        "want",
        "welfog",
        "website",
        "site",
        "on",
        "the",
        "of",
        "to",
        "i",
        "me",
        "my",
        "please",
        "pls",
        "dikhao",
        "dikao",
        "batao",
        "btao",
        "kya",
        "hai",
        "hain",
        "he",
        "h",
        "pe",
        "par",
        "mein",
        "mai",
        "only",
        "just",
        "full",
        "complete",
    }
    substantive = [x for x in toks if x not in meta and len(x) > 1]
    has_cat = any(x.startswith("categor") for x in toks)
    return bool(has_cat and not substantive)


def _looks_like_support_contact(user_text: str) -> bool:
    """True for support/contact/complaint — never attach browse product cards."""
    t = (user_text or "").strip().lower()
    if not t:
        return False
    markers = (
        "contact support",
        "connect with your team",
        "connect with support",
        "contact karna",
        "support se baat",
        "support se contact",
        "customer support",
        "customer care",
        "submit_contact",
        "would like to contact support",
        "i need help",
        "need help",
        "complaint",
        "complain",
        "shikayat",
        "madad chahiye",
        "help desk",
        "talk to support",
        "talk to team",
        "raise a ticket",
        "support ticket",
    )
    if any(m in t for m in markers):
        return True
    # Headset canned prompt from UI
    if "support" in t and ("contact" in t or "team" in t or "issue" in t):
        return True
    return False


def _looks_like_product_browse(user_text: str) -> bool:
    """True when user clearly wants to see/buy a product category."""
    import re

    from formatter import normalize_product_query
    from session import session as global_session

    t = (user_text or "").strip().lower()
    if not t:
        return False
    # Phone / OTP digits — never treat as product browse
    digits = re.sub(r"\D", "", t)
    if digits and re.sub(r"[\s\-]+", "", t) == digits and 4 <= len(digits) <= 12:
        return False
    if global_session.otp_pending:
        return False
    # Support / contact → text only
    if _looks_like_support_contact(t):
        return False
    # Category overview → text list only; never force product search/cards
    if _looks_like_category_overview(t):
        return False
    # Act intents — don't force browse search / random suggestions
    if any(
        x in t
        for x in (
            "cart me",
            "cart mein",
            "add to cart",
            "remove",
            "hata",
            "hatado",
            "hata do",
            "delete",
            "wishlist",
            "order",
            "otp",
            "login",
            "profile",
            "cancel",
            "cart",
            "support",
            "complaint",
            "contact",
        )
    ):
        return False
    q = (normalize_product_query(t) or "").strip()
    if not q:
        return False
    # Normalized query should contain a real product type, not only filler/meta
    filler = {
        "product",
        "products",
        "item",
        "items",
        "samaan",
        "option",
        "options",
        "chahiye",
        "dikhao",
        "dikao",
        "muje",
        "mujhe",
        "please",
        "pls",
        "i",
        "want",
        "to",
        "see",
        "show",
        "me",
        "my",
        "all",
        "the",
        "on",
        "of",
        "a",
        "an",
        "for",
        "list",
        "listed",
        "category",
        "categories",
        "categor",
        "welfog",
        "website",
        "site",
        "available",
        "batao",
        "btao",
        "kya",
        "hai",
        "hain",
        "pe",
        "par",
        "mein",
        "mai",
        "help",
        "need",
        "issue",
        "team",
        "regarding",
        "would",
        "like",
        "and",
        "with",
        "your",
        "connect",
    }
    tokens = {x for x in re.findall(r"[a-z0-9]+", q.lower()) if x}
    # Pure numeric tokens (ids / phones) are not product browse
    if tokens and all(x.isdigit() for x in tokens):
        return False
    return bool(tokens - filler)


def _fallback_product_cards(chat: dict, user_text: str) -> list[dict]:
    """Search each requested item separately, then merge — works for any product mix."""
    import json
    import uuid

    from formatter import (
        _pick_products,
        _rank_products_by_query,
        split_browse_queries,
    )
    from tools import execute_tool

    parts = split_browse_queries(user_text)
    if not parts:
        return []

    merged: list[dict] = []
    seen: set[str] = set()
    raw_by_part: list[tuple[str, dict]] = []

    for part in parts:
        print(f"[chat] browse search for: {part!r}")
        raw = execute_tool("search_products", {"name": part, "page": 1})
        if not isinstance(raw, dict) or raw.get("error") or raw.get("needs_clarification"):
            continue
        raw_by_part.append((part, raw))
        batch = _pick_products(raw) or []
        ranked = _rank_products_by_query(batch, part)[:8]
        for c in ranked:
            if c.get("type") != "product":
                continue
            key = f"{c.get('id') or ''}:{c.get('name') or ''}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(c)

    if not merged:
        return []

    # Inject tool traces so later cart/add can reuse ids
    hist = chat["agent"].history
    insert_at = len(hist)
    if hist and hist[-1].get("role") == "assistant" and not hist[-1].get("tool_calls"):
        insert_at = len(hist) - 1
    for part, raw in raw_by_part:
        tc_id = f"browse_{uuid.uuid4().hex[:10]}"
        hist.insert(
            insert_at,
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": "search_products",
                            "arguments": json.dumps({"name": part, "page": 1}),
                        },
                    }
                ],
            },
        )
        hist.insert(
            insert_at + 1,
            {
                "role": "tool",
                "tool_call_id": tc_id,
                "content": json.dumps(raw, ensure_ascii=False, default=str),
            },
        )
        insert_at += 2

    return merged[:20]


def _ensure_product_card_sandwich(reply: str, has_products: bool) -> str:
    """Keep model text natural; only ensure <<<CARDS>>> marker when products exist."""
    text = (reply or "").strip()
    marker = CARD_SPLIT_MARKER

    if not has_products:
        return text.replace(marker, "").strip()

    # Collapse duplicate markers / normalize spacing around marker
    while f"{marker}\n\n{marker}" in text:
        text = text.replace(f"{marker}\n\n{marker}", marker)
    text = text.replace(marker, f"\n\n{marker}\n\n")
    text = "\n".join(l.rstrip() for l in text.splitlines()).strip()

    # Drop only spammy English CTA templates — keep natural Hinglish follow-ups
    def _clean_side(side: str) -> str:
        lines = []
        for ln in side.splitlines():
            low = ln.lower().strip()
            if not low:
                lines.append(ln)
                continue
            if low in {
                "here are some matching options:",
                "here are some matching options",
                "here are matching options:",
                "matching options:",
            }:
                continue
            if "like any of these" in low:
                continue
            if "swipe" in low and ("card" in low or "option" in low):
                continue
            lines.append(ln)
        return "\n".join(lines).strip()

    if marker in text:
        before, _, after = text.partition(marker)
        before = _clean_side(before)
        after = _clean_side(after)
        # Preserve whatever the model wrote; no static filler if empty
        if before and after:
            return f"{before}\n\n{marker}\n\n{after}"
        if before:
            return f"{before}\n\n{marker}"
        if after:
            return f"{marker}\n\n{after}"
        return marker

    before = _clean_side(text)
    if before:
        return f"{before}\n\n{marker}"
    return marker


def _align_reply_with_products(
    reply: str, has_products: bool, *, skip_product_fallback: bool = False
) -> str:
    """Light cleanup only — never overwrite the model with canned product-miss copy."""
    import re

    text = (reply or "").strip()
    low = text.lower().strip()

    if has_products:
        # Tiny/empty model replies — still show cards; don't inject a fixed English line
        if not text or low in {"done", "done.", "ok", "okay"}:
            return CARD_SPLIT_MARKER
        return _ensure_product_card_sandwich(text, True)

    # No products — remove card marker; keep the AI's own wording
    text = text.replace(CARD_SPLIT_MARKER, "").strip()
    low = text.lower()

    if skip_product_fallback:
        lines = [
            ln
            for ln in text.splitlines()
            if "like any of these" not in ln.lower()
            and "refine by size" not in ln.lower()
        ]
        return "\n".join(lines).strip()

    auth_keep = (
        "otp",
        "login",
        "logged",
        "mobile",
        "phone",
        "verify",
        "bhej diya",
        "bhej di",
        "order",
        "account",
    )
    if any(k in low for k in auth_keep):
        return text

    # Strip lines that falsely claim cards were shown — keep the rest of the AI reply
    false_show = (
        "dikha diye",
        "dikha diya",
        "cards mein",
        "swipe karke",
        "neeche options",
        "upar dikha",
    )
    cleaned_lines = []
    for ln in text.splitlines():
        l = ln.lower()
        if any(p in l for p in false_show):
            continue
        cleaned_lines.append(ln)
    text = "\n".join(cleaned_lines).strip()
    low = text.lower().strip()

    # Drop empty/useless stubs only — never inject a static "no match" paragraph
    if not text or low in {"done", "done.", "ok", "okay"}:
        return ""

    text = re.sub(r"\binme(?:in)? se\b", "one of these", text, flags=re.I)
    return text


def _tools_used_this_turn(history: list) -> set[str]:
    """Tool names called after the latest user message."""
    last_user_idx = None
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") == "user":
            last_user_idx = i
            break
    if last_user_idx is None:
        return set()
    names: set[str] = set()
    for msg in history[last_user_idx + 1 :]:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            n = ((tc.get("function") or {}).get("name") or "").strip()
            if n:
                names.add(n)
    return names


def _finalize_reply(chat: dict, reply: str) -> tuple[str, list]:
    import re

    from formatter import (
        ACTION_TURN_TOOLS,
        BROWSE_ONLY_PRODUCT_TOOLS,
        _rank_products_for_user,
    )
    from session import session as global_session

    history = chat["agent"].history
    ui_cards = extract_ui_from_history(history)
    reply = strip_redundant_lists(reply)
    reply = re.sub(
        r"^(arre+|arey+|are+|yaar|oye|bhai|bro|dude|abe)\b[,!\.\s]*",
        "",
        (reply or "").lstrip(),
        count=1,
        flags=re.I,
    )

    user_text = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            c_val = msg.get("content")
            if isinstance(c_val, list):
                from image import extract_text_from_content

                user_text = extract_text_from_content(c_val)
            else:
                user_text = str(c_val or "")
            break

    used_tools = _tools_used_this_turn(history)
    # Cart/wishlist mutate / login tools → never inject random browse suggestions
    action_tools = bool(used_tools & ACTION_TURN_TOOLS)
    cart_only = bool(
        used_tools
        & {
            "get_my_cart",
            "get_cart_summary",
            "remove_from_cart",
            "add_to_cart",
            "update_cart_quantity",
            "apply_coupon",
        }
    )
    browse_tools_used = bool(used_tools & BROWSE_ONLY_PRODUCT_TOOLS)
    support_turn = _looks_like_support_contact(user_text) or (
        "submit_contact" in used_tools
    )

    digits = re.sub(r"\D", "", user_text)
    auth_digits = bool(
        digits
        and re.sub(r"[\s\-]+", "", user_text.strip()) == digits
        and 4 <= len(digits) <= 12
    )
    auth_turn = bool(
        auth_digits
        or global_session.otp_pending
        or "send_login_otp" in used_tools
        or "verify_login_otp" in used_tools
    )

    # After remove/add/update cart: don't show leftover browse SKUs as "suggestions"
    if action_tools or auth_turn:
        if "remove_from_cart" in used_tools or auth_turn:
            ui_cards = [
                c
                for c in (ui_cards or [])
                if c.get("type") not in ("product", "feature_filters")
            ]
        elif action_tools:
            # Keep only cart items from this turn; drop search/related browse cards
            ui_cards = [
                c
                for c in (ui_cards or [])
                if (c.get("type") == "product" and c.get("from_cart"))
                or c.get("type") not in ("product", "feature_filters")
            ]

    # Support / contact: never show product cards (even if model wrongly searched)
    if support_turn:
        ui_cards = [
            c
            for c in (ui_cards or [])
            if c.get("type") not in ("product", "feature_filters")
        ]

    # No browse tool this turn → drop browse product cards (no static injection leftovers)
    elif not browse_tools_used:
        ui_cards = [
            c
            for c in (ui_cards or [])
            if (c.get("type") == "product" and c.get("from_cart"))
            or c.get("type") not in ("product", "feature_filters")
        ]

    if user_text and ui_cards and not auth_turn and not action_tools and not support_turn:
        ui_cards = _rank_products_for_user(ui_cards, user_text)

    has_products = any(c.get("type") == "product" for c in (ui_cards or []))

    # Category overview asks → never attach / inject product cards
    if _looks_like_category_overview(user_text) or support_turn:
        ui_cards = [
            c
            for c in (ui_cards or [])
            if c.get("type") not in ("product", "feature_filters")
        ]
        has_products = False
    # IMPORTANT: do NOT re-search with raw user text after AI already searched.
    # Example bug: AI searched "hoodies" (0 hits) then fallback "show me hoodies"
    # matched "No Show" socks via the word "show". Trust AI / OpenSearch result.

    skip_product_ui = (
        auth_turn
        or action_tools
        or support_turn
        or ("remove_from_cart" in used_tools)
    )
    if skip_product_ui and (
        support_turn or auth_turn or "remove_from_cart" in used_tools
    ):
        ui_cards = [
            c
            for c in (ui_cards or [])
            if c.get("type") not in ("product", "feature_filters")
        ]
        has_products = False

    reply = _align_reply_with_products(
        reply, has_products, skip_product_fallback=skip_product_ui
    )

    return reply, ui_cards or []


def _begin_user_turn(chat_id: str | None, message: str, images: list[str] | None = None, image: str | None = None) -> tuple[str, dict]:
    chat_id, chat = _get_or_create_chat(chat_id)
    _stamp_owner(chat)
    _persist_session(chat_id, title=chat.get("title"))

    img_list = images if images is not None else ([image] if image else [])
    user_msg = {
        "role": "user",
        "content": message,
        "images": img_list,
        "image": img_list[0] if img_list else None,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    chat["messages"].append(user_msg)
    _persist_message(chat_id, "user", message, images=img_list)

    if chat["title"] == "New chat":
        count_label = f"{len(img_list)} Photos" if len(img_list) > 1 else "Photo"
        label = message or (count_label if img_list else "New chat")
        chat["title"] = label[:48] + ("…" if len(label) > 48 else "")
        _persist_session(chat_id, title=chat["title"])
    return chat_id, chat


def _persist_assistant_turn(chat_id: str, chat: dict, reply: str, ui_cards: list) -> dict:
    _persist_session(chat_id, title=chat["title"])
    asst_msg = {
        "role": "assistant",
        "content": reply,
        "ui": ui_cards,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    chat["messages"].append(asst_msg)
    _persist_message(chat_id, "assistant", reply, ui_cards)
    chat["updated_at"] = time.time()
    return {
        "chat_id": chat_id,
        "reply": reply,
        "ui": ui_cards,
        "title": chat["title"],
        "session": global_session.summary(),
    }


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    raw_images = data.get("images")
    if not isinstance(raw_images, list):
        raw_images = [data.get("image")] if data.get("image") else []
    images = [str(img).strip() for img in raw_images if img and str(img).strip()][:3]
    image = images[0] if images else None
    chat_id = data.get("chat_id")
    if not message and not images:
        return jsonify({"error": "Empty message"}), 400

    try:
        chat_id, chat = _begin_user_turn(chat_id, message, images=images, image=image)
    except PermissionError:
        return _forbidden()

    try:
        reply = chat["agent"].chat(message, images=images, image=image, provider="gemini")
    except Exception as e:
        reply = _agent_error_reply(e)

    reply, ui_cards = _finalize_reply(chat, reply)
    return jsonify(_persist_assistant_turn(chat_id, chat, reply, ui_cards))


@app.post("/api/chat/stream")
def chat_stream():
    """SSE: live status labels while agent thinks/tools, then final reply."""
    import json
    import queue as queue_mod

    from flask import Response, stream_with_context

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    raw_images = data.get("images")
    if not isinstance(raw_images, list):
        raw_images = [data.get("image")] if data.get("image") else []
    images = [str(img).strip() for img in raw_images if img and str(img).strip()][:3]
    image = images[0] if images else None
    chat_id = data.get("chat_id")
    if not message and not images:
        return jsonify({"error": "Empty message"}), 400

    try:
        chat_id, chat = _begin_user_turn(chat_id, message, images=images, image=image)
    except PermissionError:
        return _forbidden()
    q: queue_mod.Queue = queue_mod.Queue()

    def emit_status(text: str):
        q.put(("status", text))

    snap = snapshot_session()
    initial_status = f"Analyzing {len(images)} photos…" if len(images) > 1 else ("Analyzing photo…" if images else "Thinking…")

    def worker():
        bind_thread_session(snap)
        try:
            emit_status(initial_status)

            def on_status(text: str):
                emit_status(text)

            def on_tool(fn: str, _args: dict):
                emit_status(_tool_status_label(fn))

            reply = chat["agent"].chat(
                message,
                images=images,
                image=image,
                provider="gemini",
                on_status=on_status,
                on_tool=on_tool,
            )
            emit_status("Writing reply…")
            reply, ui_cards = _finalize_reply(chat, reply)
            payload = _persist_assistant_turn(chat_id, chat, reply, ui_cards)
            q.put(("done", payload))
        except Exception as e:
            reply = _agent_error_reply(e)
            reply, ui_cards = _finalize_reply(chat, reply)
            payload = _persist_assistant_turn(chat_id, chat, reply, ui_cards)
            q.put(("done", payload))
        finally:
            commit_session()
            unbind_thread_session()

    threading.Thread(target=worker, daemon=True).start()

    @stream_with_context
    def generate():
        yield f"data: {json.dumps({'type': 'status', 'text': initial_status}, ensure_ascii=False)}\n\n"
        while True:
            kind, payload = q.get()
            if kind == "status":
                yield f"data: {json.dumps({'type': 'status', 'text': payload}, ensure_ascii=False)}\n\n"
            elif kind == "done":
                yield f"data: {json.dumps({'type': 'done', **payload}, ensure_ascii=False)}\n\n"
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/auth/logout")
@app.post("/api/logout")
def logout():
    global_session.clear()
    return jsonify({"ok": True, "session": global_session.summary()})


if __name__ == "__main__":
    import os

    port = int(os.getenv("PORT") or os.getenv("FLASK_PORT") or "5055")
    app.run(host="0.0.0.0", port=port)
