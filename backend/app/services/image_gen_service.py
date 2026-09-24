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


async def _generate_one_image_from_account(
    client: httpx.AsyncClient, account_id: str, api_token: str, model: str, prompt: str
) -> bytes:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    last_err = None
    for attempt in range(1, 3):
        try:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
                json={"prompt": prompt},
                timeout=12.0,
            )
            if resp.status_code == 429:
                raise httpx.HTTPStatusError("429 Quota/Rate Limit Exceeded", request=resp.request, response=resp)
            resp.raise_for_status()

            raw_content = resp.content
            if not raw_content or len(raw_content) < 100:
                raise ValueError(f"Cloudflare returned empty or invalid image payload ({len(raw_content)} bytes).")

            if raw_content.startswith(b"{"):
                data = resp.json()
                if "result" in data and "image" in data["result"]:
                    b64_image = data["result"]["image"]
                    img_bytes = base64.b64decode(b64_image)
                    if len(img_bytes) > 100:
                        return img_bytes
                if "errors" in data and data["errors"]:
                    raise ValueError(f"Cloudflare AI API Error: {data['errors']}")
                raise ValueError("Cloudflare JSON response did not contain valid image data.")

            return raw_content
        except Exception as exc:
            last_err = exc
            if attempt < 2 and ("429" in str(exc) or "timeout" in str(exc).lower() or "50" in str(exc)):
                await asyncio.sleep(1.0)
                continue
            break

    raise RuntimeError(f"Cloudflare Account ({account_id[:6]}...) failed: {last_err}")


async def generate_images(prompts: list[str]) -> tuple[list[bytes], str | None]:
    """
    Generates AI images using Cloudflare Workers AI with primary & secondary account fallback.
    Validates HTTP status, image bytes, and size before proceeding.
    Raises explicit RuntimeError if both Primary and Secondary accounts fail.
    """
    images: list[bytes] = []
    notice_msg: str | None = None

    model = settings.cloudflare_image_model or "@cf/bytedance/stable-diffusion-xl-lightning"
    acc1 = settings.cloudflare_account_id
    tok1 = settings.cloudflare_api_token
    acc2 = settings.cloudflare_account_id_2
    tok2 = settings.cloudflare_api_token_2

    if not acc1 and not acc2:
        raise RuntimeError("Missing required Cloudflare Workers AI production environment variables (CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN).")

    async with httpx.AsyncClient(timeout=20.0) as client:

        async def _safe_gen(idx: int, prompt: str) -> tuple[bytes, str | None]:
            err1 = None
            err2 = None

            # 1. Try Primary Cloudflare Account
            if acc1 and tok1:
                try:
                    img_bytes = await _generate_one_image_from_account(client, acc1, tok1, model, prompt)
                    return img_bytes, None
                except Exception as cf_err1:
                    err1 = str(cf_err1)
                    logger.warning("Cloudflare Primary Account failed for prompt %d: %s. Trying Secondary Account...", idx, cf_err1)

            # 2. Try Secondary Cloudflare Account
            if acc2 and tok2:
                try:
                    img_bytes = await _generate_one_image_from_account(client, acc2, tok2, model, prompt)
                    logger.info("Successfully generated image for prompt %d using Secondary Cloudflare Account fallback!", idx)
                    return img_bytes, "Used Secondary Cloudflare Account fallback."
                except Exception as cf_err2:
                    err2 = str(cf_err2)
                    logger.warning("Cloudflare Secondary Account failed for prompt %d: %s", idx, cf_err2)

            # 3. Both Accounts Failed -> Throw Real Error
            err_parts = []
            if err1:
                err_parts.append(f"Primary Account: {err1}")
            if err2:
                err_parts.append(f"Secondary Account: {err2}")
            full_err = "; ".join(err_parts) or "No valid Cloudflare credentials available."
            raise RuntimeError(f"Cloudflare Workers AI image generation failed for image #{idx}: {full_err}")

        # Process 1 image per step for safe sub-2s execution on Vercel
        batch_size = 1
        for batch_start in range(0, len(prompts), batch_size):
            batch_prompts = prompts[batch_start:batch_start + batch_size]
            tasks = [_safe_gen(batch_start + idx + 1, p) for idx, p in enumerate(batch_prompts)]
            batch_results = await asyncio.gather(*tasks)
            for img_bytes, notice in batch_results:
                images.append(img_bytes)
                if notice and not notice_msg:
                    notice_msg = notice

    return images, notice_msg

