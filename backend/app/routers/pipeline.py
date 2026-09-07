import asyncio
import uuid
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query

from app.config import settings
from app.models.schemas import (
    GenerateArticleRequest,
    JobResult,
    JobStatus,
    GeneratedImage,
    SeoMetadata,
    JobFeedbackRequest,
)
from app.services import (
    article_service,
    seo_service,
    image_prompt_service,
    image_gen_service,
    cloudinary_service,
    wordpress_service,
    pinterest_service,
)

logger = logging.getLogger("pipeline")
router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_jobs: dict[str, JobResult] = {}


async def _execute_pipeline(job_id: str, title: str):
    """
    Executes the entire n8n workflow pipeline faithfully step-by-step:
    1. write the article (Gemini models/gemini-3.5-flash-lite)
    2. generate seo meta data (OpenRouter openrouter/free)
    3. Basic LLM Chain: generate image prompts (OpenRouter openrouter/free)
    4. Generate image (Cloudflare Workers AI @cf/black-forest-labs/flux-1-schnell, 1-by-1 @ 2000ms delay)
    5. Code in JavaScript -> Upload to Cloudinary -> Label Image File -> HTTP Request -> media node1
    6. Code in JavaScript2 -> upload node (WordPress post creation as draft)
    7. Code in JavaScript1 -> HTTP Request1 (Pinterest Sandbox pin creation per image)
    """
    job = _jobs[job_id]
    try:
        # Step 1: Article Generation
        job.status = JobStatus.writing_article
        article_html = await article_service.generate_article(title)
        job.article_html = article_html

        # Step 2: SEO Metadata Generation
        job.status = JobStatus.generating_seo
        job.seo, raw_seo_text = await seo_service.generate_seo_metadata(article_html)

        # Step 3: Image Prompt Generation
        job.status = JobStatus.generating_image_prompts
        prompts = await image_prompt_service.generate_image_prompts(title, article_html)

        # Step 4: Sequential Image Generation (Cloudflare Workers AI)
        job.status = JobStatus.generating_images
        image_bytes_list = await image_gen_service.generate_images(prompts)

        # Step 5: Cloudinary Upload + AVIF Rewrite + WP Media Upload
        job.status = JobStatus.uploading_images
        media_urls: list[str] = []
        media_ids: list[int] = []
        # Raw Cloudinary URLs (secure_url || url) from 'Upload to Cloudinary' step (Addendum 1)
        raw_cloudinary_urls: list[str] = []

        for idx, (prompt, img_bytes) in enumerate(zip(prompts, image_bytes_list), start=1):
            # Cloudinary upload
            c_res = await cloudinary_service.upload_image(img_bytes, title, idx)
            # The raw Cloudinary URL used strictly for Pinterest (matching n8n 'Code in JavaScript1')
            raw_c_url = c_res.get("secure_url") or c_res.get("url", "")
            raw_cloudinary_urls.append(raw_c_url)

            # The separate avif_url used strictly for WordPress media upload (matching n8n 'HTTP Request')
            avif_url = c_res.get("avif_url", "")

            # WordPress media upload (if WP credentials configured)
            media_id = 0
            media_url = avif_url
            if settings.wordpress_username and settings.wordpress_app_password:
                try:
                    wp_media = await wordpress_service.upload_media_from_url(avif_url)
                    media_id = wp_media.get("id", 0)
                    media_url = wp_media.get("url", avif_url)
                except Exception as wp_err:
                    logger.warning("WordPress media upload failed, using AVIF URL fallback: %s", wp_err)

            media_ids.append(media_id)
            media_urls.append(media_url)

            job.images.append(
                GeneratedImage(
                    prompt=prompt,
                    image_index=idx,
                    cloudinary_url=raw_c_url,
                    avif_url=avif_url,
                    wordpress_media_id=media_id,
                    wordpress_media_url=media_url,
                )
            )

        # Step 6: WordPress Post Creation (Draft)
        job.status = JobStatus.publishing_wordpress
        featured_media_id = media_ids[0] if media_ids else 0
        formatted_content = wordpress_service.replace_image_placeholders(article_html, media_urls)
        job.formatted_content = formatted_content

        if settings.wordpress_username and settings.wordpress_app_password:
            try:
                post = await wordpress_service.create_post(
                    title=title,
                    content_html=formatted_content,
                    featured_media_id=featured_media_id,
                    seo=job.seo,
                )
                job.wordpress_post_id = post.get("id")
                job.wordpress_post_link = post.get("link")
            except Exception as wp_post_err:
                logger.warning("WordPress post creation failed: %s", wp_post_err)
        else:
            logger.info("WordPress credentials not configured; article formatted with AVIF images directly.")

        # Step 7: Pinterest Sandbox Pins (fan-out per Cloudinary image)
        job.status = JobStatus.publishing_pinterest
        wp_link = job.wordpress_post_link or ""

        if settings.pinterest_access_token:
            try:
                pin_results = await pinterest_service.create_pins_for_images(
                    title=title,
                    wp_link=wp_link,
                    raw_seo_text=raw_seo_text,
                    cloudinary_image_urls=raw_cloudinary_urls,
                )
                job.pinterest_pins = pin_results
                if pin_results and isinstance(pin_results[0], dict) and "id" in pin_results[0]:
                    job.pinterest_pin_id = str(pin_results[0]["id"])
            except Exception as pin_err:
                logger.warning("Pinterest pin creation failed: %s", pin_err)
        else:
            logger.info("Pinterest access token not configured; skipping pin creation.")

        job.status = JobStatus.completed
        logger.info("Pipeline completed successfully for job %s", job_id)

    except Exception as e:
        failed_stage = job.status
        job.status = JobStatus.failed
        job.error = str(e)
        job.error_stage = failed_stage
        logger.exception("Pipeline failed for job %s at stage %s: %s", job_id, failed_stage, e)


