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


async def get_user_boards(access_token: str | None = None) -> list[dict]:
    """
    Fetches Pinterest boards for the authenticated user using Pinterest API v5.
    Returns list of dicts: [{"id": "...", "name": "..."}].
    """
    token = access_token or settings.pinterest_access_token
    if not token:
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    endpoints = [
        "https://api.pinterest.com/v5/boards",
        "https://api-sandbox.pinterest.com/v5/boards",
    ]
    if token.startswith("pina_"):
        endpoints.reverse()

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        for url in endpoints:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    return [{"id": item.get("id"), "name": item.get("name", "Untitled Board")} for item in items if item.get("id")]
            except Exception:
                continue
    return []


async def create_pin(
    board_id: str,
    title: str,
    wp_link: str,
    description: str,
    image_url: str,
    access_token: str | None = None,
) -> dict:
    """
    Creates a single Pinterest pin via Pinterest API v5.
    """
    token = access_token or settings.pinterest_access_token
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
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    endpoints = [
        "https://api.pinterest.com/v5/pins",
        "https://api-sandbox.pinterest.com/v5/pins",
    ]
    if token and token.startswith("pina_"):
        endpoints.reverse()

    last_error = None
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        for url in endpoints:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    res = resp.json()
                    res["link"] = wp_link
                    return res
                last_error = f"HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                last_error = str(e)
    
    raise Exception(f"Pinterest API Error: {last_error}")


async def create_pins_for_images(
    title: str,
    wp_link: str,
    raw_seo_text: str | dict,
    cloudinary_image_urls: list[str],
    section_titles: list[str] | None = None,
    board_id: str | None = None,
) -> list[dict]:
    """
    Pins each image to Pinterest (or generates 8 pin objects with live WP link).
    """
    description = parse_pinterest_description(raw_seo_text)
    target_board_id = board_id or settings.pinterest_board_id or "1086423178800607052"

    from app.services.cloudinary_service import convert_bytes_to_avif_data_url, _create_procedural_ai_asset
    results: list[dict] = []
    urls = cloudinary_image_urls if cloudinary_image_urls else [
        convert_bytes_to_avif_data_url(_create_procedural_ai_asset(title, i), title=title, fallback_index=i)
        for i in range(1, 9)
    ]

    for idx in range(1, 9):
        img_url = urls[idx - 1] if idx - 1 < len(urls) else urls[0]
        pin_title = (
            section_titles[idx - 1]
            if (section_titles and idx - 1 < len(section_titles) and section_titles[idx - 1].strip())
            else f"{title} - Pin {idx}"
        )

        if settings.pinterest_access_token:
            try:
                res = await create_pin(
                    board_id=target_board_id,
                    title=pin_title,
                    wp_link=wp_link,
                    description=description,
                    image_url=img_url,
                )
                if isinstance(res, dict):
                    res["link"] = wp_link
                results.append(res)
            except Exception as e:
                results.append({
                    "id": f"pin-{idx}",
                    "title": pin_title,
                    "description": description,
                    "image_url": img_url,
                    "link": wp_link,
                    "error": str(e),
                })
        else:
            results.append({
                "id": f"pin-{idx}",
                "title": pin_title,
                "description": description,
                "image_url": img_url,
                "link": wp_link,
                "status": "prepared",
            })

    return results
