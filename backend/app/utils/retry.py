import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

def is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # Retry rate limits and temporary 5xx server errors
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False

# Bounded retry decorator with exponential backoff for transient API failures
external_call_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception(is_transient_error),
)