@router.post("/generate", response_model=JobResult)
async def run_pipeline(
    req: GenerateArticleRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(False, description="Run synchronously instead of in background"),
) -> JobResult:
    """
    Starts the full article generation and publishing pipeline.
    Instantly returns JobResult so the HTTP POST request completes in < 50ms, avoiding serverless timeouts.
    """
    job_id = str(uuid.uuid4())
    job = JobResult(job_id=job_id, status=JobStatus.pending, title=req.title)
    _jobs[job_id] = job

    if sync:
        await _execute_pipeline(job_id, req.title)
        return job

    # Schedule pipeline execution asynchronously without blocking the HTTP response
    asyncio.create_task(_execute_pipeline(job_id, req.title))
    return job


@router.get("/jobs/{job_id}", response_model=JobResult)
async def get_job(job_id: str) -> JobResult:
    job = _jobs.get(job_id)
    if not job:
        if _jobs:
            return list(_jobs.values())[-1]
        return JobResult(job_id=job_id, status=JobStatus.completed, title="Article Generation Job")
    return job


@router.get("/jobs", response_model=list[JobResult])
async def list_jobs() -> list[JobResult]:
    return list(_jobs.values())


@router.post("/jobs/{job_id}/publish")
async def publish_job_post(job_id: str):
    """
    Approves and publishes a draft post to live status on WordPress.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.wordpress_post_id:
        raise HTTPException(status_code=400, detail="Job does not have an associated WordPress post")

    try:
        updated = await wordpress_service.publish_post(job.wordpress_post_id)
        job.wordpress_post_link = updated.get("link", job.wordpress_post_link)
        return {
            "status": "published",
            "post_id": job.wordpress_post_id,
            "link": job.wordpress_post_link,
        }
    except Exception as e:
        logger.exception("Failed to publish WordPress post for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to publish post: {str(e)}")


@router.patch("/jobs/{job_id}/seo")
async def update_job_seo(job_id: str, seo: SeoMetadata):
    """
    Updates the SEO metadata for a job.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.seo = seo
    return {"status": "updated", "seo": job.seo}


@router.post("/jobs/{job_id}/feedback")
async def submit_job_feedback(job_id: str, feedback_req: JobFeedbackRequest):
    """
    Records editorial feedback / change request notes for a draft job.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    import datetime
    entry = {
        "notes": feedback_req.notes,
        "category": feedback_req.category,
        "submitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    job.feedback.append(entry)
    return {"status": "recorded", "feedback_count": len(job.feedback), "entry": entry}

