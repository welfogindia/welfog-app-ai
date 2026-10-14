"""OpenAI agent loop with Welfog tool calling + admin knowledge/APIs."""

from __future__ import annotations

import json
import re
import uuid
from typing import Callable

import requests

from config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    MAX_AGENT_STEPS,
    ONE_SHOT_TOOLS,
    classify_query_demand,
    collect_gemini_keys,
    gemini_models_for_demand,
)
from dynamic_apis import build_dynamic_tools, execute_dynamic_api
from image import (
    format_multimodal_user_message,
    get_image_system_prompt,
    validate_image_data,
    validate_images_data,
)
from session import session
from tools import TOOLS, execute_tool

try:
    from db import get_setting
except Exception:

    def get_setting(key, default=""):
        return default


SYSTEM_PROMPT = """You are Welfog AI — the official intelligent assistant for Welfog (https://welfog.com), an Indian e-commerce marketplace.

Personality:
- Talk like a polite, professional Welfog shopping assistant. Warm and helpful, but always respectful — like a well-trained store advisor, not a street-style chat buddy.
- Use "aap" / polite Hindi-English (Hinglish). Never rude, never overly casual.
- Do NOT start replies with slang fillers: Arre, Arey, Are, Yaar, Bhai, Oye, Bro, Dude, Re, Abe, Suno yaar.
- Do NOT use teasing / flirty / overly chummy lines. No "arre wah", "kya baat hai yaar", "chill karo".
- Match the user's language (Hindi / English / Hinglish), still keep a respectful tone.
- Never invent product prices, stock, order status, or account data. Always use tools to fetch live data from APIs.
- Prefer company knowledge via search_company_knowledge (live Aidata) for brand/policy/support facts.
- Never invent policy/refund/shipping facts — call search_company_knowledge first.
- If asked about unrelated topics (other brands, politics, coding, etc.), politely redirect to Welfog help.
- Do NOT push contact/support unless the user clearly asks for support/contact/complaint. Shopping questions stay shopping.
- Greetings (hi/hye/hello/thanks) → short friendly reply ONLY. Never call search_products or any tool.

Shopping conversation (be realistic + talkative):
- YOU understand the user's meaning (language, typos, brand, product type, color, size, budget). There is NO backend keyword dictionary — form the search yourself.
- Browse → call search_products (OpenSearch products_v1). Pass `name` as the product phrase (e.g. "red t shirt"). When user named color/size/brand/category, ALSO pass those args. Ranking priority: PRODUCT TYPE first, then color/size as secondary boosts (so a red ball never beats a t-shirt ask).
- After search, UI shows unique feature_filters under cards from each product's pro_features (duplicates removed). Briefly mention user can tap a feature to filter — do NOT paste the whole feature list in text.
- If user picks / names a feature filter (e.g. "Material: Cotton" or "Filter t shirt by Pattern: Solid"), re-call search_products with the SAME product `name` plus feature_key + feature_value.
- Read tool `match_meta` / `note` after search. If color/size was requested but match_meta says 0 matches: say so honestly in the user's language (e.g. red nahi mili, yeh t-shirts other colors mein hain — try kar sakte ho). Still show the product-type results. Never invent a color/size that isn't in the cards. No static canned scripts — write a fresh natural line each time.
- If multiple items in one message → one search_products call per item in the same turn.
- Act (cart/wishlist/login) → do not re-search just to show cards; use known ids. Login/OTP flow stays normal — never mix product search into OTP turns. After remove/add cart: confirm in text only — do NOT call search_products or get_related_products, and do NOT output <<<CARDS>>>.
- Vague browse with no product type → ask what they want; don't search random SKUs.
- Category list / "all categories on Welfog" → answer with category names in text only. Do NOT call search_products. Do NOT show product cards (no <<<CARDS>>>). Ask which category they want next.
- Product reply when cards will show (MATCH user language — Hindi/English/Hinglish; write FRESH each time, never reuse a fixed phrase like "Here are some matching options"):
  1) ABOVE <<<CARDS>>>: a richer describe block (2–5 natural sentences). Say what you found, briefly describe the kinds of items/colors/sizes you see from the tool results, and how they relate to the ask. If color/size asked nahi mila but same product type hai, say that honestly. Do NOT dump prices, ids, or a catalog list in text.
  2) <<<CARDS>>> alone on its own line
  3) BELOW <<<CARDS>>>: 1–2 short natural questions — color/size/budget/style specify karna hai? Kuch aur try karein? Invent from THIS ask; no fixed CTA script.
- Zero / not_found (match_meta.mode=not_found or total=0): DO NOT output <<<CARDS>>> and DO NOT invent products. Write a longer helpful reply (3–6 sentences): clearly say the asked item nahi mila / stock mein nahi dikh raha, briefly suggest how they can refine (similar type, color, brand), and ask one clarifying question. No static template — fresh natural wording every time.
- If match_meta marks weak/partial facet matches but products are returned: describe as close options / suggestions (not exact match), still use cards, and say so clearly in the describe text.
- If user asked for MULTIPLE product types (tshirt + shoes), search each and say clearly what you found for each (and what missing).
- If wrong results, search again with a clearer query YOU choose (YOU form clean product phrases — never leave conversational filler as the only search terms).
- Product/order cards link to welfog.com — don't paste URLs in text.

Support / contact (ONLY headset button or user clearly wants to contact support/team):
- Ask for ALL details in ONE reply only: full name, email, phone, and query. Never ask them one-by-one across turns.
- Do NOT say "marketplace issue" unless the user did.
- When name + email + message are present, call submit_contact and confirm briefly.
- Never treat normal product/order questions as contact requests.
- NEVER call search_products / get_related_products / get_today_deals on support/contact turns.
- NEVER output <<<CARDS>>> or product suggestions while collecting/submitting support details.

Platform knowledge:
- Welfog is a shopping platform where customers browse products, add to cart, place orders, track delivery, and manage accounts.
- Website: welfog.com | Product search: OpenSearch products_v1 on s.welfog.com | Other APIs: welfogapi.welfog.com
- Admin may register MORE APIs (reels, etc.) — use those tools when relevant.

Authentication:
- Public APIs need no login.
- Private (orders, cart, wishlist, profile, addresses, notifications): user MUST be logged in via phone OTP.
- If not logged in and user asks for private data OR wants to update cart/profile/wishlist:
  1) Ask for 10-digit mobile number
  2) Call send_login_otp
  3) Ask for OTP
  4) Call verify_login_otp
  5) Continue with the SAME original request (cart → get_my_cart, orders → get_purchase_history, wishlist → get_my_wishlist, etc.). Never switch cart asks to orders.
- Never ask for password.
- Phone number CANNOT be updated via chat. Name, email, DOB, gender, marital_status can — use update_my_profile.
- Cart: add_to_cart / remove_from_cart / update_cart_quantity / get_my_cart / get_cart_summary / apply_coupon
- Wishlist: add_to_wishlist / remove_from_wishlist / get_my_wishlist
- Profile: get_my_profile then update_my_profile when user wants changes (except phone). Pass ONLY the fields the user asked to change — never invent/clear name or other fields.
- Addresses: get_my_addresses; select_address to set default. Creating new map addresses needs the website/app if mapAddress data is missing.

Tool use:
- Prefer tools over guessing. You may call multiple tools when needed.
- After product browse tools: natural describe intro + <<<CARDS>>> + one short clarifying question under cards (you invent it). For orders/wishlist/cart/profile/login: natural reply only (no product sandwich).
- Do NOT dump markdown field lists, numbered product catalogs, ### headings with prices, or image links.
- NEVER write product ids, stock ids, or id arrays like [2619217, 2619412] in the reply. Cards already show products — text is only natural language.
- NEVER list product names with ₹ prices in text — the UI shows a product slider with photos automatically, best matches first.
- NEVER output image URLs, markdown images like ![Image](...), or welfog.com/images links. Photos already show in UI product/order cards automatically.
- NEVER invent image prefixes. The UI uses https://image.welfog.com/ for images.
- Orders list → get_purchase_history
- Specific order → get_order_details
- Wishlist → get_my_wishlist
- Policy / FAQ / refund / about Welfog / bank limits / shipping rules / features (shorts, video, app how-to) → search_company_knowledge
- After search_company_knowledge: give a COMPLETE useful answer from the tool result (short paragraphs or a clear bullet list). Do NOT stop after only an intro line like "uses yeh hain:" — finish the explanation.
- Add to cart → use product_id + stock_id from earlier results/cards. Call add_to_cart. If needs_login, ask phone/OTP only — do not search or re-show product cards. If API fails (Stock out / not found), say that clearly.
- Remove from cart → get_my_cart first for cart_item_id, then remove_from_cart
- For cancel_order, confirm order id + reason first.
- Contact / support → ask name + email + phone + query in ONE message (never say "marketplace issue" unless user said that), then submit_contact when complete.
- For admin-registered dynamic APIs, call the matching tool by name when the user intent matches the tool description.
- After update_my_profile / cart changes, briefly confirm success; UI may show refreshed profile/cart.

Welfog Play (short videos / reels platform):
- Welfog Play is Welfog's short-video / reels platform (like Instagram Reels).
- Play profile view ("meri play profile", "show my play profile", "mera play profile kya hai") -> call tool play_get_my_profile (requires login).
- Play profile edit ("bio change kar do", "Play username change karo", "Play profile update karo") -> call tool play_update_my_profile with only requested fields (name, username, bio). If user says "profile edit karni hai" without specifying details, ask what they want to change (name, username, bio). Preserve existing fields; never overwrite with blank values. Requires login.
- Play uploaded reels ("meri reels dikhao", "my uploaded reels", "maine Play par kya upload kiya hai") -> call tool play_get_my_reels (requires login).
- Play search ("Play par bablu search karo", "search bablu on Play", "backend developer reels search karo") -> call tool play_search with the clean search phrase extracted from user's request.
- Play feed ("Play feed dikhao", "trending reels", "explore Play") -> call tool play_get_feed.
- For private Play actions (my profile, edit profile, my reels), user MUST be logged in via phone OTP. If not logged in, ask for 10-digit mobile number for OTP.
- Never invent follower counts, reel views, captions, or shortLinks. All factual data must come from Play tools.
- NEVER output raw .m3u8 URLs. The UI renders compact, clickable reel cards linking to API shortLinks.
Session:
- Current session may already be authenticated; use get_session_status if unsure.
"""


