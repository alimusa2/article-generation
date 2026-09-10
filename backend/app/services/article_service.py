import re
import logging
import httpx
from app.config import settings
from app.utils.retry import external_call_retry
from app.services.seo_service import _call_openrouter

logger = logging.getLogger("article_service")

ARTICLE_SYSTEM_PROMPT = """You are an experienced home decor writer and interior stylist, with hands-on experience designing and renovating real bedrooms, living rooms, and other home spaces. You write to rank on Google — not just to sound pretty.

GOAL
Write an article that outranks generic competitor content by being more specific, more useful, and more trustworthy — not just better written.

STEP 1 — RESEARCH BEFORE WRITING (reflect this in the content, don't show it separately)
Before drafting, think through:
- What is the searcher actually trying to accomplish? (redecorating on a budget, matching a style, small space, renters, a specific room type)
- What related questions do people search? (e.g. "what colors go with X", "is X good for a bedroom", "does X make a room look smaller")
- What sub-topics would a real buyer or decorator guide expect? (color palettes, furniture, lighting, textures, small-space tips, mistakes to avoid, cost)
- Base every H2/H3 heading on this research. Never use vague, content-free headings like "Sunset-Inspired Palette" with nothing behind them — every heading must answer a real question or describe a specific, useful idea.

STEP 2 — STRUCTURE
- Word count: 800-900 words total (concise, high-density advice).
- Intro (80-120 words): hook the reader, state what they'll get from the article, briefly establish why this topic/color/style matters.
- Exactly 8 H2 sections, each built around one specific, researched idea — never a repeated template. Each section includes:
  - The specific idea/technique — name actual colors, materials, furniture types, or styles (never vague terms like "warm tones" alone).
  - Why it works — real design reasoning, not just description.
  - One practical, actionable tip — a cost-saving swap, a common mistake to avoid, a small-space/renter adaptation, or a pairing suggestion.
- One short FAQ section (3-4 Q&As) near the end, using real questions people search for on this topic.
- Short conclusion (60-100 words) summarizing the article with one clear next step or encouragement.

IMAGE PLACEMENTS
The article must contain exactly 8 image placeholders — one after each of the 8 H2 sections' full description (idea + reasoning + tip), before the next heading. Format each one exactly like this, on its own line:
[image space]
Do not place a placeholder in the intro, the FAQ, or the conclusion. Do not add more or fewer than 8 — this count is a hard requirement since 8 H2 sections is also a hard requirement.

STEP 3 — TONE & WORDING
- Simple, warm, conversational — explain like you're talking to a friend, not writing for a design magazine.
- Short sentences and paragraphs: 2-4 sentences max per paragraph.
- No fluffy openers like "Imagine stepping into a room that transports you..." — get to useful information quickly.
- No jargon without a plain-language explanation.

STEP 4 — E-E-A-T (this is critical — most competitor articles fail here)
- Experience: include 2-3 lines per section that sound first-hand and practical (e.g. "if your room doesn't get much natural light, go with a warmer coral-orange rather than a saturated neon shade — it won't look muddy at night").
- Expertise: name specific colors (e.g. "terracotta," "burnt sienna," "clay orange"), materials, or design principles (color theory, the 60-30-10 rule, proportion) where relevant.
- Authoritativeness: reference known design movements or eras by name where useful (mid-century modern, Mediterranean, boho) to show real design knowledge.
- Trustworthiness: give balanced advice — say when an idea won't work well (e.g. "avoid this in small, dark rooms" / "this works best with good natural light"). Never make unverifiable claims.

STEP 5 — FORMATTING OUTPUT
- Output clean HTML: h1 for the title, h2 for each section heading, h3 only if a section needs a genuine sub-point, p for paragraphs.
- Bold key terms sparingly for scannability (use <strong>, never bold inside headings).
- FAQ section: h2 "Frequently Asked Questions," then each question as h3 starting with "Q:" and the answer as a p starting with "A:".
- No markdown, no code fences, no text outside the HTML.

Before finishing, verify: word count is 1000-1200, there are exactly 8 H2 sections, exactly 8 [image space] placeholders exist (one per section, none elsewhere), headings are research-driven, and at least one first-hand-sounding line appears per section."""


