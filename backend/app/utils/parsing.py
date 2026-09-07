"""
LLMs don't always return clean JSON, even when told to. The original n8n
workflow handled this with a chain of fallbacks (strip code fences -> try
JSON.parse -> regex-extract quoted strings -> split by line -> ultimate fallback).
Port that same defensiveness here rather than assuming json.loads() will just work.
"""
import json
import re


def strip_code_fences(raw: str) -> str:
    return re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).replace("```", "").strip()


def extract_json_object(raw: str) -> dict:
    """
    Used for SEO metadata. Multi-step fallback chain:
    1. Strip code fences and try json.loads directly
    2. Regex match for outermost { ... } and json.loads
    3. Regex extraction of individual keys ("seo_title", "meta_description", etc.)
    4. Line-split extraction for key: value patterns
    5. Ultimate fallback: return empty/default metadata dict
    """
    if isinstance(raw, dict):
        return raw

    cleaned = strip_code_fences(str(raw))

    # Step 1: Direct JSON parsing
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Step 2: Regex extraction for {...}
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Step 3: Regex extraction of individual fields
    def _extract_field(pattern: str, text: str) -> str:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        return m.group(1).strip() if m else ""

    seo_title = _extract_field(r'"(?:seo_)?title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', cleaned)
    meta_desc = _extract_field(r'"(?:meta_)?description"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', cleaned)
    url_slug = _extract_field(r'"url_slug"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', cleaned)
    focus_kw = _extract_field(r'"focus_keyphrase"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', cleaned)

    sec_keywords: list[str] = []
    sec_match = re.search(r'"secondary_keywords"\s*:\s*\[([\s\S]*?)\]', cleaned, flags=re.IGNORECASE)
    if sec_match:
        sec_keywords = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', sec_match.group(1))

    if seo_title or meta_desc or url_slug or focus_kw or sec_keywords:
        return {
            "seo_title": seo_title,
            "meta_description": meta_desc,
            "url_slug": url_slug,
            "focus_keyphrase": focus_kw,
            "secondary_keywords": sec_keywords,
        }

    # Step 4: Line-split fallback (e.g. Key: Value plain text)
    fields = {}
    for line in cleaned.splitlines():
        line = line.strip()
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.lower().replace("-", "_").replace(" ", "_").strip('*_ "')
            v = v.strip('*_ "')
            if "title" in k and "seo_title" not in fields:
                fields["seo_title"] = v
            elif "description" in k and "meta_description" not in fields:
                fields["meta_description"] = v
            elif "slug" in k and "url_slug" not in fields:
                fields["url_slug"] = v
            elif "keyphrase" in k or "keyword" in k and "focus_keyphrase" not in fields:
                fields["focus_keyphrase"] = v

    if fields:
        return {
            "seo_title": fields.get("seo_title", ""),
            "meta_description": fields.get("meta_description", ""),
            "url_slug": fields.get("url_slug", ""),
            "focus_keyphrase": fields.get("focus_keyphrase", ""),
            "secondary_keywords": [],
        }

    # Step 5: Ultimate fallback
    return {
        "seo_title": "",
        "meta_description": "",
        "url_slug": "",
        "focus_keyphrase": "",
        "secondary_keywords": [],
    }


def extract_prompt_list(raw: str | list, expected_count: int = 8) -> list[str]:
    """
    Used for the 8 image prompts. Matches n8n 'Split Image Prompts' node verbatim:
    1. If already array of strings/objects, extract strings
    2. Strip code fences
    3. Try JSON parsing first (clean.match(/\\[[\\s\\S]*\\]/))
    4. Regex fallback: find text enclosed in double quotes: "([^"\\]*(?:\\.[^"\\]*)*)"
    5. Line-by-line fallback: split by line, strip list numbers/bullets, filter non-empty and non-{/[
    6. Ultimate fallback: if raw is non-empty string, return [raw.strip()], else ['Default image prompt']
    """
    # If already array
    if isinstance(raw, list):
        prompts = [p.get("prompt", str(p)) if isinstance(p, dict) else str(p) for p in raw]
        return prompts if prompts else ["Default image prompt"]

    raw_str = json.dumps(raw) if isinstance(raw, dict) else str(raw or "")
    prompts: list[str] = []

    # 1. Clean markdown code fences
    clean = strip_code_fences(raw_str)

    # 2. Try JSON Parsing first
    match = re.search(r"\[[\s\S]*\]", clean)
    try:
        parsed = json.loads(match.group(0) if match else clean)
        if isinstance(parsed, list):
            prompts = [str(p.get("prompt", p) if isinstance(p, dict) else p) for p in parsed]
    except Exception:
        # 3. Regex fallback: Find text enclosed in double quotes
        string_matches = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', clean)
        if string_matches:
            prompts = [m for m in string_matches if len(m.strip()) > 0]

    # 4. Line-by-line fallback: Split text lines (handles numbered/bulleted lists & plain text)
    if not prompts:
        lines = []
        for p in clean.split("\n"):
            stripped = re.sub(r"^[\d+.\-*\s]+", "", p).strip()
            if stripped and not stripped.startswith("{") and not stripped.startswith("["):
                lines.append(stripped)
        if lines:
            prompts = lines

    # 5. Ultimate Fallback: If everything else fails, use the whole text as 1 prompt
    if not prompts:
        if raw_str.strip():
            prompts = [raw_str.strip()]
        else:
            prompts = ["Default image prompt"]

    return prompts
