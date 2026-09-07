import base64
import io
import logging
import re
import httpx
from PIL import Image
import pillow_heif
from app.config import settings

logger = logging.getLogger("cloudinary_service")

# Register pillow-heif for local AVIF encoding
try:
    pillow_heif.register_heif_opener()
except Exception as e:
    logger.warning("Could not register pillow_heif opener: %s", e)


def convert_bytes_to_avif_data_url(image_bytes: bytes) -> str:
    """Converts raw image bytes to AVIF format using Pillow + pillow_heif and returns a Base64 Data URL."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="AVIF", quality=80)
    avif_bytes = out.getvalue()
    b64 = base64.b64encode(avif_bytes).decode("utf-8")
    return f"data:image/avif;base64,{b64}"


def _compute_public_id(title: str, index: int) -> str:
    # Exact replica of JS: title.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + (index)
    slug = re.sub(r"[^a-z0-9]", "-", title.lower())
    return f"{slug}-{index}"


async def upload_image(image_bytes: bytes, title: str, index: int) -> dict[str, str]:
    """
    Converts image to AVIF locally and optionally uploads to Cloudinary if configured.
    Returns a dict containing 'secure_url', 'avif_url', and 'url'.
    """
    avif_data_url = convert_bytes_to_avif_data_url(image_bytes)

    if (
        settings.cloudinary_cloud_name
        and settings.cloudinary_upload_preset
        and settings.cloudinary_upload_preset != "my_preset_name"
    ):
        try:
            url = f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/upload"
            files = {"file": (f"blog-image-{index}.png", image_bytes, "image/png")}
            data = {
                "public_id": _compute_public_id(title, index),
                "upload_preset": settings.cloudinary_upload_preset,
            }
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                resp = await client.post(url, files=files, data=data)
                resp.raise_for_status()
                res_json = resp.json()
                secure_url = res_json.get("secure_url", "")
                raw_url = res_json.get("url", secure_url)

            clean_url = re.sub(r"\.(jpg|jpeg|png)$", ".avif", secure_url, flags=re.IGNORECASE)
            avif_url = clean_url.replace("/upload/", "/upload/f_avif/")

            return {
                "secure_url": secure_url,
                "avif_url": avif_url,
                "url": raw_url,
            }
        except Exception as e:
            logger.warning("Cloudinary upload failed or not configured, using local AVIF conversion: %s", e)

    return {
        "secure_url": avif_data_url,
        "avif_url": avif_data_url,
        "url": avif_data_url,
    }

