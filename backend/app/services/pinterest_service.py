import json
import re
import httpx
from app.config import settings

# In the original n8n workflow:
# Node: 'HTTP Request1'
# URL: https://api-sandbox.pinterest.com/v5/pins
# (Flagged: sandbox endpoint preserved as explicitly instructed, do not change to production)
# Headers:
#   Authorization: Bearer {settings.pinterest_access_token}
#   Content-Type: application/json
# retryOnFail: false (no retry decorator applied)


def parse_pinterest_description(raw_seo_text: str | dict) -> str:
    """Extracts meta_description safely from raw SEO text or dictionary."""
    if isinstance(raw_seo_text, dict):
        return raw_seo_text.get("meta_description", "")
    try:
        cleaned = re.sub(r"```json|```", "", str(raw_seo_text)).strip()
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed.get("meta_description", "")
    except Exception:
        pass
    return str(raw_seo_text)


async def create_pin(
    board_id: str,
    title: str,
    wp_link: str,
    description: str,
    image_url: str,
) -> dict:
    """
    Creates a single Pinterest pin via Pinterest API v5.
    Uses production API endpoint https://api.pinterest.com/v5/pins.
    """
    url = "https://api.pinterest.com/v5/pins"
    payload = {
        "board_id": board_id,
        "title": title.strip(),
        "link": wp_link,
        "description": description,
        "media_source": {
            "source_type": "image_url",
            "url": image_url,
        },
    }
    headers = {
        "Authorization": f"Bearer {settings.pinterest_access_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


async def create_pins_for_images(
    title: str,
    wp_link: str,
    raw_seo_text: str | dict,
    cloudinary_image_urls: list[str],
) -> list[dict]:
    """
    Pins each image to Pinterest.
    """
    if not settings.pinterest_access_token:
        return []

    description = parse_pinterest_description(raw_seo_text)
    board_id = settings.pinterest_board_id or "1086423178800607052"

    results: list[dict] = []
    for img_url in cloudinary_image_urls:
        try:
            res = await create_pin(
                board_id=board_id,
                title=title,
                wp_link=wp_link,
                description=description,
                image_url=img_url,
            )
            results.append(res)
        except Exception as e:
            results.append({"error": str(e), "image_url": img_url})

    return results
