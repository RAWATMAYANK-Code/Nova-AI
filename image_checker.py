"""
image_checker.py
Uses Gemini/LLM vision capability to read text/claims from an uploaded image.
Supports automatic key failover & vision model fallbacks if quota/rate limits occur.
"""

import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

MAX_IMAGE_URL_BYTES = 15 * 1024 * 1024  # 15 MB
VISION_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.0-flash"]


from security_utils import is_safe_url, validate_image_bytes

def extract_text_from_image(image_bytes, mime_type="image/jpeg"):
    """
    Sends the image to Gemini vision and extracts the headline text.
    Tries active Gemini models and key failovers if quota/rate limit occurs.
    """
    # Magic bytes check for uploaded image
    is_valid, detected_type_or_msg = validate_image_bytes(image_bytes)
    if not is_valid:
        print(f"[image_checker] Image validation rejected payload: {detected_type_or_msg}")
        return ""
    mime_type = detected_type_or_msg if detected_type_or_msg.startswith("image/") else mime_type

    load_dotenv(override=True)
    gemini_raw = os.getenv("GEMINI_API_KEY", "")
    gemini_keys = [k.strip() for k in gemini_raw.split(",") if k.strip()]

    if not gemini_keys:
        print("[image_checker] No GEMINI_API_KEY set in .env")
        return ""

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "This image contains a news headline, article, or claim (it may be a "
        "screenshot, forwarded message, or social media post). Extract ONLY the "
        "core factual claim or headline text from the image, in plain text. "
        "Do not add commentary. If there is no readable text, respond with NO_TEXT_FOUND."
    )

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": image_b64}}
            ]
        }]
    }

    for key_idx, key in enumerate(gemini_keys):
        for model in VISION_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                response = requests.post(url, params={"key": key}, json=payload, timeout=25)
                if response.status_code == 429:
                    print(f"[image_checker] Key {key_idx + 1} ({model}) 429 rate limited, trying next option...")
                    continue

                if not response.ok:
                    continue

                data = response.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    continue

                parts = candidates[0].get("content", {}).get("parts") or []
                if not parts:
                    continue

                text = parts[0].get("text", "").strip()
                if "NO_TEXT_FOUND" in text:
                    return ""
                return text

            except Exception as e:
                print(f"[image_checker] Error on key {key_idx + 1} ({model}): {e}")
                continue

    print("[image_checker] All Gemini keys/models exhausted for image extraction.")
    return ""


def extract_text_from_image_url(image_url):
    # 1. SSRF Security Check
    is_safe, msg = is_safe_url(image_url)
    if not is_safe:
        print(f"[image_checker] SSRF Guard blocked image URL: {msg}")
        return ""

    try:
        with requests.get(image_url, stream=True, timeout=15) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type and not content_type.startswith("image/"):
                print(f"[image_checker] URL did not point to an image (Content-Type: {content_type})")
                return ""

            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=65536):
                total += len(chunk)
                if total > MAX_IMAGE_URL_BYTES:
                    print("[image_checker] Image URL exceeded size limit, aborting download")
                    return ""
                chunks.append(chunk)
            image_bytes = b"".join(chunks)

        mime_type = content_type or "image/jpeg"
        return extract_text_from_image(image_bytes, mime_type)

    except requests.exceptions.RequestException as e:
        print(f"[image_checker] Error fetching image URL: {e}")
        return ""


if __name__ == "__main__":
    with open("test_image.jpg", "rb") as f:
        img_bytes = f.read()
    print(extract_text_from_image(img_bytes))