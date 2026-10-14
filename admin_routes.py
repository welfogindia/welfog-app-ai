"""Admin panel routes: /admin"""

from __future__ import annotations

import json
from functools import wraps

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from db import (
    dashboard_stats,
    delete_api,
    delete_chat_session,
    delete_knowledge,
    get_api,
    get_chat_messages,
    get_chat_session,
    get_knowledge,
    get_setting,
    list_apis,
    list_chat_sessions,
    list_knowledge,
    save_api,
    save_knowledge,
    set_setting,
    verify_admin,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


@admin_bp.get("/login")
def login():
    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html")


@admin_bp.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    admin = verify_admin(username, password)
    if not admin:
        flash("Invalid username or password", "error")
        return redirect(url_for("admin.login"))
    session["admin_id"] = admin["id"]
    session["admin_user"] = admin["username"]
    return redirect(url_for("admin.dashboard"))


@admin_bp.get("/logout")
def logout():
    session.pop("admin_id", None)
    session.pop("admin_user", None)
    return redirect(url_for("admin.login"))


@admin_bp.get("/")
@login_required
def dashboard():
    stats = dashboard_stats()
    recent = list_chat_sessions(limit=8)
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent=recent,
        admin_user=session.get("admin_user"),
    )


@admin_bp.get("/chats")
@login_required
def chats():
    return render_template(
        "admin/chats.html",
        chats=list_chat_sessions(limit=200),
        admin_user=session.get("admin_user"),
    )


@admin_bp.get("/chats/<chat_id>")
@login_required
def chat_view(chat_id):
    chat = get_chat_session(chat_id)
    if not chat:
        flash("Chat not found", "error")
        return redirect(url_for("admin.chats"))
    messages = get_chat_messages(chat_id)
    return render_template(
        "admin/chat_view.html",
        chat=chat,
        messages=messages,
        admin_user=session.get("admin_user"),
    )


@admin_bp.post("/chats/<chat_id>/delete")
@login_required
def chat_delete(chat_id):
    delete_chat_session(chat_id)
    flash("Chat deleted", "ok")
    return redirect(url_for("admin.chats"))


@admin_bp.get("/knowledge")
@login_required
def knowledge():
    return render_template(
        "admin/knowledge.html",
        items=list_knowledge(),
        admin_user=session.get("admin_user"),
    )


@admin_bp.get("/knowledge/new")
@login_required
def knowledge_new():
    return render_template(
        "admin/knowledge_form.html",
        item=None,
        admin_user=session.get("admin_user"),
    )


@admin_bp.get("/knowledge/<int:kid>/edit")
@login_required
def knowledge_edit(kid):
    item = get_knowledge(kid)
    if not item:
        flash("Not found", "error")
        return redirect(url_for("admin.knowledge"))
    return render_template(
        "admin/knowledge_form.html",
        item=item,
        admin_user=session.get("admin_user"),
    )


@admin_bp.post("/knowledge/save")
@login_required
def knowledge_save():
    kid = request.form.get("id")
    kid_int = int(kid) if kid else None
    save_knowledge(
        kid=kid_int,
        title=(request.form.get("title") or "").strip(),
        category=(request.form.get("category") or "general").strip(),
        content=(request.form.get("content") or "").strip(),
        is_active=bool(request.form.get("is_active")),
        priority=int(request.form.get("priority") or 0),
    )
    flash("Knowledge saved — AI will use it automatically", "ok")
    return redirect(url_for("admin.knowledge"))


@admin_bp.post("/knowledge/<int:kid>/delete")
@login_required
def knowledge_delete(kid):
    delete_knowledge(kid)
    flash("Deleted", "ok")
    return redirect(url_for("admin.knowledge"))


@admin_bp.get("/apis")
@login_required
def apis():
    return render_template(
        "admin/apis.html",
        apis=list_apis(),
        admin_user=session.get("admin_user"),
    )


@admin_bp.get("/apis/new")
@login_required
def apis_new():
    return render_template(
        "admin/api_form.html",
        api=None,
        admin_user=session.get("admin_user"),
    )


@admin_bp.get("/apis/<int:api_id>/edit")
@login_required
def apis_edit(api_id):
    api = get_api(api_id)
    if not api:
        flash("Not found", "error")
        return redirect(url_for("admin.apis"))
    return render_template(
        "admin/api_form.html",
        api=api,
        admin_user=session.get("admin_user"),
    )


@admin_bp.post("/apis/save")
@login_required
def apis_save():
    api_id = request.form.get("id")
    api_id_int = int(api_id) if api_id else None
    tool_name = (request.form.get("tool_name") or "").strip().replace(" ", "_")
    # validate query params JSON
    qjson = (request.form.get("query_params_json") or "").strip()
    if qjson:
        try:
            json.loads(qjson)
        except Exception:
            flash("Query params JSON invalid", "error")
            return redirect(request.referrer or url_for("admin.apis"))
    hjson = (request.form.get("headers_json") or "").strip()
    if hjson:
        try:
            json.loads(hjson)
        except Exception:
            flash("Headers JSON invalid", "error")
            return redirect(request.referrer or url_for("admin.apis"))
    bjson = (request.form.get("body_template_json") or "").strip()
    if bjson:
        try:
            json.loads(bjson)
        except Exception:
            flash("Body template JSON invalid", "error")
            return redirect(request.referrer or url_for("admin.apis"))

    try:
        save_api(
            {
                "name": (request.form.get("name") or "").strip(),
                "tool_name": tool_name,
                "description": (request.form.get("description") or "").strip(),
                "method": request.form.get("method") or "GET",
                "url": (request.form.get("url") or "").strip(),
                "headers_json": hjson,
                "query_params_json": qjson,
                "body_template_json": bjson,
                "auth_mode": request.form.get("auth_mode") or "none",
                "response_hint": (request.form.get("response_hint") or "").strip(),
                "is_active": bool(request.form.get("is_active")),
                "sort_order": int(request.form.get("sort_order") or 0),
            },
            api_id=api_id_int,
        )
    except Exception as e:
        flash(f"Save failed: {e}", "error")
        return redirect(request.referrer or url_for("admin.apis"))

    flash("API saved — AI can call it as a tool now", "ok")
    return redirect(url_for("admin.apis"))


@admin_bp.post("/apis/<int:api_id>/delete")
@login_required
def apis_delete(api_id):
    delete_api(api_id)
    flash("API deleted", "ok")
    return redirect(url_for("admin.apis"))


@admin_bp.get("/settings")
@login_required
def settings():
    return render_template(
        "admin/settings.html",
        extra_system_prompt=get_setting("extra_system_prompt", ""),
        admin_user=session.get("admin_user"),
    )


@admin_bp.post("/settings")
@login_required
def settings_save():
    set_setting("extra_system_prompt", request.form.get("extra_system_prompt") or "")
    flash("Settings saved", "ok")
    return redirect(url_for("admin.settings"))
