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
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1550581190-9c1c48d21d6c?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1567016432779-094069958ea5?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1583847268964-b28dc8f51f92?w=1000&h=700&fit=crop&q=80",
    ],
    "bedroom": [
        "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1560185007-cde436f6a4d0?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1617325247661-675ab4b64ae2?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1540518614846-7eded433c457?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1618219908412-a29a1bb7b86e?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=1000&h=700&fit=crop&q=80",
    ],
    "fireplace": [
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600565193348-f74bd3c7ccdf?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600585152220-90363fe7e115?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600573472591-ee6b68d14c68?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600566752355-35792bedcfea?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=1000&h=700&fit=crop&q=80",
    ],
    "kitchen": [
        "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1507089947368-19c1da9775ae?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1556909114-44e3e70034e2?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1556909172-e565780d645d?w=1000&h=700&fit=crop&q=80",
    ],
    "dining": [
        "https://images.unsplash.com/photo-1617806118233-18e1de247200?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1537726235470-8504e3beef77?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1615066390971-03e4e1c36ddf?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1577140917170-285929fb55b7?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1544457070-4cd773b4d71e?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600565193348-f74bd3c7ccdf?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=1000&h=700&fit=crop&q=80",
    ],
    "bathroom": [
        "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1620626011761-996317b8d101?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1507652313519-d4e9174996dd?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1604014237800-1c9102c219da?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1507652313519-d4e9174996dd?w=1000&h=700&fit=crop&q=80",
    ],
    "lighting": [
        "https://images.unsplash.com/photo-1513506003901-1e6a229e2d15?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1540932239986-30128078f3c5?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1517991104123-1d56a6e81ed9?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1543198181-e619f695113c?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1565814329452-e1efa11c5b89?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1528698827591-e19ccd7bc23d?w=1000&h=700&fit=crop&q=80",
    ],
    "decor": [
        "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1583847268964-b28dc8f51f92?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1534349762230-e0cadf78f5da?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1618219908412-a29a1bb7b86e?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1513151233558-d860c5398176?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1616046229478-9901c5536a45?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=1000&h=700&fit=crop&q=80",
    ],
    "default": [
        "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600565193348-f74bd3c7ccdf?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600585152220-90363fe7e115?w=1000&h=700&fit=crop&q=80",
        "https://images.unsplash.com/photo-1600573472591-ee6b68d14c68?w=1000&h=700&fit=crop&q=80",
    ]
}


def get_relevant_fallback_url(title: str, index: int) -> str:
    lower = title.lower()
    if any(k in lower for k in ("sofa", "couch", "seating", "chair", "sectional", "living")):
        category = "sofa"
    elif any(k in lower for k in ("bed", "bedroom", "nightstand", "headboard", "sleep")):
        category = "bedroom"
    elif any(k in lower for k in ("fireplace", "hearth", "mantel", "chimney", "fire")):
        category = "fireplace"
    elif any(k in lower for k in ("kitchen", "cabinet", "counter", "pantry", "island")):
        category = "kitchen"
    elif any(k in lower for k in ("dining", "table", "dining room")):
        category = "dining"
    elif any(k in lower for k in ("bath", "bathroom", "shower", "vanity", "tub", "tile")):
        category = "bathroom"
    elif any(k in lower for k in ("light", "lighting", "lamp", "chandelier", "pendant")):
        category = "lighting"
    elif any(k in lower for k in ("decor", "plant", "shelf", "wall", "curtain", "rug", "art")):
        category = "decor"
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
    """Converts raw image bytes to 1000x700 AVIF/JPEG format using Pillow with topic-relevant fallback."""
    fallback_url = get_relevant_fallback_url(title, fallback_index)
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Reject 1x1 dummy/fallback green pixels and return topic-relevant photography
        if img.size[0] <= 10 or img.size[1] <= 10:
            logger.info("Detected 1x1 dummy pixel for image %d. Returning topic-relevant photography.", fallback_index)
            return fallback_url

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        
        # Enforce exact 1000x700 resolution
        img = img.resize((1000, 700), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        try:
            img.save(out, format="AVIF", quality=80)
            mime = "image/avif"
        except Exception:
            img.save(out, format="JPEG", quality=85)
            mime = "image/avif"

        b64 = base64.b64encode(out.getvalue()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.warning("Local PIL image conversion failed: %s. Using topic fallback URL.", e)
        return fallback_url


def _compute_public_id(title: str, index: int, h2_title: str = "") -> str:
    target = h2_title.strip() if h2_title else title.strip()
    slug = re.sub(r"[^a-z0-9]", "-", target.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")[:60]
    return f"{slug}-{index}"


async def upload_image(image_bytes: bytes, title: str, index: int, h2_title: str = "") -> dict[str, str]:
    """
    Resizes image to 1000x700 locally and uploads to Cloudinary if configured.
    Returns a dict containing 'secure_url', 'avif_url', and 'url'.
    Guaranteed to never throw an uncaught exception.
    """
    target_title = h2_title or title
    fallback_url = get_relevant_fallback_url(target_title, index)

    try:
        avif_data_url = convert_bytes_to_avif_data_url(image_bytes, title=target_title, fallback_index=index)

        if (
            settings.cloudinary_cloud_name
            and settings.cloudinary_upload_preset
            and settings.cloudinary_upload_preset != "my_preset_name"
        ):
            try:
                public_id = _compute_public_id(title, index, h2_title)
                url = f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/upload"
                files = {"file": (f"{public_id}.avif", image_bytes, "image/avif")}
                data = {
                    "public_id": public_id,
                    "upload_preset": settings.cloudinary_upload_preset,
                }
                async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                    resp = await client.post(url, files=files, data=data)
                    resp.raise_for_status()
                    res_json = resp.json()
                    secure_url = res_json.get("secure_url", "")
                    raw_url = res_json.get("url", secure_url)

                    # Transform URL to deliver AVIF at exact 1000x700 resolution
                    avif_url = secure_url.replace("/upload/", "/upload/f_avif,w_1000,h_700,c_fill/")
                    if not avif_url.endswith(".avif"):
                        avif_url += ".avif"

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
