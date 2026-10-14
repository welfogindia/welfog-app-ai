"""Per-browser customer session (Flask cookie + thread-local for SSE workers)."""

from __future__ import annotations

import secrets
import threading
import time

_tls = threading.local()
_STORE_KEY = "welfog_user"
# SSE workers cannot write Flask cookies after the stream starts.
# Keep login/OTP state here keyed by visitor_key so the next request still has the phone.
_SERVER_SESSIONS: dict[str, dict] = {}


def _flask_store() -> dict | None:
    try:
        from flask import has_request_context, session as flask_session

        if not has_request_context():
            return None
        data = flask_session.get(_STORE_KEY)
        if not isinstance(data, dict):
            data = {}
            flask_session[_STORE_KEY] = data
        return data
    except Exception:
        return None


def _visitor_key_of(data: dict | None) -> str:
    return str((data or {}).get("visitor_key") or "").strip()


def commit_session(data: dict | None = None) -> None:
    blob = dict(data if data is not None else snapshot_session())
    vk = _visitor_key_of(blob)
    if vk:
        _SERVER_SESSIONS[vk] = blob


def _hydrate_from_server(data: dict) -> dict:
    vk = _visitor_key_of(data)
    saved = _SERVER_SESSIONS.get(vk) if vk else None
    if saved:
        merged = dict(saved)
        merged["visitor_key"] = vk
        data.clear()
        data.update(merged)
        _SERVER_SESSIONS[vk] = data
    return data


def _store() -> dict:
    if getattr(_tls, "bound", False):
        data = getattr(_tls, "data", None)
        if data is None:
            data = {}
            _tls.data = data
        return data
    data = _flask_store()
    if data is not None:
        return _hydrate_from_server(data)
    data = getattr(_tls, "data", None)
    if data is None:
        data = {}
        _tls.data = data
    return data


def _touch() -> None:
    try:
        from flask import has_request_context, session as flask_session

        if has_request_context():
            flask_session.permanent = True
            flask_session.modified = True
    except Exception:
        pass
    vk = _visitor_key_of(_store())
    if vk and not getattr(_tls, "bound", False):
        _SERVER_SESSIONS[vk] = dict(_store())


def snapshot_session() -> dict:
    return dict(_store())


def bind_thread_session(data: dict | None) -> None:
    incoming = dict(data or {})
    vk = _visitor_key_of(incoming)
    if vk and vk in _SERVER_SESSIONS:
        merged = dict(_SERVER_SESSIONS[vk])
        merged["visitor_key"] = vk
        _tls.data = merged
    else:
        _tls.data = incoming
    _tls.bound = True


def unbind_thread_session() -> None:
    _tls.bound = False
    _tls.data = None


class Session:
    @property
    def phone(self) -> str | None:
        return _store().get("phone")

    @phone.setter
    def phone(self, value: str | None) -> None:
        _store()["phone"] = value
        _touch()

    @property
    def user_id(self):
        return _store().get("user_id")

    @user_id.setter
    def user_id(self, value) -> None:
        _store()["user_id"] = value
        _touch()

    @property
    def access_token(self) -> str | None:
        return _store().get("access_token")

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        _store()["access_token"] = value
        _touch()

    @property
    def user_name(self) -> str | None:
        return _store().get("user_name")

    @user_name.setter
    def user_name(self, value: str | None) -> None:
        _store()["user_name"] = value
        _touch()

    @property
    def user_email(self) -> str | None:
        return _store().get("user_email")

    @user_email.setter
    def user_email(self, value: str | None) -> None:
        _store()["user_email"] = value
        _touch()

    @property
    def otp_pending(self) -> bool:
        return bool(_store().get("otp_pending"))

    @otp_pending.setter
    def otp_pending(self, value: bool) -> None:
        _store()["otp_pending"] = bool(value)
        _touch()

    @property
    def temp_user_id(self) -> str | None:
        return _store().get("temp_user_id")

    @temp_user_id.setter
    def temp_user_id(self, value: str | None) -> None:
        _store()["temp_user_id"] = value
        _touch()

    @property
    def is_authenticated(self) -> bool:
        d = _store()
        return bool(d.get("user_id") and d.get("access_token"))

    def ensure_visitor_key(self) -> str:
        current = str(_store().get("visitor_key") or "").strip()
        if not current:
            current = secrets.token_hex(16)
            _store()["visitor_key"] = current
            _touch()
        return current

    def ensure_temp_user_id(self) -> str:
        """Guest/cart temp id used by /api/crux/addcart (same shape as website)."""
        current = self.temp_user_id
        if not current:
            current = f"TEMP_UID{secrets.token_hex(6)}{int(time.time()) % 100000}"
            self.temp_user_id = current
        return current

    def set_from_login(self, data: dict) -> None:
        user = data.get("user") or {}
        d = _store()
        d["user_id"] = user.get("id")
        d["user_name"] = user.get("name")
        d["user_email"] = user.get("email")
        phone = user.get("phone")
        if phone not in (None, ""):
            d["phone"] = phone
        d["access_token"] = data.get("access_token")
        d["otp_pending"] = False
        self.ensure_temp_user_id()
        _touch()

    def replace_from_app_login(self, data: dict) -> None:
        """Drop the previous browser session, then login.

        Flutter WebView keeps one Flask cookie / visitor_key. If we only
        overwrite user_id, list_chats still returns the old account's
        threads via visitor_key. A new visitor_key is required.
        """
        self.clear()
        self.set_from_login(data)

    def clear(self) -> None:
        d = _store()
        old = str(d.get("visitor_key") or "").strip()
        if old:
            _SERVER_SESSIONS.pop(old, None)
        d.clear()
        d["visitor_key"] = secrets.token_hex(16)
        _touch()

    def summary(self) -> dict:
        return {
            "authenticated": self.is_authenticated,
            "user_id": self.user_id,
            "name": self.user_name,
            "phone": self.phone,
            "email": self.user_email,
            "otp_pending": self.otp_pending,
            "temp_user_id": self.temp_user_id,
        }


session = Session()