class WelfogAgent:
    def __init__(self):
        self.history: list[dict] = []
        self.pending_otp_phone = ""

    def reset(self):
        self.history = []
        self.pending_otp_phone = ""

    def _last_assistant_text(self) -> str:
        for msg in reversed(self.history[:-1]):
            if msg.get("role") == "assistant" and (msg.get("content") or "").strip():
                return str(msg.get("content") or "").lower()
        return ""

    def _phone_from_history(self) -> str:
        pending = re.sub(r"\D", "", str(getattr(self, "pending_otp_phone", "") or ""))
        if len(pending) == 10:
            return pending
        for msg in reversed(self.history):
            if msg.get("role") != "user":
                continue
            raw = str(msg.get("content") or "").strip()
            digits = re.sub(r"\D", "", raw)
            if len(digits) == 10 and re.sub(r"[\s\-]+", "", raw) == digits:
                return digits
        text = self._last_assistant_text()
        m = re.search(r"\b(\d{10})\b", text)
        return m.group(1) if m else ""

    def _resolved_otp_phone(self) -> str:
        phone = re.sub(r"\D", "", str(session.phone or ""))
        if len(phone) == 10:
            return phone
        return self._phone_from_history()

    def _awaiting_otp(self) -> bool:
        if session.otp_pending or getattr(self, "pending_otp_phone", ""):
            return True
        t = self._last_assistant_text()
        return any(
            p in t
            for p in (
                "otp yahan",
                "otp enter",
                "enter karein",
                "otp bhej diya",
                "otp aapke",
                "otp bhej di",
                "verify otp",
                "otp share",
                "otp dalein",
                "otp daalein",
            )
        )

    def _awaiting_phone(self) -> bool:
        if session.is_authenticated:
            return False
        if self._awaiting_otp() and (session.phone or self._phone_from_history()):
            return False
        t = self._last_assistant_text()
        # Already sent OTP — waiting for code, not another phone
        if any(
            p in t
            for p in (
                "otp bhej diya",
                "otp aapke",
                "bhej diya gaya",
                "otp yahan",
                "enter karein",
            )
        ):
            return False
        return any(
            p in t
            for p in (
                "mobile number",
                "10-digit",
                "10 digit",
                "phone number",
                "number share",
                "number batao",
                "number share karein",
                "login hona",
                "otp bhej deta",
                "otp bhej dunga",
                "otp bhej du",
                "mobile number share",
            )
        )

    def _append_tool_turn(self, tool_name: str, args: dict, result: object) -> None:
        tc_id = f"auth_{uuid.uuid4().hex[:10]}"
        self.history.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }
                ],
            }
        )
        self.history.append(
            {
                "role": "tool",
                "tool_call_id": tc_id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            }
        )

    def _pending_private_intent(self) -> str:
        """What the user wanted before phone/OTP — cart|orders|wishlist|profile|addresses|none."""
        for msg in reversed(self.history):
            if msg.get("role") != "user":
                continue
            raw = str(msg.get("content") or "").strip()
            if not raw:
                continue
            digits = re.sub(r"\D", "", raw)
            # Skip pure phone / OTP digit turns
            if digits and re.sub(r"[\s\-]+", "", raw) == digits and 4 <= len(digits) <= 12:
                continue
            t = raw.lower()
            if any(
                x in t
                for x in (
                    "cart list",
                    "my cart",
                    "mera cart",
                    "meri cart",
                    "cart dikhao",
                    "cart dikha",
                    "cart me",
                    "cart mein",
                    "basket",
                    "kart",
                    "cart",
                )
            ):
                return "cart"
            if any(
                x in t
                for x in (
                    "wishlist",
                    "wish list",
                    "wish-list",
                    "save for later",
                )
            ):
                return "wishlist"
            if any(
                x in t
                for x in (
                    "address",
                    "addresses",
                    "delivery location",
                    "shipping address",
                )
            ):
                return "addresses"
            if any(
                x in t
                for x in (
                    "play profile",
                    "mera play profile",
                    "meri play profile",
                    "play account",
                    "play bio",
                    "play username",
                )
            ):
                return "play_profile"
            if any(
                x in t
                for x in (
                    "meri reels",
                    "mere reels",
                    "meri reel",
                    "uploaded reels",
                    "play reels",
                    "play videos",
                    "my reels",
                    "my play reels",
                    "kya upload kiya",
                )
            ):
                return "play_reels"
            if any(
                x in t
                for x in (
                    "my profile",
                    "mera profile",
                    "meri profile",
                    "profile",
                    "my account",
                    "mera account",
                )
            ):
                return "profile"
            if any(
                x in t
                for x in (
                    "my order",
                    "mere order",
                    "meri order",
                    "order list",
                    "orders",
                    "order",
                    "purchase",
                    "tracking",
                    "track",
                )
            ):
                return "orders"
            # First real ask before OTP — don't assume orders
            return "none"
        return "none"

    def _resume_after_login(
        self,
        *,
        who: str,
        on_status: Callable[[str], None] | None = None,
        on_tool: Callable[[str, dict], None] | None = None,
    ) -> str:
        """Continue the original private request after OTP — never hardcode orders."""
        intent = self._pending_private_intent()
        print(f"[auth] resume_after_login intent={intent}")

        if intent == "cart":
            if on_status:
                on_status("Loading your cart…")
            args: dict = {}
            if on_tool:
                on_tool("get_my_cart", args)
            data = execute_tool("get_my_cart", args)
            self._append_tool_turn("get_my_cart", args, data)
            return (
                f"Login successful{who}! Yeh rahi aapki cart — "
                "quantity change ya remove karna ho to bata dena."
            )

        if intent == "wishlist":
            if on_status:
                on_status("Loading your wishlist…")
            args = {}
            if on_tool:
                on_tool("get_my_wishlist", args)
            data = execute_tool("get_my_wishlist", args)
            self._append_tool_turn("get_my_wishlist", args, data)
            return f"Login successful{who}! Yeh rahi aapki wishlist."

        if intent == "addresses":
            if on_status:
                on_status("Loading your addresses…")
            args = {}
            if on_tool:
                on_tool("get_my_addresses", args)
            data = execute_tool("get_my_addresses", args)
            self._append_tool_turn("get_my_addresses", args, data)
            return (
                f"Login successful{who}! Yeh rahe aapke saved addresses. "
                "Website pe manage karne ke liye: https://welfog.com/account/addresses"
            )

        if intent == "profile":
            if on_status:
                on_status("Loading your profile…")
            args = {}
            if on_tool:
                on_tool("get_my_profile", args)
            data = execute_tool("get_my_profile", args)
            self._append_tool_turn("get_my_profile", args, data)
            return f"Login successful{who}! Yeh raha aapka profile."

        if intent == "play_profile":
            if on_status:
                on_status("Loading your Play profile…")
            args = {}
            if on_tool:
                on_tool("play_get_my_profile", args)
            data = execute_tool("play_get_my_profile", args)
            self._append_tool_turn("play_get_my_profile", args, data)
            return f"Login successful{who}! Yeh rahi aapki Welfog Play profile."

        if intent == "play_reels":
            if on_status:
                on_status("Loading your Play reels…")
            args = {}
            if on_tool:
                on_tool("play_get_my_reels", args)
            data = execute_tool("play_get_my_reels", args)
            self._append_tool_turn("play_get_my_reels", args, data)
            return f"Login successful{who}! Yeh rahi aapki uploaded Play reels."

        if intent == "orders":
            if on_status:
                on_status("Loading your orders…")
            args = {"page": 1}
            if on_tool:
                on_tool("get_purchase_history", args)
            data = execute_tool("get_purchase_history", args)
            self._append_tool_turn("get_purchase_history", args, data)
            return (
                f"Login successful{who}! Yeh rahe aapke recent orders — "
                "kisi order ki detail chahiye to order id bata dena."
            )

        return (
            f"Login successful{who}! Ab batao kya chahiye — "
            "cart, orders, wishlist, profile, ya addresses?"
        )

    def _login_otp_fast_path(
        self,
        user_text: str,
        *,
        on_status: Callable[[str], None] | None = None,
        on_tool: Callable[[str, dict], None] | None = None,
    ) -> str | None:
        """Deterministic phone/OTP handling — don't let Gemini treat digits as products."""
        raw = (user_text or "").strip()
        digits = re.sub(r"\D", "", raw)
        # Only pure digit messages (maybe spaces/dashes)
        if not digits or re.sub(r"[\s\-]+", "", raw) != digits:
            return None

        # OTP (4–8 digits) while login in progress
        if 4 <= len(digits) <= 8 and (self._awaiting_otp() or session.otp_pending):
            phone = self._resolved_otp_phone()
            if len(phone) != 10:
                return (
                    "OTP verify ke liye pehle 10-digit mobile number bhejo — "
                    "main OTP dubara bhej dunga."
                )
            if on_status:
                on_status("Verifying OTP…")
            args = {"phone": phone, "otp": digits}
            if on_tool:
                on_tool("verify_login_otp", args)
            result = execute_tool("verify_login_otp", args)
            self._append_tool_turn("verify_login_otp", args, result)
            print(f"[auth] verify_login_otp phone={phone} ok={bool(isinstance(result, dict) and result.get('ok'))}")
            if isinstance(result, dict) and result.get("ok"):
                self.pending_otp_phone = ""
                name = (result.get("user") or {}).get("name") or session.user_name or ""
                who = f" {name}" if name else ""
                return self._resume_after_login(
                    who=who, on_status=on_status, on_tool=on_tool
                )
            api = (result or {}).get("api_response") if isinstance(result, dict) else None
            msg = ""
            if isinstance(api, dict):
                msg = str(api.get("message") or "")
            return (
                (msg.strip() or "OTP galat ya expire ho gaya.")
                + " Dubara sahi OTP bhejo, ya naya OTP ke liye mobile number dobara bhejo."
            )

        # Phone (10 digits) when assistant asked for login / number
        if len(digits) == 10 and (self._awaiting_phone() or session.otp_pending):
            if on_status:
                on_status("Sending OTP…")
            args = {"phone": digits}
            if on_tool:
                on_tool("send_login_otp", args)
            result = execute_tool("send_login_otp", args)
            self._append_tool_turn("send_login_otp", args, result)
            ok = bool(isinstance(result, dict) and result.get("ok"))
            print(f"[auth] send_login_otp phone={digits} ok={ok}")
            if ok:
                self.pending_otp_phone = digits
                session.phone = digits
                session.otp_pending = True
                return (
                    f"OTP aapke mobile number {digits} par bhej diya gaya hai. "
                    "Kripya woh OTP yahan enter karein taaki login complete ho sake."
                )
            api = (result or {}).get("api_response") if isinstance(result, dict) else None
            msg = str((api or {}).get("message") or "") if isinstance(api, dict) else ""
            return (
                msg.strip()
                or "OTP bhej nahi paaya. Number check karke dubara try karein."
            )

        return None

    def _contact_starter_reply(self, user_text: str) -> str | None:
        """If user is starting support contact, return one message asking all fields."""
        import re

        t = (user_text or "").strip().lower()
        if not t:
            return None
        # Already mid-contact (email-looking reply, etc.) → let normal agent handle submit
        if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", t):
            return None
        if len(t.split()) > 40:
            return None
        starters = (
            "contact support",
            "connect with your team",
            "connect with support",
            "contact karna",
            "support se baat",
            "support se contact",
            "query dalni",
            "submit_contact",
            "would like to contact support",
        )
        if not any(s in t for s in starters):
            # Headset canned prompt only — not generic "help" / product asks
            if "contact support" in t and "connect with your team" in t:
                pass
            else:
                return None
        # Don't re-prompt if we already asked for the contact pack recently
        for msg in reversed(self.history[:-1]):
            if msg.get("role") != "assistant":
                continue
            c = (msg.get("content") or "").lower()
            if "full name" in c and "email" in c and ("query" in c or "phone" in c):
                return None
            break
        return (
            "Sure — I can connect you with support. Please share all of this in one message:\n"
            "1) Full name\n"
            "2) Email\n"
            "3) Phone\n"
            "4) Your query / how we can help"
        )

    def _system_prompt(self, *, has_image: bool = False) -> str:
        # Live Aidata search tool supplies company facts per query — avoid dumping
        # the whole MySQL knowledge table into every turn (saves tokens).
        extra = get_setting("extra_system_prompt", "")
        parts = [SYSTEM_PROMPT]
        if extra:
            parts.append("\n\n[Admin extra instructions]\n" + extra)
        parts.append(
            "\n\n[Knowledge] For policies/FAQs/company facts call tool "
            "search_company_knowledge (live aidata.welfog.com). Use its instruction+context."
        )
        if has_image:
            parts.append(get_image_system_prompt())
        return "".join(parts)

    def _all_tools(self) -> list[dict]:
        dyn = []
        try:
            dyn = build_dynamic_tools()
        except Exception:
            dyn = []
        builtin_names = {(t.get("function") or {}).get("name") for t in TOOLS}
        dyn = [t for t in dyn if (t.get("function") or {}).get("name") not in builtin_names]
        return TOOLS + dyn

    def _chat_completions(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict],
        tools: list[dict],
        provider: str,
        demand: str = "low",
    ) -> dict:
        import time

        # Low = short chat; high = fuller FAQ / tool answers (avoid mid-sentence cuts)
        max_tokens = 500 if demand == "low" else 1600
        temperature = 0.4 if demand == "low" else 0.6
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        t0 = time.perf_counter()
        # Tools + big schemas are slow on Gemini; don't wait 90s on casual chat
        timeout = 55 if tools else 35
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if not resp.ok:
            try:
                err = resp.json()
                msg = (
                    (err.get("error") or {}).get("message")
                    if isinstance(err.get("error"), dict)
                    else err.get("error") or err.get("message") or resp.text
                )
            except Exception:
                msg = resp.text
            raise RuntimeError(f"{provider} error ({resp.status_code}): {msg}")
        data = resp.json()
        fr = ""
        try:
            fr = (data.get("choices") or [{}])[0].get("finish_reason") or ""
        except Exception:
            pass
        print(f"[llm] demand={demand} via {provider} {ms}ms finish={fr} tools={bool(tools)}")
        return data

    def _provider_chain(
        self, demand: str = "low"
    ) -> list[tuple[str, str, str, str]]:
        """Gemini only — models ordered by query demand (token save)."""
        keys = collect_gemini_keys()
        if not keys and GEMINI_API_KEY:
            keys = [GEMINI_API_KEY]
        models = gemini_models_for_demand(demand)
        out: list[tuple[str, str, str, str]] = []
        for model in models:
            for i, key in enumerate(keys):
                label = f"Gemini/{model}/k{i + 1}/{demand}"
                out.append((label, GEMINI_BASE_URL, key, model))
        return out

    def _openai_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        provider: str = "gemini",
        demand: str = "low",
    ) -> dict:
        """Gemini-only; picks lite vs full model from demand."""
        errors: list[str] = []
        providers = self._provider_chain(demand)

        last_err: Exception | None = None
        for label, base_url, api_key, model in providers:
            if not api_key:
                errors.append(f"{label} skipped (no API key)")
                continue
            try:
                data = self._chat_completions(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    tools=tools,
                    provider=label,
                    demand=demand,
                )
                return data
            except Exception as err:
                last_err = err
                errors.append(f"{label} failed ({err})")

        detail = "; ".join(errors) if errors else "No Gemini API key configured (GEMINI_API_KEY)"
        raise RuntimeError(detail) from last_err

    def chat(
        self,
        user_text: str,
        *,
        images: list[str] | None = None,
        image: str | None = None,
        provider: str = "gemini",
        on_status: Callable[[str], None] | None = None,
        on_tool: Callable[[str, dict], None] | None = None,
    ) -> str:
        has_image = False
        raw_images = images if images is not None else ([image] if image else [])
        if raw_images:
            is_val, clean_images, err = validate_images_data(raw_images)
            if not is_val:
                err_reply = err or "Invalid image provided. Please try with a JPG, PNG, or WEBP image."
                self.history.append({"role": "user", "content": user_text or "Uploaded image"})
                self.history.append({"role": "assistant", "content": err_reply})
                return err_reply
            has_image = True
            self.history.append(format_multimodal_user_message(user_text, clean_images))
        else:
            self.history.append({"role": "user", "content": user_text})

        if not has_image:
            # Contact start → always ask ALL fields in one fixed reply (model kept asking one-by-one)
            contact_reply = self._contact_starter_reply(user_text)
            if contact_reply:
                self.history.append({"role": "assistant", "content": contact_reply})
                return contact_reply

            # Phone / OTP while login in progress → call Welfog auth APIs directly
            auth_reply = self._login_otp_fast_path(
                user_text, on_status=on_status, on_tool=on_tool
            )
            if auth_reply:
                self.history.append({"role": "assistant", "content": auth_reply})
                return auth_reply

        final_text = ""
        tools = self._all_tools()
        builtin_names = {(t.get("function") or {}).get("name") for t in TOOLS}
        demand = "high" if has_image else classify_query_demand(user_text, history_len=len(self.history))
        force_answer = False  # after one-shot tools, skip another tool round
        escalate = False  # only for truncation / knowledge answers

        for step in range(MAX_AGENT_STEPS):
            if on_status:
                if step == 0:
                    on_status("Analyzing image & request…" if has_image else "Analyzing your request…")
                else:
                    on_status("Thinking…")

            # Keep same fast tier for shopping; escalate only when needed
            step_demand = "high" if (has_image or escalate or demand == "high") else "low"
            step_tools = [] if force_answer else tools
            session_hint = (
                f"\n\n[Live session] authenticated={session.is_authenticated}, "
                f"user_id={session.user_id}, name={session.user_name}, phone={session.phone}, "
                f"otp_pending={session.otp_pending}"
                f"\n[Model tier] {step_demand}"
            )
            messages = [
                {"role": "system", "content": self._system_prompt(has_image=has_image) + session_hint},
                *self.history,
            ]

            data = self._openai_chat(
                messages, step_tools, provider="gemini", demand=step_demand
            )
            choice = data["choices"][0]
            message = choice["message"]
            # Keep Gemini tool_calls.extra_content.thought_signature intact
            self.history.append(json.loads(json.dumps(message)))

            content = message.get("content") or ""
            if content:
                final_text = content

            tool_calls = message.get("tool_calls") or []
            # When we asked for a final answer (no tools), ignore phantom tool_calls
            if not step_tools:
                tool_calls = []
            finish_reason = (choice.get("finish_reason") or "").lower()

            # Hit token cap mid-answer — one retry with high budget
            if (
                not tool_calls
                and finish_reason in ("length", "max_tokens")
                and not escalate
                and step < MAX_AGENT_STEPS - 1
            ):
                print(f"[llm] truncated finish_reason={finish_reason}; retrying with high max_tokens")
                escalate = True
                force_answer = True
                if self.history and self.history[-1].get("role") == "assistant":
                    self.history.pop()
                if on_status:
                    on_status("Refining answer…")
                continue

            if not tool_calls:
                if finish_reason in ("length", "max_tokens"):
                    print(f"[llm] reply still truncated finish_reason={finish_reason}")
                if on_status:
                    on_status("Preparing reply…")
                break

            called: set[str] = set()
            for tc in tool_calls:
                fn = tc["function"]["name"]
                called.add(fn)
                raw_args = tc["function"].get("arguments") or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}

                if on_tool:
                    on_tool(fn, args)
                elif on_status:
                    on_status(f"Working on {fn.replace('_', ' ')}…")

                if fn in builtin_names:
                    result = execute_tool(fn, args)
                else:
                    result = execute_dynamic_api(fn, args)

                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

            if on_status:
                on_status("Analyzing results…")

            # Knowledge answers need fuller model; browse tools → answer next (no 3rd LLM)
            if "search_company_knowledge" in called:
                escalate = True
            if called and called <= ONE_SHOT_TOOLS:
                force_answer = True

        return final_text or ""
