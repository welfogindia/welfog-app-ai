"""MySQL layer for my_ai database — chats, knowledge, API registry, admins."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

import pymysql
from pymysql.cursors import DictCursor
from werkzeug.security import check_password_hash, generate_password_hash

from config import (
    ADMIN_DEFAULT_PASS,
    ADMIN_DEFAULT_USER,
    MYSQL_DB,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)


def get_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )


@contextmanager
def db_cursor() -> Iterator[Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS admins (
      id INT AUTO_INCREMENT PRIMARY KEY,
      username VARCHAR(80) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
      id VARCHAR(64) PRIMARY KEY,
      title VARCHAR(255) NOT NULL DEFAULT 'New chat',
      visitor_key VARCHAR(120) NULL,
      user_phone VARCHAR(20) NULL,
      user_id INT NULL,
      user_name VARCHAR(120) NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_updated (updated_at),
      INDEX idx_phone (user_phone)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
      id BIGINT AUTO_INCREMENT PRIMARY KEY,
      chat_id VARCHAR(64) NOT NULL,
      role VARCHAR(20) NOT NULL,
      content MEDIUMTEXT NOT NULL,
      ui_html MEDIUMTEXT NULL,
      meta_json MEDIUMTEXT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      INDEX idx_chat (chat_id),
      CONSTRAINT fk_chat FOREIGN KEY (chat_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_items (
      id INT AUTO_INCREMENT PRIMARY KEY,
      title VARCHAR(200) NOT NULL,
      category VARCHAR(100) NOT NULL DEFAULT 'general',
      content MEDIUMTEXT NOT NULL,
      is_active TINYINT(1) NOT NULL DEFAULT 1,
      priority INT NOT NULL DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_active (is_active, priority)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS api_registry (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(120) NOT NULL,
      tool_name VARCHAR(80) NOT NULL UNIQUE,
      description TEXT NOT NULL,
      method VARCHAR(10) NOT NULL DEFAULT 'GET',
      url TEXT NOT NULL,
      headers_json TEXT NULL,
      query_params_json TEXT NULL,
      body_template_json TEXT NULL,
      auth_mode VARCHAR(40) NOT NULL DEFAULT 'none',
      response_hint TEXT NULL,
      is_active TINYINT(1) NOT NULL DEFAULT 1,
      sort_order INT NOT NULL DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_settings (
      setting_key VARCHAR(100) PRIMARY KEY,
      setting_value MEDIUMTEXT NOT NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def init_db():
    """Create tables and seed default admin + sample knowledge/settings."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for sql in SCHEMA_SQL:
                cur.execute(sql)

            cur.execute(
                """
                SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=DATABASE()
                  AND TABLE_NAME='chat_sessions'
                  AND COLUMN_NAME='visitor_key'
                """
            )
            row = cur.fetchone() or {}
            if int(row.get("c") or 0) == 0:
                cur.execute(
                    "ALTER TABLE chat_sessions ADD COLUMN visitor_key VARCHAR(120) NULL"
                )

            cur.execute("SELECT id FROM admins WHERE username=%s LIMIT 1", (ADMIN_DEFAULT_USER,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                    (ADMIN_DEFAULT_USER, generate_password_hash(ADMIN_DEFAULT_PASS)),
                )

            cur.execute("SELECT setting_key FROM ai_settings WHERE setting_key='extra_system_prompt'")
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO ai_settings (setting_key, setting_value) VALUES (%s, %s)",
                    (
                        "extra_system_prompt",
                        "Use company knowledge from admin panel when answering about policies, brand, and support.",
                    ),
                )

            cur.execute("SELECT id FROM knowledge_items LIMIT 1")
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO knowledge_items (title, category, content, is_active, priority)
                    VALUES (%s, %s, %s, 1, 10)
                    """,
                    (
                        "About Welfog",
                        "company",
                        "Welfog is an Indian e-commerce marketplace (welfog.com). Customers can shop products, track orders, manage cart/wishlist, and login via phone OTP. Support helps with orders, delivery, and returns.",
                    ),
                )
    finally:
        conn.close()


# ---------- Auth ----------
def verify_admin(username: str, password: str) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM admins WHERE username=%s LIMIT 1", (username,))
        row = cur.fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return {"id": row["id"], "username": row["username"]}
    return None


# ---------- Settings ----------
def get_setting(key: str, default: str = "") -> str:
    with db_cursor() as cur:
        cur.execute("SELECT setting_value FROM ai_settings WHERE setting_key=%s", (key,))
        row = cur.fetchone()
    return row["setting_value"] if row else default


def set_setting(key: str, value: str):
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)
            """,
            (key, value),
        )


