"""Welfog Play (short-video / reels platform) isolated integration module.

Provides:
- Play API client wrappers
- Dynamic current-user identity resolution (numeric user_id -> Mongo _id)
- Conversational profile editing with field preservation
- User posts / uploaded reels extraction
- Play search & discovery feed
- UI card normalization for thumbnails, profile, and reel shortLinks
- OpenAI function tool definitions for agent tool-calling
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from config import PLAY_API_BASE, PLAY_DEVICE_ID
from session import session

PLAY_TIMEOUT = 12


def _clean_str(val: Any) -> str:
    return str(val or "").strip()


def _format_count(val: Any) -> str:
    try:
        n = int(val)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
        if n >= 1_000:
            return f"{n / 1_000:.1f}K".replace(".0K", "K")
        return str(n)
    except Exception:
        return "0"


def _format_likes(likes: Any) -> str:
    if isinstance(likes, list):
        return _format_count(len(likes))
    num = _clean_str(likes)
    if num.isdigit():
        return _format_count(int(num))
    return "0"


def _format_views(views: Any) -> str:
    num = _clean_str(views)
    if num.isdigit():
        return _format_count(int(num))
    return "0"


class PlayClient:
    """HTTP client for Welfog Play APIs."""

    def __init__(self, base_url: str = PLAY_API_BASE):
        self.base_url = base_url.rstrip("/")
        self.http = requests.Session()
        self.http.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "WelfogAI-Play/1.0",
                "x-device-id": PLAY_DEVICE_ID,
            }
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        try:
            resp = self.http.request(
                method.upper(),
                url,
                params=params,
                json=json_body,
                timeout=PLAY_TIMEOUT,
            )
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:1000], "status_code": resp.status_code}
            if not resp.ok and isinstance(data, dict):
                data.setdefault("http_status", resp.status_code)
            return data
        except requests.RequestException as err:
            return {"error": True, "message": str(err)}

    def get(self, path: str, params: dict | None = None) -> Any:
        return self.request("GET", path, params=params)

    def patch(self, path: str, json_body: dict | None = None) -> Any:
        res = self.request("PATCH", path, json_body=json_body or {})
        # If server returns 405 Method Not Allowed or 404, fallback to PUT
        if isinstance(res, dict) and res.get("http_status") in (404, 405):
            res = self.request("PUT", path, json_body=json_body or {})
        return res

    def put(self, path: str, json_body: dict | None = None) -> Any:
        return self.request("PUT", path, json_body=json_body or {})


play_api = PlayClient()


# ---------------------------------------------------------------------------
# Core Play API wrappers
# ---------------------------------------------------------------------------

def get_play_feed(user_id: Any = None) -> dict:
    """Fetch Play feed reels for discovery/trending."""
    uid = user_id if user_id not in (None, "") else (session.user_id or 0)
    params = {"userId": str(uid)}
    res = play_api.get("/api/reels/shownew", params=params)
    if not isinstance(res, dict) or res.get("error"):
        return {"ok": False, "error": True, "message": (res or {}).get("message", "Failed to fetch Play feed")}
    reels = res.get("reels") if isinstance(res.get("reels"), list) else []
    return {
        "ok": True,
        "count": len(reels),
        "reels": reels,
        "direction": res.get("direction", "next"),
    }


def get_play_profile(user_id: Any) -> dict:
    """Fetch Play profile by numeric user id or Mongo id."""
    uid = _clean_str(user_id)
    if not uid:
        return {"ok": False, "error": True, "message": "user_id is required"}
    res = play_api.get(f"/api/users/{uid}")
    if not isinstance(res, dict) or res.get("error") or res.get("http_status") in (404, 500):
        msg = (res or {}).get("message") or "Play profile not found"
        return {"ok": False, "error": True, "message": msg}

    user_data = res.get("data") if isinstance(res.get("data"), dict) else res
    if not isinstance(user_data, dict) or not user_data.get("_id"):
        return {"ok": False, "error": True, "message": "Invalid Play profile response"}

    return {
        "ok": True,
        "user": user_data,
        "_id": user_data.get("_id"),
        "userid": user_data.get("userid") or user_data.get("userId"),
        "username": user_data.get("username", ""),
        "name": user_data.get("name", ""),
        "bio": user_data.get("bio", ""),
        "profilePicture": user_data.get("profilePicture", ""),
        "followersCount": int(user_data.get("followersCount") or len(user_data.get("followers") or []) or 0),
        "followingCount": int(user_data.get("followingCount") or len(user_data.get("following") or []) or 0),
        "postCount": int(user_data.get("postCount") or 0),
        "isSuspended": bool(user_data.get("isSuspended", False)),
    }


def update_play_profile(mongo_user_id: str, updates: dict) -> dict:
    """Update Play profile for Mongo user _id (PATCH/PUT)."""
    mid = _clean_str(mongo_user_id)
    if not mid:
        return {"ok": False, "error": True, "message": "Mongo user ID is required to update Play profile"}
    res = play_api.patch(f"/api/users/{mid}", json_body=updates)
    if not isinstance(res, dict) or res.get("error") or res.get("http_status") in (400, 404, 500):
        msg = (res or {}).get("message") or "Failed to update Play profile"
        return {"ok": False, "error": True, "message": msg, "api_response": res}
    return {"ok": True, "updated": updates, "user": res}


def get_play_user_reels(mongo_user_id: str) -> dict:
    """Fetch user's uploaded Play reels via Mongo user _id."""
    mid = _clean_str(mongo_user_id)
    if not mid:
        return {"ok": False, "error": True, "message": "Mongo user ID is required"}
    res = play_api.get(f"/api/users/userpost/{mid}")
    if not isinstance(res, dict) or res.get("error") or res.get("http_status") in (404, 500):
        msg = (res or {}).get("message") or "Failed to load Play reels"
        return {"ok": False, "error": True, "message": msg}

    reels = res.get("reels") if isinstance(res.get("reels"), list) else []
    post_count = res.get("postCount") if res.get("postCount") is not None else len(reels)
    return {
        "ok": True,
        "user": res.get("user") or {},
        "postCount": post_count,
        "reels": reels,
    }


