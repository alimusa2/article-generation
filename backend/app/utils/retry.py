from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

# Mirrors the n8n node settings: retryOnFail + continueErrorOutput.
# 3 attempts, exponential backoff — tuned for flaky free-tier endpoints.
external_call_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.TransportError)),
)
