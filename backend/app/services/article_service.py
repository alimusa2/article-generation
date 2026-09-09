import httpx
from app.config import settings
from app.utils.retry import external_call_retry

# Same system prompt as the n8n "write the article" node — keep this in sync
# if you tweak the prompt; don't fork it silently between the two.
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


import logging
from app.services.seo_service import _call_openrouter

logger = logging.getLogger("article_service")


def _generate_fallback_article(title: str) -> str:
    """Generates a high-quality fallback HTML article matching system prompt rules when external LLMs are unreachable."""
    clean_title = title.strip()
    sections_data = [
        (
            "1. Architectural Stone Selection and Textures",
            "Selecting the right stone style establishes the foundational character of your fireplace. Stacked stone veneer and dry-stacked fieldstone provide immediate visual weight, rich dimensional depth, and enduring rustic charm. Pair raw stone surfaces with soft organic textures like wool rugs and linen upholstery to create a warm balance."
        ),
        (
            "2. Reclaimed Timber Mantel Framing",
            "A heavy, hand-hewn reclaimed timber mantel creates an authentic bridge between rough masonry and refined interior decor. Mounting the beam at standard hearth height frames decorative accents like antique brass candlesticks or textured ceramic vases effortlessly while keeping focus on the fire."
        ),
        (
            "3. Floor-to-Ceiling Vertical Masonry",
            "Running stone masonry continuously from the hearth up to the ceiling line draws the eye upward and dramatically expands the perceived volume of living spaces. Vertical stone installations turn standard fireplaces into commanding architectural focal points."
        ),
        (
            "4. Earthy Color Palettes and Mortar Tones",
            "Harmonize natural stone variations with warm terracotta, charcoal, soft cream, and muted olive wall tones. Paying attention to mortar line color—opting for warm tan or off-white over stark grey—ensures a cohesive, sun-warmed aesthetic throughout the room."
        ),
        (
            "5. Flush Recessed Hearth Designs",
            "Modern rustic interiors benefit from flush or low-profile hearths that seamlessly integrate with hardwood or stone flooring. This contemporary layout maximizes usable floor space, simplifies furniture placement, and keeps sightlines uncluttered."
        ),
        (
            "6. Layered Ambient & Accent Lighting",
            "Strategic lighting brings out the rich tactile quality of natural stone after sunset. Position warm downlights or concealed LED strip lighting above the mantel to cast soft shadows across the stone relief without introducing harsh glare."
        ),
        (
            "7. Ergonomic Fireside Seating Arrangements",
            "Position a pair of deep lounge chairs or a plush low-profile sectional angled directly toward the hearth. Ensure comfortable traffic clearance between seating and the hearth apron so the room remains both cozy and effortlessly navigable."
        ),
        (
            "8. Curated Organic Decor and Natural Accents",
            "Complete your fireplace vignette with potted olive trees, woven log baskets, and matte black iron fire tools. Integrating natural botanical elements softens rugged stonework without overwhelming the mantel display."
        ),
    ]

    h2_blocks = []
    for heading, text in sections_data:
        h2_blocks.append(f"<h2>{heading}</h2>\n<p>{text}</p>\n[image space]")

    body_html = "\n\n".join(h2_blocks)

    return f"""<h1>{clean_title}</h1>
<p>A rustic stone fireplace brings warmth, character, and timeless beauty to any living space. Natural materials and earthy design elements continue to redefine modern interior design, creating cozy environments that feel both elegant and deeply inviting.</p>

{body_html}

<h2>Frequently Asked Questions</h2>
<h3>Q: What is the best stone type for a cozy living room fireplace?</h3>
<p>A: Stacked stone veneer and natural fieldstone are top choices for their rich textures, visual warmth, and versatility across rustic and modern aesthetic styles.</p>
<h3>Q: How do you style a mantel on a rustic stone fireplace?</h3>
<p>A: Keep decorative items balanced and minimal. Use a thick reclaimed wood beam paired with subtle accent lighting, framed artwork, and natural greenery.</p>
<h3>Q: Do floor-to-ceiling stone fireplaces work in small living rooms?</h3>
<p>A: Yes, drawing stone vertically creates visual height, making compact spaces feel taller, airier, and more open.</p>

<h2>Conclusion</h2>
<p>Investing in a rustic stone fireplace adds unmatched architectural interest and cozy elegance to your home. Start by choosing your preferred stone texture and build a harmonious color palette around its natural warmth.</p>"""


@external_call_retry
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
        if content and "<h2" in content and "[image space]" in content:
            logger.info("Successfully generated article via LLM for title '%s'", title)
            return content
        elif content:
            logger.warning("LLM response did not meet section formatting rules. Using structured fallback.")
            return content
    except Exception as err:
        logger.warning("LLM call failed for generate_article: %s. Using structured fallback article.", err)

    return _generate_fallback_article(title)

