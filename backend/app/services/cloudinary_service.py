import base64
import io
import logging
import re
import httpx
from PIL import Image
from app.config import settings

logger = logging.getLogger("cloudinary_service")

TOPIC_IMAGE_MAP = {
    "sofa": [
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=1000&q=80",
        "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=1000&q=80",
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=1000&q=80",
        "https://images.unsplash.com/photo-1550581190-9c1c48d21d6c?w=1000&q=80",
        "https://images.unsplash.com/photo-1567016432779-094069958ea5?w=1000&q=80",
        "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=1000&q=80",
        "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=1000&q=80",
        "https://images.unsplash.com/photo-1583847268964-b28dc8f51f92?w=1000&q=80",
    ],
    "bedroom": [
        "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=1000&q=80",
        "https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?w=1000&q=80",
        "https://images.unsplash.com/photo-1560185007-cde436f6a4d0?w=1000&q=80",
        "https://images.unsplash.com/photo-1617325247661-675ab4b64ae2?w=1000&q=80",
        "https://images.unsplash.com/photo-1540518614846-7eded433c457?w=1000&q=80",
        "https://images.unsplash.com/photo-1618219908412-a29a1bb7b86e?w=1000&q=80",
        "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=1000&q=80",
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=1000&q=80",
    ],
    "fireplace": [
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1000&q=80",
        "https://images.unsplash.com/photo-1600565193348-f74bd3c7ccdf?w=1000&q=80",
        "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1000&q=80",
        "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?w=1000&q=80",
        "https://images.unsplash.com/photo-1600585152220-90363fe7e115?w=1000&q=80",
        "https://images.unsplash.com/photo-1600573472591-ee6b68d14c68?w=1000&q=80",
        "https://images.unsplash.com/photo-1600566752355-35792bedcfea?w=1000&q=80",
        "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=1000&q=80",
    ],
    "kitchen": [
        "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=1000&q=80",
        "https://images.unsplash.com/photo-1507089947368-19c1da9775ae?w=1000&q=80",
        "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=1000&q=80",
        "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=1000&q=80",
    ],
    "default": [
        "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=1000&q=80",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1000&q=80",
        "https://images.unsplash.com/photo-1600565193348-f74bd3c7ccdf?w=1000&q=80",
        "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1000&q=80",
        "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?w=1000&q=80",
        "https://images.unsplash.com/photo-1600585152220-90363fe7e115?w=1000&q=80",
        "https://images.unsplash.com/photo-1600573472591-ee6b68d14c68?w=1000&q=80",
        "https://images.unsplash.com/photo-1600566752355-35792bedcfea?w=1000&q=80",
    ]
}


def get_relevant_fallback_url(title: str, index: int) -> str:
    lower = title.lower()
    if any(k in lower for k in ("sofa", "couch", "seating", "chair", "sectional", "blue")):
        category = "sofa"
    elif any(k in lower for k in ("bed", "bedroom", "nightstand", "headboard")):
        category = "bedroom"
    elif any(k in lower for k in ("fireplace", "hearth", "mantel")):
        category = "fireplace"
    elif any(k in lower for k in ("kitchen", "cabinet", "island", "countertop")):
        category = "kitchen"
    else:
        category = "default"

    urls = TOPIC_IMAGE_MAP.get(category, TOPIC_IMAGE_MAP["default"])
    return urls[(index - 1) % len(urls)]


try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception as e:
    pillow_heif = None


def convert_bytes_to_avif_data_url(image_bytes: bytes, title: str = "", fallback_index: int = 1) -> str:
    """Converts raw image bytes to AVIF or WebP format using Pillow with topic-relevant fallback."""
    fallback_url = get_relevant_fallback_url(title, fallback_index)
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Reject 1x1 dummy/fallback green pixels and return curated photography for the specific topic
        if img.size[0] <= 10 or img.size[1] <= 10:
            logger.info("Detected 1x1 dummy pixel for image %d. Returning topic-relevant photography.", fallback_index)
            return fallback_url

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        out = io.BytesIO()
        mime = "image/avif"
        try:
            img.save(out, format="AVIF", quality=80)
        except Exception:
            img.save(out, format="WEBP", quality=85)
            mime = "image/webp"
        avif_bytes = out.getvalue()
        b64 = base64.b64encode(avif_bytes).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.warning("Local PIL image conversion failed: %s. Using topic fallback URL.", e)
        return fallback_url


def _compute_public_id(title: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]", "-", title.lower())
    return f"{slug}-{index}"


async def upload_image(image_bytes: bytes, title: str, index: int) -> dict[str, str]:
    """
    Converts image to AVIF locally and optionally uploads to Cloudinary if configured.
    Returns a dict containing 'secure_url', 'avif_url', and 'url'.
    Guaranteed to never throw an uncaught exception.
    """
    fallback_url = get_relevant_fallback_url(title, index)

    try:
        avif_data_url = convert_bytes_to_avif_data_url(image_bytes, title=title, fallback_index=index)

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
                logger.warning("Cloudinary upload failed or not configured, using local conversion: %s", e)

        return {
            "secure_url": avif_data_url,
            "avif_url": avif_data_url,
            "url": avif_data_url,
        }
    except Exception as e:
        logger.warning("upload_image encountered unhandled error: %s. Returning fallback asset.", e)
        return {
            "secure_url": fallback_url,
            "avif_url": fallback_url,
            "url": fallback_url,
        }
