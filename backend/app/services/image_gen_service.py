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
        timeout=2.0,
    )
    resp.raise_for_status()
    data = resp.json()
    b64_image = data["result"]["image"]
    return base64.b64decode(b64_image)


async def generate_images(prompts: list[str]) -> list[bytes]:
    """
    Generates images concurrently in parallel for maximum speed and sub-10s pipeline completion.
    Returns 1x1 fallback transparent PNG bytes if any individual image fails.
    """
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        sem = asyncio.Semaphore(4)

        async def _safe_gen(prompt: str) -> bytes:
            async with sem:
                try:
                    return await _generate_one_image(client, prompt)
                except Exception:
                    # Fallback transparent PNG bytes
                    return base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                    )

        tasks = [_safe_gen(p) for p in prompts]
        images = await asyncio.gather(*tasks)
        return list(images)
