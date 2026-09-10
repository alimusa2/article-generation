import io
import base64
import pytest
from PIL import Image

from app.services import cloudinary_service, wordpress_service
from app.models.schemas import JobResult, JobStatus, GeneratedImage
from app.routers.pipeline import _advance_job


def test_avif_conversion_and_resolution():
    # Create sample RGB image
    img = Image.new("RGB", (800, 600), color=(255, 100, 50))
    out = io.BytesIO()
    img.save(out, format="JPEG")
    jpeg_bytes = out.getvalue()

    avif_data_url = cloudinary_service.convert_bytes_to_avif_data_url(jpeg_bytes, title="Modern Living Room", fallback_index=1)
    
    assert avif_data_url.startswith("data:image/avif;base64,")
    header, b64_str = avif_data_url.split(",", 1)
    raw_bytes = base64.b64decode(b64_str)
    
    # Open converted image with PIL and check resolution
    converted_img = Image.open(io.BytesIO(raw_bytes))
    assert converted_img.size == (1000, 700)


def test_fallback_url_deduplication():
    used_urls = set()
    fallback_urls = []
    title = "10 Modern Dining Room Ideas"

    for i in range(1, 9):
        url = cloudinary_service.get_relevant_fallback_url(title, index=i, used_urls=used_urls)
        fallback_urls.append(url)

    # Enforce strict rule: all 8 image URLs must be unique (no duplicates)
    assert len(fallback_urls) == 8
    assert len(set(fallback_urls)) == 8

    # Enforce exact 1000x700 query parameters in fallback unsplash URLs
    for url in fallback_urls:
        assert "w=1000" in url
        assert "h=700" in url


def test_wordpress_placeholder_replacement_dimensions():
    html_input = "<h2>Section 1</h2>\n<p>Content</p>\n[image space]\n<h2>Section 2</h2>\n<p>Content</p>\n[image space]"
    media_urls = [
        "https://example.com/image1.avif",
        "https://example.com/image2.avif"
    ]
    result_html = wordpress_service.replace_image_placeholders(html_input, media_urls)

    assert 'width="1000"' in result_html
    assert 'height="700"' in result_html
    assert 'aspect-ratio:1000/700' in result_html
    assert 'https://example.com/image1.avif' in result_html
    assert 'https://example.com/image2.avif' in result_html


@pytest.mark.asyncio
async def test_pipeline_deduplication_stage():
    from app.models.schemas import SeoMetadata
    # Setup job with 8 image placeholders and completed prior stages (article & SEO)
    job = JobResult(
        job_id="test-dedup-job",
        status=JobStatus.generating_images,
        title="Modern Kitchen Design",
        article_html="<h2>Kitchen Island</h2><p>Text</p>[image space]" * 8,
        seo=SeoMetadata(seo_title="Title", meta_description="Desc", url_slug="slug", focus_keyphrase="key", secondary_keywords=[]),
        images=[GeneratedImage(prompt=f"Prompt {i}", image_index=i) for i in range(1, 9)],
    )

    # Run _advance_job stage for images
    await _advance_job(job)

    # Verify that all 8 images have unique avif_url
    avif_urls = [img.avif_url for img in job.images if img.avif_url]
    assert len(avif_urls) == 8
    assert len(set(avif_urls)) == 8
