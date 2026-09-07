import httpx
from app.config import settings
from app.models.schemas import SeoMetadata
from app.utils.parsing import extract_json_object

SEO_SYSTEM_PROMPT = """# SEO Metadata Generator

You are an SEO metadata specialist. Your task is to analyze the provided article and generate accurate, search-optimized metadata based ONLY on the information contained in the article.

The article itself contains the title and topic information. Identify the main topic and primary search keyword naturally from the article. Do not invent a keyword unrelated to the article.

## SEO TITLE

* 50-60 characters.
* Include the main keyword naturally, preferably near the beginning.
* Make it compelling and relevant to the article's search intent.
* Do not simply copy the article title if it does not meet the requirements.
* Use Title Case.
* Avoid keyword stuffing.

## META DESCRIPTION

* 150-160 characters.
* Include the main keyword naturally within the first 110 characters when possible.
* Clearly explain the value of the article.
* Make it compelling and action-oriented.
* Must accurately reflect the article.
* Do not copy or closely reproduce the article's opening paragraph.
* Never use generic filler.

## URL SLUG

* Maximum 75 characters.
* Lowercase only.
* Words separated with hyphens.
* No special characters.
* Include the main keyword when practical.
* Remove unnecessary stop words while keeping the slug readable.

## FOCUS KEYPHRASE

* 1-2 words only.
* Lowercase.
* Select the primary search phrase that best represents the article's main topic.
* Base it on the article content.

## SECONDARY KEYWORDS

* Return 3-5 related keywords or search phrases.
* Lowercase only.
* No duplicates.
* No trailing punctuation.
* Use terms genuinely related to the article.

## IMPORTANT OUTPUT RULES

Return ONLY one valid JSON object.

Use exactly these five keys and no others:

{
"seo_title": "",
"meta_description": "",
"url_slug": "",
"focus_keyphrase": "",
"secondary_keywords": []
}

Do not use Markdown.
Do not use code fences.
Do not add explanations.
Do not add text before or after the JSON.

The article may be long. Analyze it and generate only the metadata. Do not reproduce the article.

If some information is unclear, make the best reasonable decision based on the article instead of refusing to respond.

Always return a JSON object. Never return an empty response.

Before returning, ensure:

* seo_title is between 50 and 60 characters
* meta_description is between 150 and 160 characters
* url_slug is under 75 characters
* focus_keyphrase contains 1-2 words
* secondary_keywords contains 3-5 items"""


# In n8n JSON, 'retryOnFail' is false on the 'generate seo meta data' node.
# Preserving asymmetry: no retry decorator applied here.
async def _call_openrouter(system_prompt: str, user_prompt: str) -> str:
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": settings.openrouter_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def generate_seo_metadata(article_html: str) -> tuple[SeoMetadata, str]:
    user_prompt = (
        "# Article SEO Metadata Request\n\n"
        "Generate SEO metadata for the following article.\n\n"
        "ARTICLE CONTENT:\n\n"
        f"{article_html}\n\n"
        "Analyze the complete article to identify its title, main topic, primary keyword, search intent, and related keywords.\n\n"
        "Return only the JSON object specified in the system instructions.\n"
    )
    raw = await _call_openrouter(SEO_SYSTEM_PROMPT, user_prompt)
    parsed = extract_json_object(raw)
    seo = SeoMetadata(
        seo_title=parsed.get("seo_title") or parsed.get("title", ""),
        meta_description=parsed.get("meta_description") or parsed.get("description", ""),
        url_slug=parsed.get("url_slug", ""),
        focus_keyphrase=parsed.get("focus_keyphrase", ""),
        secondary_keywords=parsed.get("secondary_keywords") or [],
    )
    return seo, raw