def search_play(
    query: str,
    *,
    user_page: int = 1,
    video_page: int = 1,
    user_limit: int = 10,
    video_limit: int = 20,
) -> dict:
    """Search Play creators and reels/videos by search query."""
    q = _clean_str(query)
    # Remove conversational command noise from search query
    clean_q = re.sub(
        r"(?i)\b(?:play\s+par|play\s+pe|play\s+reels?|search\s+on\s+play|search\s+play|search|dhundo|dikh?ao|batao|karo|reels?|videos?)\b",
        "",
        q,
    ).strip()
    clean_q = clean_q or q

    params = {
        "query": clean_q,
        "search": clean_q,
        "userPage": max(1, int(user_page or 1)),
        "videoPage": max(1, int(video_page or 1)),
        "userLimit": max(1, min(50, int(user_limit or 10))),
        "videoLimit": max(1, min(50, int(video_limit or 20))),
    }
    res = play_api.get("/api/users/search_populer", params=params)
    if not isinstance(res, dict) or res.get("error"):
        return {"ok": False, "error": True, "message": (res or {}).get("message", "Play search failed")}

    users = res.get("users") if isinstance(res.get("users"), list) else []
    videos = res.get("videos") if isinstance(res.get("videos"), list) else []
    return {
        "ok": True,
        "query": clean_q,
        "users": users,
        "videos": videos,
        "hasMoreUsers": bool(res.get("hasMoreUsers")),
        "hasMoreVideos": bool(res.get("hasMoreVideos")),
    }


# ---------------------------------------------------------------------------
# Current authenticated user helpers (Security & Identity resolution)
# ---------------------------------------------------------------------------

def _require_auth() -> dict | None:
    if not session.is_authenticated or not session.user_id:
        return {
            "error": True,
            "needs_login": True,
            "message": (
                "Welfog Play par apni profile ya uploaded reels access karne ke liye login zaroori hai. "
                "Kripya apna 10-digit mobile number share karein, main OTP bhej deta hoon."
            ),
        }
    return None


def get_current_user_play_profile() -> dict:
    """Resolve authenticated user's Play profile securely using session.user_id."""
    blocked = _require_auth()
    if blocked:
        return blocked
    return get_play_profile(session.user_id)


def update_current_user_play_profile(
    *,
    name: str | None = None,
    username: str | None = None,
    bio: str | None = None,
    email: str | None = None,
) -> dict:
    """Update authenticated user's Play profile with field preservation."""
    blocked = _require_auth()
    if blocked:
        return blocked

    # Fetch current profile to obtain Mongo _id and preserve existing values
    current = get_play_profile(session.user_id)
    if not current.get("ok"):
        return current

    mongo_id = current.get("_id")
    if not mongo_id:
        return {"error": True, "message": "Play profile identifier (_id) could not be resolved."}

    user_obj = current.get("user") or {}
    payload = {
        "name": user_obj.get("name", ""),
        "username": user_obj.get("username", ""),
        "email": user_obj.get("email", "") or session.user_email or "",
        "bio": user_obj.get("bio", ""),
    }

    changed_fields = []
    if name is not None and str(name).strip():
        payload["name"] = str(name).strip()
        changed_fields.append("name")
    if username is not None and str(username).strip():
        # Remove leading @ if user provided it
        payload["username"] = str(username).strip().lstrip("@")
        changed_fields.append("username")
    if bio is not None and str(bio).strip():
        payload["bio"] = str(bio).strip()
        changed_fields.append("bio")
    if email is not None and str(email).strip():
        payload["email"] = str(email).strip()
        changed_fields.append("email")

    if not changed_fields:
        return {
            "error": True,
            "message": (
                "Aapko Play profile mein kya update karna hai? "
                "Name, username, ya bio bata dijiye (jaise: 'username bablu_kumar kar do')."
            ),
        }

    res = update_play_profile(mongo_id, payload)
    if not res.get("ok"):
        return res

    # Verification: return updated view
    updated_profile = get_play_profile(session.user_id)
    return {
        "ok": True,
        "message": f"Play profile successfully updated ({', '.join(changed_fields)}).",
        "changed_fields": changed_fields,
        "profile": updated_profile.get("user") if updated_profile.get("ok") else payload,
        "_id": mongo_id,
        "username": payload["username"],
        "name": payload["name"],
        "bio": payload["bio"],
    }