def list_settings() -> list[dict]:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM ai_settings ORDER BY setting_key")
        return list(cur.fetchall())


# ---------- Knowledge ----------
def list_knowledge(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM knowledge_items"
    if active_only:
        sql += " WHERE is_active=1"
    sql += " ORDER BY priority DESC, id DESC"
    with db_cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def get_knowledge(kid: int) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM knowledge_items WHERE id=%s", (kid,))
        return cur.fetchone()


def save_knowledge(
    *,
    kid: int | None,
    title: str,
    category: str,
    content: str,
    is_active: bool = True,
    priority: int = 0,
) -> int:
    with db_cursor() as cur:
        if kid:
            cur.execute(
                """
                UPDATE knowledge_items
                SET title=%s, category=%s, content=%s, is_active=%s, priority=%s
                WHERE id=%s
                """,
                (title, category, content, 1 if is_active else 0, priority, kid),
            )
            return kid
        cur.execute(
            """
            INSERT INTO knowledge_items (title, category, content, is_active, priority)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (title, category, content, 1 if is_active else 0, priority),
        )
        return cur.lastrowid


def delete_knowledge(kid: int):
    with db_cursor() as cur:
        cur.execute("DELETE FROM knowledge_items WHERE id=%s", (kid,))


def knowledge_prompt_block() -> str:
    items = list_knowledge(active_only=True)
    if not items:
        return ""
    lines = ["\n\n[Company / Admin Knowledge — treat as trusted facts]"]
    for it in items:
        lines.append(f"### {it['title']} ({it['category']})\n{it['content']}")
    return "\n\n".join(lines)


# ---------- API registry ----------
def list_apis(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM api_registry"
    if active_only:
        sql += " WHERE is_active=1"
    sql += " ORDER BY sort_order ASC, id ASC"
    with db_cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def get_api(api_id: int) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM api_registry WHERE id=%s", (api_id,))
        return cur.fetchone()


def get_api_by_tool(tool_name: str) -> dict | None:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM api_registry WHERE tool_name=%s AND is_active=1 LIMIT 1",
            (tool_name,),
        )
        return cur.fetchone()


def save_api(data: dict, api_id: int | None = None) -> int:
    fields = (
        data.get("name"),
        data.get("tool_name"),
        data.get("description"),
        (data.get("method") or "GET").upper(),
        data.get("url"),
        data.get("headers_json") or "",
        data.get("query_params_json") or "",
        data.get("body_template_json") or "",
        data.get("auth_mode") or "none",
        data.get("response_hint") or "",
        1 if data.get("is_active", True) else 0,
        int(data.get("sort_order") or 0),
    )
    with db_cursor() as cur:
        if api_id:
            cur.execute(
                """
                UPDATE api_registry SET
                  name=%s, tool_name=%s, description=%s, method=%s, url=%s,
                  headers_json=%s, query_params_json=%s, body_template_json=%s,
                  auth_mode=%s, response_hint=%s, is_active=%s, sort_order=%s
                WHERE id=%s
                """,
                (*fields, api_id),
            )
            return api_id
        cur.execute(
            """
            INSERT INTO api_registry
              (name, tool_name, description, method, url, headers_json, query_params_json,
               body_template_json, auth_mode, response_hint, is_active, sort_order)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            fields,
        )
        return cur.lastrowid


def delete_api(api_id: int):
    with db_cursor() as cur:
        cur.execute("DELETE FROM api_registry WHERE id=%s", (api_id,))


# ---------- Chats ----------
def upsert_chat_session(
    chat_id: str,
    *,
    title: str | None = None,
    visitor_key: str | None = None,
    user_phone: str | None = None,
    user_id: int | None = None,
    user_name: str | None = None,
):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM chat_sessions WHERE id=%s", (chat_id,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                """
                INSERT INTO chat_sessions (id, title, visitor_key, user_phone, user_id, user_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    chat_id,
                    title or "New chat",
                    visitor_key,
                    user_phone,
                    user_id,
                    user_name,
                ),
            )
        else:
            parts = []
            vals: list[Any] = []
            if title is not None:
                parts.append("title=%s")
                vals.append(title)
            if visitor_key is not None:
                parts.append("visitor_key=%s")
                vals.append(visitor_key)
            if user_phone is not None:
                parts.append("user_phone=%s")
                vals.append(user_phone)
            if user_id is not None:
                parts.append("user_id=%s")
                vals.append(user_id)
            if user_name is not None:
                parts.append("user_name=%s")
                vals.append(user_name)
            if parts:
                vals.append(chat_id)
                cur.execute(
                    f"UPDATE chat_sessions SET {', '.join(parts)} WHERE id=%s",
                    vals,
                )


