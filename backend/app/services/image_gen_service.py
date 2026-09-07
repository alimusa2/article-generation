import asyncio
import base64
import httpx
from app.config import settings

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
    )
    resp.raise_for_status()
    data = resp.json()
    b64_image = data["result"]["image"]
    return base64.b64decode(b64_image)


async def generate_images(prompts: list[str]) -> list[bytes]:
    """
    Generates images sequentially (batch size 1) with an exact 2000ms interval
    between calls, preserving the n8n batching configuration:
    batchSize: 1, batchInterval: 2000.
    """
    images: list[bytes] = []
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        for idx, prompt in enumerate(prompts):
            img_bytes = await _generate_one_image(client, prompt)
            images.append(img_bytes)
            # 2000ms delay between calls (unless last image)
            if idx < len(prompts) - 1:
                await asyncio.sleep(2.0)

    return images