def get_current_user_play_reels() -> dict:
    """Fetch authenticated user's uploaded reels using resolved Mongo _id."""
    blocked = _require_auth()
    if blocked:
        return blocked

    profile = get_play_profile(session.user_id)
    if not profile.get("ok"):
        return profile

    mongo_id = profile.get("_id")
    if not mongo_id:
        return {"error": True, "message": "Play profile identifier (_id) could not be resolved."}

    return get_play_user_reels(mongo_id)


# ---------------------------------------------------------------------------
# Tool definitions for Agent Function Calling
# ---------------------------------------------------------------------------

PLAY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "play_get_my_profile",
            "description": (
                "Get the logged-in user's Welfog Play profile (posts count, followers count, "
                "following count, bio, username, display name, avatar). Requires login."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_update_my_profile",
            "description": (
                "Update the logged-in user's Welfog Play profile. Only updates provided fields "
                "(name, username, bio, email). Preserves existing fields without overwriting them. "
                "If user says 'profile edit karni hai' without specifying changes, ask them what to update. "
                "Requires login."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "New display name"},
                    "username": {"type": "string", "description": "New Play username (without @)"},
                    "bio": {"type": "string", "description": "New profile bio / description"},
                    "email": {"type": "string", "description": "Optional email address"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_get_my_reels",
            "description": (
                "Get the logged-in user's uploaded Welfog Play reels/videos with post count, "
                "captions, views, and destination shortLinks. Requires login."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_search",
            "description": (
                "Search Welfog Play for creators/users and reels/videos by keyword, name, or topic "
                "(e.g. 'bablu', 'backend developer', 'funny', 'fashion'). "
                "Returns matching creators and reel thumbnails with destination shortLinks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Clean search term or creator name/topic (extract meaning from user sentence)",
                    },
                    "user_page": {"type": "integer", "description": "User results page, default 1"},
                    "video_page": {"type": "integer", "description": "Reels results page, default 1"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_get_feed",
            "description": (
                "Discover trending / recent Welfog Play reels feed. "
                "Returns reel thumbnails, creator names, views, captions, and shortLinks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Optional user id context"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_get_user_profile",
            "description": "Get a public Play profile for any creator by numeric user id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Creator numeric user id"},
                },
                "required": ["user_id"],
            },
        },
    },
]

PLAY_TOOL_NAMES = frozenset({t["function"]["name"] for t in PLAY_TOOLS})


def is_play_tool(name: str) -> bool:
    return name in PLAY_TOOL_NAMES


def execute_play_tool(name: str, args: dict) -> dict:
    """Dispatcher for Play tools."""
    args = args or {}
    try:
        if name == "play_get_my_profile":
            return get_current_user_play_profile()
        if name == "play_update_my_profile":
            return update_current_user_play_profile(
                name=args.get("name"),
                username=args.get("username"),
                bio=args.get("bio"),
                email=args.get("email"),
            )
        if name == "play_get_my_reels":
            return get_current_user_play_reels()
        if name == "play_search":
            return search_play(
                query=args.get("query", ""),
                user_page=args.get("user_page", 1),
                video_page=args.get("video_page", 1),
            )
        if name == "play_get_feed":
            return get_play_feed(user_id=args.get("user_id"))
        if name == "play_get_user_profile":
            return get_play_profile(args.get("user_id", ""))
        return {"error": True, "message": f"Unknown Play tool: {name}"}
    except Exception as err:
        return {"error": True, "message": f"Play tool {name} failed: {err}"}


# ---------------------------------------------------------------------------
# UI Card normalization (Reel cards & Profile cards for frontend)
# ---------------------------------------------------------------------------