def add_chat_message(chat_id: str, role: str, content: str, ui: Any = None, meta: Any = None):
    ui_html = json.dumps(ui, ensure_ascii=False, default=str) if ui is not None else None
    meta_json = json.dumps(meta, ensure_ascii=False, default=str) if meta is not None else None
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_messages (chat_id, role, content, ui_html, meta_json)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (chat_id, role, content, ui_html, meta_json),
        )
        cur.execute(
            "UPDATE chat_sessions SET updated_at=%s WHERE id=%s",
            (datetime.utcnow(), chat_id),
        )


def list_chat_sessions(limit: int = 100) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT s.*,
              (SELECT COUNT(*) FROM chat_messages m WHERE m.chat_id=s.id) AS message_count
            FROM chat_sessions s
            ORDER BY s.updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def list_user_chat_sessions(
    *,
    user_id: int | None = None,
    phone: str | None = None,
    visitor_key: str | None = None,
    limit: int = 100,
) -> list[dict]:
    uid = user_id if user_id not in (None, "", 0) else None
    ph = str(phone or "").strip() or None
    vk = str(visitor_key or "").strip() or None
    if not uid and not ph and not vk:
        return []
    clauses: list[str] = []
    vals: list[Any] = []
    if uid:
        clauses.append("s.user_id=%s")
        vals.append(uid)
    if ph:
        clauses.append("s.user_phone=%s")
        vals.append(ph)
    if vk:
        clauses.append("s.visitor_key=%s")
        vals.append(vk)
    where = " OR ".join(clauses)
    vals.append(limit)
    with db_cursor() as cur:
        cur.execute(
            f"""
            SELECT s.*,
              (SELECT COUNT(*) FROM chat_messages m WHERE m.chat_id=s.id) AS message_count
            FROM chat_sessions s
            WHERE {where}
            ORDER BY s.updated_at DESC
            LIMIT %s
            """,
            vals,
        )
        return list(cur.fetchall())


def get_chat_messages(chat_id: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, chat_id, role, content, ui_html, meta_json, created_at
            FROM chat_messages
            WHERE chat_id=%s
            ORDER BY id ASC
            """,
            (chat_id,),
        )
        rows = list(cur.fetchall())
    for r in rows:
        raw = r.get("ui_html")
        if raw:
            try:
                r["ui"] = json.loads(raw)
            except Exception:
                r["ui"] = []
        else:
            r["ui"] = []
        raw_meta = r.get("meta_json")
        if raw_meta:
            try:
                meta = json.loads(raw_meta)
                if isinstance(meta, dict):
                    if meta.get("images") and isinstance(meta.get("images"), list):
                        r["images"] = [img for img in meta["images"] if img]
                        r["image"] = r["images"][0] if r["images"] else None
                    elif meta.get("image"):
                        r["images"] = [meta["image"]]
                        r["image"] = meta["image"]
            except Exception:
                pass
    return rows


def get_chat_session(chat_id: str) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM chat_sessions WHERE id=%s", (chat_id,))
        return cur.fetchone()


def delete_chat_session(chat_id: str):
    with db_cursor() as cur:
        cur.execute("DELETE FROM chat_messages WHERE chat_id=%s", (chat_id,))
        cur.execute("DELETE FROM chat_sessions WHERE id=%s", (chat_id,))


def dashboard_stats() -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM chat_sessions")
        chats = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM chat_messages")
        msgs = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM knowledge_items WHERE is_active=1")
        knowledge = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM api_registry WHERE is_active=1")
        apis = cur.fetchone()["c"]
    return {
        "chats": chats,
        "messages": msgs,
        "knowledge": knowledge,
        "apis": apis,
    }
