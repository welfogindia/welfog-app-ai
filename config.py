import os
import re


def _load_env_file() -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


_load_env_file()

# Google Gemini only (OpenAI / Grok removed)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Optional extras — tried on 429 / failure:
# GEMINI_API_KEY_2=...  GEMINI_API_KEY_3=...  or GEMINI_API_KEYS=k1,k2

# Token-saving model split by message shape (length / digits / history) — NOT keyword maps.
# AI understands intent; we only pick lite vs full model size.
GEMINI_MODEL_FAST = os.getenv("GEMINI_MODEL_FAST", "gemini-flash-lite-latest")
GEMINI_MODEL_FULL = os.getenv("GEMINI_MODEL_FULL", "gemini-flash-latest")
# Legacy alias
GEMINI_MODEL = os.getenv("GEMINI_MODEL", GEMINI_MODEL_FULL)
GEMINI_MODEL_FALLBACKS = os.getenv(
    "GEMINI_MODEL_FALLBACKS",
    "gemini-flash-lite-latest,gemini-flash-latest",
)
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai",
).rstrip("/")

# Live company knowledge (Aidata Search) — prefer over static admin KB dump
AIDATA_SEARCH_ENABLED = str(os.getenv("AIDATA_SEARCH_ENABLED", "1")).strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
AIDATA_SEARCH_URL = (
    os.getenv("AIDATA_SEARCH_URL") or "https://aidata.welfog.com/api/search"
).strip()
AIDATA_SEARCH_API_KEY = (
    os.getenv("AIDATA_SEARCH_API_KEY") or "welfog-search-2026"
).strip()
AIDATA_SEARCH_TIMEOUT = float(os.getenv("AIDATA_SEARCH_TIMEOUT") or "12")

_BLOCKED_MODELS = frozenset(
    {
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro",
    }
)


def collect_gemini_keys() -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        v = (raw or "").strip()
        if not v or v in seen:
            return
        seen.add(v)
        keys.append(v)

    add(GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY", ""))
    for i in range(2, 9):
        add(os.getenv(f"GEMINI_API_KEY_{i}", ""))
    extra = (os.getenv("GEMINI_API_KEYS") or "").strip()
    if extra:
        for part in extra.split(","):
            add(part)
    return keys


def _clean_model(name: str) -> str | None:
    m = (name or "").strip()
    if not m or m in _BLOCKED_MODELS:
        return None
    return m


def classify_query_demand(text: str, *, history_len: int = 0) -> str:
    """
    Model tier from message shape only — NO keyword/intent dictionaries.
    AI understands meaning (greeting vs shop vs support); we only size the call.
    """
    t = (text or "").strip()
    if not t:
        return "low"
    # Pure digits → phone/OTP shape (login tools) → fuller model
    if re.fullmatch(r"\d{4,10}", t):
        return "high"
    # Long / multi-turn → fuller budget; short → lite (AI still decides tools)
    if len(t) > 80 or history_len >= 6:
        return "high"
    return "low"


def gemini_models_for_demand(demand: str = "low") -> list[str]:
    """Ordered models: primary for demand first, then one fallback on error only."""
    d = (demand or "low").strip().lower()
    if d == "high":
        primary = _clean_model(GEMINI_MODEL_FULL) or "gemini-flash-latest"
        secondary = _clean_model(GEMINI_MODEL_FAST) or "gemini-flash-lite-latest"
    else:
        primary = _clean_model(GEMINI_MODEL_FAST) or "gemini-flash-lite-latest"
        secondary = _clean_model(GEMINI_MODEL_FULL) or "gemini-flash-latest"

    ordered = [primary, secondary]
    out: list[str] = []
    seen: set[str] = set()
    for m in ordered:
        if not m or m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out or ["gemini-flash-lite-latest"]


def gemini_models() -> list[str]:
    """Default list (full-first) for backwards compatibility."""
    return gemini_models_for_demand("high")


# Welfog production API (do NOT use localhost)
WELFOG_API_BASE = os.getenv("WELFOG_API_BASE", "https://welfogapi.welfog.com").rstrip("/")
# Public website (product/order deep links in chat UI)
WELFOG_WEB_BASE = os.getenv("WELFOG_WEB_BASE", "https://welfog.com").rstrip("/")
# Welfog Play (short-video/reels platform) API base
PLAY_API_BASE = os.getenv("PLAY_API_BASE", "https://api.welfog.com").rstrip("/")
PLAY_DEVICE_ID = os.getenv("PLAY_DEVICE_ID", "welfog-ai-agent")

# OpenSearch product catalog (replaces /api/v2/products/search for browse)
OPENSEARCH_BASE = os.getenv("OPENSEARCH_BASE", "https://s.welfog.com").rstrip("/")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "os_admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "Welfog@952172!")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "products_v1")
OPENSEARCH_SIZE = int(os.getenv("OPENSEARCH_SIZE", "20") or "20")
OPENSEARCH_TIMEOUT = float(os.getenv("OPENSEARCH_TIMEOUT", "20") or "20")

MAX_AGENT_STEPS = 6
REQUEST_TIMEOUT = 45
MAX_TOOL_RESULT_CHARS = 12000

# Tools that usually need only one call then a text reply (skip extra tool loops)
ONE_SHOT_TOOLS = frozenset(
    {
        "search_products",
        "get_today_deals",
        "get_related_products",
        "get_my_wishlist",
        "get_purchase_history",
        "get_my_orders",
        "get_order_details",
        "get_my_cart",
        "get_cart_summary",
        "get_my_profile",
        "get_my_addresses",
        "search_company_knowledge",
        "get_session_status",
        "autosuggest",
        "get_banners",
        "play_get_my_profile",
        "play_update_my_profile",
        "play_get_my_reels",
        "play_search",
        "play_get_feed",
        "play_get_user_profile",
    }
)

# Admin / AI MySQL database (XAMPP)
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "welfog_ai_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Welfog@952172!")
MYSQL_DB = os.getenv("MYSQL_DB", "welfog_ai")
 
# MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
# MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
# MYSQL_USER = os.getenv("MYSQL_USER", "root")
# MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
# MYSQL_DB = os.getenv("MYSQL_DB", "welfog-app-ai")

# Default admin (created on first boot if missing)
ADMIN_DEFAULT_USER = os.getenv("ADMIN_DEFAULT_USER", "admin")
ADMIN_DEFAULT_PASS = os.getenv("ADMIN_DEFAULT_PASS", "admin123")

SECRET_KEY = os.getenv("SECRET_KEY", "welfog-ai-admin-change-me-in-production")
