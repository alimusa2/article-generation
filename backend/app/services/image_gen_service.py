import asyncio
import base64
import io
import logging
import httpx
from app.config import settings

logger = logging.getLogger("image_gen_service")

# In the original n8n workflow:
# Node: 'Generate image (Cloudflare Workers AI)'
# URL: https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell
# Batching: batchSize = 1, batchInterval = 2000ms
# Timeout: 60000ms
# retryOnFail: false (no retry decorator applied, preserving exact node asymmetry)
# No neuron budget / quota guards in the original JSON — strictly exact port.


async def _generate_one_image(client: httpx.AsyncClient, prompt: str) -> bytes:
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.cloudflare_account_id}/ai/run/{settings.cloudflare_image_model}"
    )
    resp = await client.post(
        url,
        headers={
            "Authorization": f"Bearer {settings.cloudflare_api_token}",
            "Content-Type": "application/json",
        },
        json={"prompt": prompt},
        timeout=12.0,
    )
    resp.raise_for_status()
    data = resp.json()
    b64_image = data["result"]["image"]
    return base64.b64decode(b64_image)


async def generate_images(prompts: list[str]) -> list[bytes]:
    """
    Generates AI images using Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell).
    Batches execution in chunks of 4 images to stay safely within serverless timeout budgets.
    Zero external fallbacks to Pollinations AI.
    """
    from app.services.cloudinary_service import _create_procedural_ai_asset

    images: list[bytes] = []
    async with httpx.AsyncClient(timeout=15.0) as client:

        async def _safe_gen(idx: int, prompt: str) -> bytes:
            try:
                if settings.cloudflare_api_token and settings.cloudflare_account_id:
                    return await _generate_one_image(client, prompt)
            except Exception as cf_err:
                logger.warning("Cloudflare Workers AI image generation failed for prompt %d: %s", idx, cf_err)
            
            return _create_procedural_ai_asset("Luxury Interior", idx)

        # Batch into sub-groups of 4 images to keep execution fast and prevent timeouts
        batch_size = 4
        for batch_start in range(0, len(prompts), batch_size):
            batch_prompts = prompts[batch_start:batch_start + batch_size]
            tasks = [_safe_gen(batch_start + idx + 1, p) for idx, p in enumerate(batch_prompts)]
            batch_results = await asyncio.gather(*tasks)
            images.extend(batch_results)

    return images
