import pytest
from app.utils.parsing import extract_json_object, extract_prompt_list
from app.services.wordpress_service import replace_image_placeholders


def test_extract_prompt_list_clean_json():
    clean_json = '["Prompt 1", "Prompt 2", "Prompt 3", "Prompt 4", "Prompt 5", "Prompt 6", "Prompt 7", "Prompt 8"]'
    result = extract_prompt_list(clean_json)
    assert len(result) == 8
    assert result[0] == "Prompt 1"


def test_extract_prompt_list_markdown_fenced():
    fenced = '```json\n["Prompt A", "Prompt B"]\n```'
    result = extract_prompt_list(fenced)
    assert len(result) == 2
    assert result[0] == "Prompt A"


def test_extract_prompt_list_regex_fallback():
    # LLM forgot outer brackets
    broken = '"Cozy fireplace in rustic living room", "Modern electric fireplace with marble hearth"'
    result = extract_prompt_list(broken)
    assert len(result) == 2
    assert "rustic" in result[0]
    assert "marble" in result[1]


def test_extract_prompt_list_line_by_line_fallback():
    bulleted = "1. Modern minimalist fireplace\n2. Scandinavian wood stove\n3. Traditional stone mantel"
    result = extract_prompt_list(bulleted)
    assert len(result) == 3
    assert result[0] == "Modern minimalist fireplace"
    assert result[1] == "Scandinavian wood stove"
    assert result[2] == "Traditional stone mantel"


def test_extract_prompt_list_ultimate_fallback():
    plain = "Just a single block of raw descriptive text for an image"
    result = extract_prompt_list(plain)
    assert len(result) == 1
    assert result[0] == plain

    empty = ""
    result = extract_prompt_list(empty)
    assert len(result) == 1
    assert result[0] == "Default image prompt"


def test_extract_seo_metadata_clean_json():
    json_str = '''{
        "seo_title": "Top 10 Modern Fireplace Ideas for 2026",
        "meta_description": "Transform your living space with these cozy and modern fireplace design ideas. Expert tips, styling inspiration, and buyer guides.",
        "url_slug": "modern-fireplace-ideas-2026",
        "focus_keyphrase": "fireplace ideas",
        "secondary_keywords": ["modern fireplace", "living room decor", "fireplace design"]
    }'''
    result = extract_json_object(json_str)
    assert result["seo_title"] == "Top 10 Modern Fireplace Ideas for 2026"
    assert result["url_slug"] == "modern-fireplace-ideas-2026"
    assert len(result["secondary_keywords"]) == 3


def test_extract_seo_metadata_fenced_and_embedded():
    embedded = '''Here is the requested SEO metadata:
    ```json
    {
        "seo_title": "Best Electric Fireplaces for Small Spaces",
        "meta_description": "Discover the most efficient, stylish electric fireplaces tailored for cozy apartments and small living rooms. Read our complete guide.",
        "url_slug": "best-electric-fireplaces",
        "focus_keyphrase": "electric fireplaces",
        "secondary_keywords": ["small space heating", "apartment decor"]
    }
    ```
    Hope this helps!'''
    result = extract_json_object(embedded)
    assert result["seo_title"] == "Best Electric Fireplaces for Small Spaces"
    assert result["focus_keyphrase"] == "electric fireplaces"


def test_extract_seo_metadata_line_fallback():
    lines = """
    seo_title: Gorgeous Contemporary Fireplaces
    meta_description: Learn how to style contemporary fireplaces with rich textures and modern finishes.
    url_slug: gorgeous-contemporary-fireplaces
    focus_keyphrase: contemporary fireplaces
    """
    result = extract_json_object(lines)
    assert result["seo_title"] == "Gorgeous Contemporary Fireplaces"
    assert "contemporary fireplaces" in result["meta_description"]


def test_replace_image_placeholders():
    html = """
    <h1>Fireplace Guide</h1>
    <h2>Rustic Stone</h2>
    <p>Details about stone.</p>
    [image space]
    <h2>Modern Sleek</h2>
    <p>Details about sleek.</p>
    [image space]
    """
    urls = ["https://example.com/img1.avif", "https://example.com/img2.avif"]
    res = replace_image_placeholders(html, urls)
    assert '<img src="https://example.com/img1.avif" alt="Article Image 1"' in res
    assert '<img src="https://example.com/img2.avif" alt="Article Image 2"' in res
    assert "[image space]" not in res


def test_parse_pinterest_description_exact_and_unguarded():
    from app.services.pinterest_service import parse_pinterest_description
    import json

    # Clean JSON
    valid_raw = '{"meta_description": "A cozy fireplace guide."}'
    assert parse_pinterest_description(valid_raw) == "A cozy fireplace guide."

    # Fenced JSON matching n8n text.replace(/```json|```/g, '').trim()
    fenced_raw = '```json\n{"meta_description": "Fenced description."}\n```'
    assert parse_pinterest_description(fenced_raw) == "Fenced description."

    # Non-JSON string fallback
    broken_raw = "Not a json object"
    assert parse_pinterest_description(broken_raw) == "Not a json object"

    # Missing meta_description key fallback
    missing_key = '{"other_key": "val"}'
    assert parse_pinterest_description(missing_key) == ""