def _generate_fallback_article(title: str) -> str:
    """Generates a high-quality, dynamic fallback HTML article based on the user's requested topic/title."""
    clean_title = title.strip()
    words = [
        w for w in clean_title.split()
        if len(w) > 2 and w.lower() not in ("the", "and", "for", "with", "your", "ideas", "best", "top", "how", "ways", "tips")
    ]
    topic = " ".join(words) if words else clean_title

    subtopics = [
        (
            f"1. Key Design Principles & Materials for {topic.title()}",
            f"Incorporating {topic.lower()} starts with selecting authentic materials, tactile textures, and balanced structural proportions. Focus on natural wood grains, warm metals, or durable upholstery to establish a solid design foundation."
        ),
        (
            f"2. Color Palette & Ambient Lighting Balance",
            f"Pair {topic.lower()} with complementary wall tones such as soft ivory, warm taupe, charcoal, or terracotta. Layer natural window light with warm downlights to accentuate depth and surface details."
        ),
        (
            f"3. Optimal Spatial Layout & Traffic Flow",
            f"Arrange furniture around your {topic.lower()} focal points while keeping walkways clear and navigable. Maintain comfortable sightlines and proportion ratios so the space feels cohesive and ergonomic."
        ),
        (
            f"4. Layering Textures, Fabrics & Finishes",
            f"Enhance the character of {topic.lower()} by layering contrasting materials—such as linen drapery, wool area rugs, matte black accents, and polished stone—for a rich, multi-dimensional look."
        ),
        (
            f"5. Smart Budget-Friendly Styling Swaps",
            f"Achieve a high-end interior look with {topic.lower()} on a reasonable budget. Swap expensive solid pieces for quality veneers, thrift vintage accent decor, or apply targeted DIY paint treatments."
        ),
        (
            f"6. Adapting {topic.title()} for Small Spaces & Apartments",
            f"For compact rooms, scale down {topic.lower()} elements and utilize vertical wall space. Light-reflecting surfaces, floating shelves, and low-profile furniture help maximize room volume."
        ),
        (
            f"7. Styling Mistakes & Over-Decorating Pitfalls to Avoid",
            f"Avoid crowding your {topic.lower()} setup with excessive small decorative knick-knacks. Stick to a restricted 3-color palette and allow key statement pieces space to breathe."
        ),
        (
            f"8. Final Organic Touches & Botanical Accents",
            f"Complete your {topic.lower()} styling with organic accents such as potted indoor plants, woven seagrass baskets, and curated coffee table books for an inviting, lived-in aesthetic."
        ),
    ]

    h2_blocks = []
    for heading, text in subtopics:
        h2_blocks.append(f"<h2>{heading}</h2>\n<p>{text}</p>\n[image space]")

    body_html = "\n\n".join(h2_blocks)

    return f"""<h1>{clean_title}</h1>
<p>Transforming your space with {clean_title.lower()} brings warmth, character, and functional beauty to any room. Explore practical styling advice, color pairings, and expert interior design ideas to elevate your home effortlessly.</p>

{body_html}

<h2>Frequently Asked Questions</h2>
<h3>Q: What is the best way to start styling {topic.lower()}?</h3>
<p>A: Begin with your primary focal piece, choose a cohesive 3-color palette, and layer secondary textures like rugs and ambient lighting around it.</p>
<h3>Q: Can {topic.lower()} suit modern and traditional spaces?</h3>
<p>A: Yes, natural materials and balanced proportions allow {topic.lower()} to transition seamlessly between contemporary minimalist and classic rustic interiors.</p>
<h3>Q: How do I keep {topic.lower()} looking uncluttered in smaller rooms?</h3>
<p>A: Stick to low-profile furniture, utilize vertical storage solutions, and keep decorative accessories curated rather than crowded.</p>

<h2>Conclusion</h2>
<p>Integrating {clean_title.lower()} adds timeless architectural interest and cozy elegance to your living space. Start by selecting your core materials and build a harmonious color palette for an elevated, professional result.</p>"""


async def generate_article(title: str) -> str:
    """Calls OpenRouter/Gemini LLM pipeline to generate raw HTML article, with fallback on error."""
    system_prompt = ARTICLE_SYSTEM_PROMPT
    user_prompt = (
        f"Write the complete article now, following all system rules exactly, "
        f"for this title/keyword:\n{title}\n\n"
        f"The article must have exactly {settings.h2_sections_per_article} H2 sections "
        f"and exactly {settings.images_per_article} [image space] placeholders. "
        f"Return only the final HTML article."
    )

    try:
        content = await _call_openrouter(system_prompt, user_prompt)
        if content:
            # Clean markdown code fences and extraneous pre-HTML text
            cleaned = re.sub(r"^```(?:html)?\s*", "", content.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            html_match = re.search(r"<(?:h1|h2)[\s\S]*", cleaned, re.IGNORECASE)
            if html_match:
                cleaned = html_match.group(0).strip()

            if "<h2" in cleaned and "[image space]" in cleaned:
                logger.info("Successfully generated article via LLM for title '%s'", title)
                return cleaned
            else:
                logger.warning("LLM response did not meet section formatting rules. Using structured fallback.")
                return _generate_fallback_article(title)
    except Exception as err:
        logger.warning("LLM call failed for generate_article: %s. Using structured fallback article.", err)

    return _generate_fallback_article(title)
