"""Welfog AI isolated image vision module.

Handles:
- Image validation and data URL sanitation
- Multimodal user message formatting for Gemini Vision
- Intent-aware visual guidance (Product Discovery vs Damaged/Defect vs Invoice vs Unrelated)
- Google Gemini content safety filter handling
"""

from __future__ import annotations

import re
from typing import Any

# Supported image types
SUPPORTED_IMAGE_MIMES = ("image/jpeg", "image/png", "image/webp", "image/gif", "image/jpg")
MAX_IMAGE_BASE64_LENGTH = 12 * 1024 * 1024  # 12MB raw base64 string cap


def validate_image_data(image_raw: Any) -> tuple[bool, str, str | None]:
    """
    Validates base64 data URI or public image URL.
    Returns: (is_valid, cleaned_image_str, error_message_or_None)
    """
    if not image_raw or not isinstance(image_raw, str):
        return False, "", "No image data provided"

    s = image_raw.strip()
    if len(s) > MAX_IMAGE_BASE64_LENGTH:
        return False, "", "Image size is too large (max 10MB)"

    # Handle standard Data URI
    if s.startswith("data:"):
        if not s.startswith("data:image/"):
            return False, "", "Unsupported image format. Please use JPG, PNG, or WEBP."
        header_end = s.find(",")
        if header_end == -1:
            return False, "", "Invalid image data format"
        mime_part = s[:header_end].lower()
        if not any(mime in mime_part for mime in SUPPORTED_IMAGE_MIMES):
            return False, "", "Unsupported image format. Please use JPG, PNG, or WEBP."
        return True, s, None

    # Handle public HTTPS image URL
    if re.match(r"^https?://[^\s/$.?#].[^\s]*$", s, re.IGNORECASE):
        return True, s, None

    # Plain base64 without prefix -> wrap as jpeg data URI
    if len(s) > 100 and not s.startswith("data:"):
        return True, f"data:image/jpeg;base64,{s}", None

    return False, "", "Invalid image format. Please upload a JPG, PNG, or WEBP photo."


def validate_images_data(images_raw: Any) -> tuple[bool, list[str], str | None]:
    """
    Validates a list of images (up to 3).
    Returns: (is_valid, list_of_cleaned_images, error_message_or_None)
    """
    if not images_raw:
        return False, [], "No images provided"

    if isinstance(images_raw, str):
        raw_list = [images_raw]
    elif isinstance(images_raw, (list, tuple)):
        raw_list = [img for img in images_raw if img]
    else:
        return False, [], "Invalid images payload format"

    if not raw_list:
        return False, [], "No images provided"

    cleaned_list: list[str] = []
    for item in raw_list[:3]:
        ok, cleaned, err = validate_image_data(item)
        if not ok:
            return False, [], err
        cleaned_list.append(cleaned)

    if not cleaned_list:
        return False, [], "No valid images provided"

    return True, cleaned_list, None


def extract_text_from_content(content: Any) -> str:
    """Safely extracts text string from either a plain string or a multimodal content list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(parts).strip()
    return ""


def format_multimodal_user_message(user_text: str, images: str | list[str]) -> dict:
    """Formats a user message containing image(s) and text for Gemini's OpenAI-compatible endpoint."""
    text = (user_text or "").strip()
    if not text:
        text = "Please examine these image(s) and assist me with them."

    if isinstance(images, str):
        img_list = [images]
    elif isinstance(images, (list, tuple)):
        img_list = list(images)
    else:
        img_list = []

    content: list[dict] = [{"type": "text", "text": text}]
    for img_url in img_list[:3]:
        content.append({
            "type": "image_url",
            "image_url": {"url": img_url},
        })

    return {
        "role": "user",
        "content": content,
    }


def get_image_system_prompt() -> str:
    """System prompt guidance specifically activated when an image is present in the turn."""
    return """

[Image / Visual Assistant Guidance]:
One or more images (up to 3) have been attached by the customer. Visually inspect the image(s) with high attention to detail:

1. CLASSIFY THE USER INTENT CAREFULLY:
   - PRODUCT DISCOVERY / SHOPPING:
     If the user uploads clothes, shoes, accessories, or shopping products they want to buy or see:
     Identify product type, style, color, pattern, brand/fabric.
     Call tool `search_products` with the clean product phrase in `name` (and color/brand if applicable).
     Describe what you see in the photo naturally, and show matching Welfog options using <<<CARDS>>>.

   - DEFECT / DAMAGED ITEM / RETURN COMPLAINT:
     If the image shows a damaged product, tear, broken part, stained fabric, or damaged package:
     DO NOT call `search_products`! Do NOT show product cards.
     Empathize warmly in polite Hindi/Hinglish (e.g. "Yeh dekh kar bohot khed hua ki aapko damaged product receive hua hai").
     Explain that you clearly see the defect/issue in the photo.
     Ask if this was received in a recent Welfog order and request their 10-digit mobile number or Order ID so we can assist with replacement or refund.

   - INVOICE / COURIER SLIP / BOX LABEL:
     If the image is an invoice paper, courier receipt, or box tag:
     Read the visible Order ID, tracking AWB, or item details directly from the image.
     If user is logged in, check order details or ask how you can help regarding that specific order.

   - UNRELATED / NOT E-COMMERCE (Pet, selfie, nature, meme, vehicle):
     DO NOT search products. Politely acknowledge what is in the photo in a friendly, respectful tone.
     Mention that you are Welfog's shopping assistant, and ask if they need help finding any fashion, shoes, or lifestyle items on Welfog.

2. SPECIFIC QUESTIONS:
   If the customer also asked a specific question in text (e.g. "Iska material kya hai?", "Ye shoes original hain?", "Isme blue color milega?"):
   Always answer their specific question first based on your visual inspection of the image!
"""


def is_safety_error(err_str: str) -> bool:
    """Checks if the LLM error is due to content safety / moderation filters."""
    s = (err_str or "").lower()
    return any(
        kw in s
        for kw in (
            "safety",
            "harm_category",
            "blocked",
            "inappropriate",
            "content moderation",
            "policy violation",
            "content_filter",
            "moderation",
        )
    )


def get_safety_error_reply() -> str:
    """User-friendly response when an image violates safety policies."""
    return (
        "Kripya dhyan dein: Hamari safety guidelines ke mutabiq yeh image process nahi ki ja sakti. "
        "Kripya sirf Welfog shopping ya order support se related photos hi share karein."
    )
