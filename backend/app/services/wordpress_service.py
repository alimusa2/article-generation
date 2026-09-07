import base64
import re
import httpx
from app.config import settings
from app.models.schemas import SeoMetadata


def _auth_header() -> dict:
    # WordPress Application Passwords use HTTP Basic auth.
    token = base64.b64encode(
        f"{settings.wordpress_username}:{settings.wordpress_app_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {token}"}


# In the original n8n workflow:
# Node: 'media node1'
# URL: https://www.furnish-luxe.com/wp-json/wp/v2/media
# Headers:
#   Content-Disposition: attachment; filename=image.avif
#   Content-Type: image/avif
# retryOnFail: false (no retry decorator applied)
async def upload_media_from_url(avif_url: str) -> dict:
    """
    Downloads or decodes the AVIF image and re-uploads it to WP media.
    Returns the media item dict including 'id' and 'url'.
    """
    if avif_url.startswith("data:"):
        _, encoded = avif_url.split(",", 1)
        img_content = base64.b64decode(encoded)
    else:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            img_resp = await client.get(avif_url)
            img_resp.raise_for_status()
            img_content = img_resp.content

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        upload_resp = await client.post(
            f"{settings.wordpress_base_url}/wp-json/wp/v2/media",
            headers={
                **_auth_header(),
                "Content-Disposition": "attachment; filename=image.avif",
                "Content-Type": "image/avif",
            },
            content=img_content,
        )
        upload_resp.raise_for_status()
        data = upload_resp.json()
        media_id = data.get("id", 0)
        # guid.rendered || source_url || url (matching n8n Code in JavaScript2)
        media_url = (
            (data.get("guid", {}) or {}).get("rendered")
            or data.get("source_url")
            or data.get("url")
            or ""
        )
        return {"id": media_id, "url": media_url, "raw": data}


def replace_image_placeholders(article_html: str, media_urls: list[str]) -> str:
    """
    Replaces [image space] or [image...] placeholders with responsive figures,
    matching n8n 'Code in JavaScript2' step 4 byte-for-byte.
    """
    formatted_content = article_html
    if media_urls and formatted_content:
        image_index = [0]  # mutable counter for closure

        def _sub(_match):
            if image_index[0] < len(media_urls):
                url = media_urls[image_index[0]]
                image_index[0] += 1
                return (
                    f'<figure class="wp-block-image">'
                    f'<img src="{url}" alt="Article Image {image_index[0]}" '
                    f'style="max-width:100%;height:auto;display:block;margin:0 auto;" />'
                    f'</figure>'
                )
            return ""

        formatted_content = re.sub(
            r"\[image\s*space\]|\[image[^\]]*\]",
            _sub,
            formatted_content,
            flags=re.IGNORECASE,
        )

    # Catch-all: If HTML <img> tags already exist in the text without inline width constraints, enforce responsive styling
    if formatted_content:
        formatted_content = re.sub(
            r"<img (?!.*?style=)",
            '<img style="max-width:100%;height:auto;display:block;margin:0 auto;" ',
            formatted_content,
            flags=re.IGNORECASE,
        )

    return formatted_content


# In the original n8n workflow:
# Node: 'upload node'
# URL: https://www.furnish-luxe.com/wp-json/wp/v2/posts
# retryOnFail: false (no retry decorator applied)
async def create_post(
    title: str,
    content_html: str,
    featured_media_id: int,
    seo: SeoMetadata,
) -> dict:
    """
    Creates a WordPress draft post.
    NOTE / FLAGGED BUG:
    1. The n8n JSON sets 'featured_image_id': $json.featured_media. Standard WordPress REST API
       expects 'featured_media'. We preserve 'featured_image_id' as written in the original JSON.
    2. The n8n JSON sets 'title': $('On form submission').item.json.Title, using the original form
       title rather than the generated SEO title. We preserve this exact behavior.
    """
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        payload = {
            # In n8n JSON: 'title': $('On form submission').item.json.Title
            "title": title,
            # In n8n JSON: 'content': $json.content
            "content": content_html,
            # In n8n JSON: 'status': 'draft'
            "status": "draft",
            # FLAGGED BUG: Standard WP REST API uses 'featured_media', but n8n JSON explicitly specifies 'featured_image_id'
            "featured_image_id": featured_media_id,
            # In n8n JSON: 'meta': { _yoast_wpseo_metadesc: metaDesc, _rank_math_description: metaDesc }
            "meta": {
                "_yoast_wpseo_metadesc": seo.meta_description,
                "_rank_math_description": seo.meta_description,
            },
        }

        resp = await client.post(
            f"{settings.wordpress_base_url}/wp-json/wp/v2/posts",
            headers={
                **_auth_header(),
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def publish_post(post_id: int) -> dict:
    """
    Updates an existing WordPress post status from 'draft' to 'publish'.
    """
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        resp = await client.post(
            f"{settings.wordpress_base_url}/wp-json/wp/v2/posts/{post_id}",
            headers={
                **_auth_header(),
                "Content-Type": "application/json",
            },
            json={"status": "publish"},
        )
        resp.raise_for_status()
        return resp.json()