def _extract_shortlink(reel: dict) -> str | None:
    links = reel.get("shortLinks")
    if isinstance(links, list) and links:
        first = links[0]
        if isinstance(first, dict) and first.get("shortLink"):
            return str(first["shortLink"]).strip()
        if isinstance(first, str) and first.strip():
            return first.strip()
    return None


def _normalize_reel_card(r: dict) -> dict | None:
    if not isinstance(r, dict):
        return None
    rid = r.get("_id") or r.get("id")
    caption = _clean_str(r.get("caption") or "Welfog Play Reel")
    thumb = _clean_str(r.get("thumbnailUrl") or r.get("thumbnail") or r.get("coverImage"))
    short_link = _extract_shortlink(r)

    # Views & likes
    views = r.get("views") or 0
    likes = r.get("likes") or []
    likes_count = len(likes) if isinstance(likes, list) else (int(likes) if str(likes).isdigit() else 0)

    creator_name = _clean_str(r.get("name") or "Creator")
    username = _clean_str(r.get("username") or "")

    return {
        "type": "play_reel",
        "id": rid,
        "caption": caption,
        "thumbnail": thumb,
        "views": _format_count(views),
        "likes": _format_count(likes_count),
        "creator_name": creator_name,
        "username": username,
        "href": short_link,
        "created_at": _clean_str(r.get("createdAt")),
    }


def _normalize_user_card(u: dict) -> dict | None:
    if not isinstance(u, dict):
        return None
    uid = u.get("userid") or u.get("userId") or u.get("_id")
    name = _clean_str(u.get("name") or "Play Creator")
    username = _clean_str(u.get("username") or "")
    pic = _clean_str(u.get("profilePicture") or "")
    bio = _clean_str(u.get("bio") or "")
    followers = u.get("followersCount") or (len(u.get("followers")) if isinstance(u.get("followers"), list) else 0)

    return {
        "type": "play_user",
        "user_id": uid,
        "name": name,
        "username": username,
        "profile_picture": pic,
        "bio": bio,
        "followers_count": _format_count(followers),
    }


def pick_play_ui(tool_name: str, data: dict) -> list[dict]:
    """Build UI card representations from Play tool results."""
    if not isinstance(data, dict) or data.get("error"):
        return []

    cards: list[dict] = []

    # 1. Profile operations
    if tool_name in ("play_get_my_profile", "play_get_user_profile"):
        user = data.get("user") or data
        if isinstance(user, dict) and user.get("_id"):
            cards.append(
                {
                    "type": "play_profile",
                    "user_id": user.get("userid") or user.get("userId") or session.user_id,
                    "mongo_id": user.get("_id"),
                    "name": user.get("name") or session.user_name or "Play Creator",
                    "username": user.get("username") or "",
                    "bio": user.get("bio") or "",
                    "profile_picture": user.get("profilePicture") or "",
                    "post_count": int(user.get("postCount") or 0),
                    "followers_count": int(
                        user.get("followersCount") or len(user.get("followers") or []) or 0
                    ),
                    "following_count": int(
                        user.get("followingCount") or len(user.get("following") or []) or 0
                    ),
                    "is_self": tool_name == "play_get_my_profile",
                }
            )
        return cards

    if tool_name == "play_update_my_profile":
        prof = data.get("profile") or {}
        if isinstance(prof, dict):
            cards.append(
                {
                    "type": "play_profile",
                    "user_id": session.user_id,
                    "mongo_id": data.get("_id") or prof.get("_id"),
                    "name": prof.get("name") or data.get("name") or session.user_name or "Play Creator",
                    "username": prof.get("username") or data.get("username") or "",
                    "bio": prof.get("bio") or data.get("bio") or "",
                    "profile_picture": prof.get("profilePicture") or "",
                    "post_count": int(prof.get("postCount") or 0),
                    "followers_count": int(
                        prof.get("followersCount") or len(prof.get("followers") or []) or 0
                    ),
                    "following_count": int(
                        prof.get("followingCount") or len(prof.get("following") or []) or 0
                    ),
                    "is_self": True,
                }
            )
        return cards

    # 2. My reels / user posts
    if tool_name == "play_get_my_reels":
        reels = data.get("reels") or []
        for r in reels[:15]:
            c = _normalize_reel_card(r)
            if c:
                cards.append(c)
        return cards

    # 3. Search
    if tool_name == "play_search":
        users = data.get("users") or []
        for u in users[:4]:
            c = _normalize_user_card(u)
            if c:
                cards.append(c)
        videos = data.get("videos") or []
        for r in videos[:15]:
            c = _normalize_reel_card(r)
            if c:
                cards.append(c)
        return cards

    # 4. Feed
    if tool_name == "play_get_feed":
        reels = data.get("reels") or []
        for r in reels[:15]:
            c = _normalize_reel_card(r)
            if c:
                cards.append(c)
        return cards

    return cards
