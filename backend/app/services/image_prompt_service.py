import re
import logging
import httpx
from app.config import settings
from app.services.seo_service import _call_openrouter
from app.utils.parsing import extract_prompt_list

logger = logging.getLogger("image_prompt_service")

IMAGE_PROMPT_SYSTEM_PROMPT = """You are an expert interior design photographer and prompt engineer for luxury home decor magazines like Architectural Digest and Elle Decor.

YOUR MISSION:
Read the provided 8 H2 article sections. For each H2 section in order (1 through 8), create ONE hyper-specific, realistic editorial photography prompt.

STRICT RELEVANCE & QUALITY RULES:
1. 100% RELEVANCE TO H2: Every image prompt MUST directly and accurately feature the exact primary subject, specific furniture piece, material, color, or lighting mentioned in that specific H2 heading. (e.g. If H2 1 is about "Terracotta Wall Accents", prompt 1 MUST be a luxury shot of a terracotta-accented wall; if H2 2 is about "Velvet Tufted Headboards", prompt 2 MUST feature a velvet tufted headboard — never generic plants, empty shelves, or random items).
2. PREMIUM EDITORIAL PHOTOGRAPHY STYLE: Every prompt must specify: "Professional high-end interior architecture photograph, Architectural Digest style, soft natural window light, 35mm lens, 8k hyper-realistic detail, luxury styling".
3. SPECIFIC DECOR ELEMENTS: Describe exact textures, materials (linen, white oak, brushed brass, travertine, velvet), colors, and composition.
4. NO TEXT / LOGOS / PEOPLE: Do not include on-screen text, brand logos, signs, or human faces.

OUTPUT FORMAT:
Return ONLY a valid JSON array of exactly 8 strings, one per H2 section in order (1 to 8).
"""


def _extract_h2_sections(article_html: str) -> list[str]:
    """Extracts H2 section titles and text snippets to ensure 1:1 section relevance."""
    matches = re.findall(
        r"<h2[^>]*>(.*?)</h2>\s*(.*?)(?=<h2|$)", article_html, re.DOTALL | re.IGNORECASE
    )
    section_texts = []
    for idx, (h2, content) in enumerate(matches, start=1):
        clean_title = re.sub(r"<[^>]+>", "", h2).strip()
        clean_content = re.sub(r"<[^>]+>", " ", content).strip()
        clean_content = re.sub(r"\s+", " ", clean_content)[:250]
        if clean_title:
            section_texts.append(f"Section {idx} H2: {clean_title}\nContext: {clean_content}")

    return section_texts


async def _call_groq(system_prompt: str, user_prompt: str) -> str:
    """Calls Groq API using settings.groq_api_key and settings.groq_model."""
    if settings.groq_api_key:
        model = settings.groq_model or "openai/gpt-oss-20b"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.5,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if content:
                    logger.info("Successfully generated image prompts using Groq model '%s'", model)
                    return content
        except Exception as err:
            logger.warning("Groq API call error: %s. Falling back to OpenRouter/Gemini...", err)

    return await _call_openrouter(system_prompt, user_prompt)


def _generate_fallback_image_prompts(title: str, article_html: str) -> list[str]:
    sections = _extract_h2_sections(article_html)
    prompts = []
    base_style = "Professional high-end interior architecture photograph, Architectural Digest style, soft natural window light, 35mm lens, 8k hyper-realistic detail, luxury styling"
    for idx in range(settings.images_per_article):
        if idx < len(sections):
            sec_title = sections[idx].split("\n")[0].replace(f"Section {idx+1} H2: ", "").strip()
            prompts.append(f"{sec_title}, {base_style}, featuring elegant hearth details and warm ambient decor.")
        else:
            prompts.append(f"{title} - Scene {idx+1}, {base_style}, showcasing luxury rustic home interior aesthetic.")
    return prompts


async def generate_image_prompts(title: str, article_html: str) -> list[str]:
    sections = _extract_h2_sections(article_html)
    sections_formatted = "\n\n".join(sections) if sections else article_html

    user_prompt = (
        f"Generate exactly {settings.images_per_article} image prompts for this blog article.\n"
        f"ARTICLE TITLE: {title}\n\n"
        f"THE 8 H2 SECTIONS:\n{sections_formatted}\n\n"
        f"Remember: Output ONLY a JSON array of 8 strings, matching each section in 1:1 order."
    )
    try:
        raw = await _call_groq(IMAGE_PROMPT_SYSTEM_PROMPT, user_prompt)
        prompts = extract_prompt_list(raw, expected_count=settings.images_per_article)
        if len(prompts) == settings.images_per_article:
            return prompts
    except Exception as err:
        logger.warning("generate_image_prompts LLM failed: %s. Using structured fallback prompts.", err)

    return _generate_fallback_image_prompts(title, article_html)

