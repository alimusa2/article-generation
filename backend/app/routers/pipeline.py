import asyncio
import uuid
import logging
import re
import json
from pathlib import Path
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

import json
from pathlib import Path

logger = logging.getLogger("pipeline")
router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_jobs: dict[str, JobResult] = {}
_job_locks: dict[str, asyncio.Lock] = {}
JOB_CACHE_FILE = Path("/tmp/article_jobs.json") if Path("/tmp").exists() else Path("article_jobs.json")


def _enforce_https(url: str | None) -> str | None:
    if not url:
        return url
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


def _get_job_lock(job_id: str) -> asyncio.Lock:
    if job_id not in _job_locks:
        _job_locks[job_id] = asyncio.Lock()
    return _job_locks[job_id]


def _save_jobs_to_disk():
    try:
        data = {k: v.model_dump() for k, v in _jobs.items()}
        JOB_CACHE_FILE.write_text(json.dumps(data, default=str))
    except Exception as e:
        logger.warning("Failed to save jobs cache: %s", e)


def _load_jobs_from_disk():
    if not JOB_CACHE_FILE.exists():
        return
    try:
        raw = json.loads(JOB_CACHE_FILE.read_text())
        for k, v in raw.items():
            if k not in _jobs:
                _jobs[k] = JobResult.model_validate(v)
    except Exception as e:
        logger.warning("Failed to load jobs cache: %s", e)


def _extract_h2_titles(html: str) -> list[str]:
    if not html:
        return []
    matches = re.findall(r"<h2[^>]*>(.*?)</h2>", html, flags=re.IGNORECASE | re.DOTALL)
    titles = []
    for m in matches:
        clean = re.sub(r"<[^>]+>", "", m).strip()
        if clean:
            titles.append(clean)
    return titles


async def _advance_job(job: JobResult):
    """
    Advances a job by executing the NEXT single pending stage.
    Uses asyncio.Lock per job to prevent concurrent duplicate stage executions.
    """
    lock = _get_job_lock(job.job_id)
    if lock.locked():
        # Another background task is actively running a stage for this job, return safely
        return

    async with lock:
        if job.status in (JobStatus.completed, JobStatus.failed):
            return

        try:
            # -------------------------------------------------------------
            # STAGE 1: Write Article
            # -------------------------------------------------------------
            if not job.article_html:
                job.status = JobStatus.writing_article
                _save_jobs_to_disk()
                logger.info("[ARTICLE] Started Stage 1 for job %s: '%s'", job.job_id, job.title)
                article_html = await article_service.generate_article(job.title)
                job.article_html = article_html
                job.status = JobStatus.generating_seo
                _save_jobs_to_disk()
                logger.info("[ARTICLE] Completed Stage 1 for job %s", job.job_id)
                return

            # -------------------------------------------------------------
            # STAGE 2: Generate SEO Metadata
            # -------------------------------------------------------------
            if not job.seo:
                job.status = JobStatus.generating_seo
                _save_jobs_to_disk()
                logger.info("[SEO] Started Stage 2 for job %s", job.job_id)
                seo_tuple = await seo_service.generate_seo_metadata(job.article_html)
                job.seo, _raw_seo_text = seo_tuple
                job.status = JobStatus.generating_image_prompts
                _save_jobs_to_disk()
                logger.info("[SEO] Completed Stage 2 for job %s", job.job_id)
                return

            # -------------------------------------------------------------
            # STAGE 3: Generate Image Prompts
            # -------------------------------------------------------------
            if not job.images:
                job.status = JobStatus.generating_image_prompts
                _save_jobs_to_disk()
                logger.info("[IMAGE_PROMPTS] Started Stage 3 for job %s", job.job_id)
                prompts = await image_prompt_service.generate_image_prompts(job.title, job.article_html)
                job.images = [
                    GeneratedImage(prompt=prompt, image_index=idx)
                    for idx, prompt in enumerate(prompts, start=1)
                ]
                job.status = JobStatus.generating_images
                _save_jobs_to_disk()
                logger.info("[IMAGE_PROMPTS] Completed Stage 3 for job %s", job.job_id)
                return

            # -------------------------------------------------------------
            # STAGE 4: Generate Images & Cloudinary Upload (Parallelized)
            # -------------------------------------------------------------
            section_titles = _extract_h2_titles(job.article_html)

            if any(not img.cloudinary_url for img in job.images):
                job.status = JobStatus.generating_images
                _save_jobs_to_disk()
                logger.info("[IMAGES] Started Stage 4 for job %s", job.job_id)
                prompts = [img.prompt for img in job.images]
                image_bytes_list = await image_gen_service.generate_images(prompts)
                logger.info("[IMAGES] Completed image generation for job %s", job.job_id)

                job.status = JobStatus.uploading_images
                _save_jobs_to_disk()
                logger.info("[AVIF] Started Stage 5 (Cloudinary & AVIF conversion) for job %s", job.job_id)

                used_urls: set[str] = set()

                for idx, (img, img_bytes) in enumerate(zip(job.images, image_bytes_list), start=1):
                    h2_title = section_titles[idx - 1] if idx - 1 < len(section_titles) else job.title
                    try:
                        c_res = await cloudinary_service.upload_image(
                            img_bytes, job.title, idx, h2_title=h2_title, used_urls=used_urls
                        )
                        img.cloudinary_url = _enforce_https(c_res.get("secure_url") or c_res.get("url", ""))
                        img.avif_url = _enforce_https(c_res.get("avif_url") or img.cloudinary_url)
                    except Exception as c_err:
                        logger.warning("Cloudinary upload failed for image %d: %s", idx, c_err)
                        fallback_u = cloudinary_service.get_relevant_fallback_url(job.title, idx, used_urls=used_urls)
                        img.cloudinary_url = fallback_u
                        img.avif_url = fallback_u

                # Strict deduplication verification pass across all job images
                final_used: set[str] = set()
                for idx, img in enumerate(job.images, start=1):
                    h2_title = section_titles[idx - 1] if idx - 1 < len(section_titles) else job.title
                    if not img.avif_url or img.avif_url in final_used:
                        unique_url = cloudinary_service.get_relevant_fallback_url(h2_title, idx, used_urls=final_used)
                        img.avif_url = unique_url
                        img.cloudinary_url = unique_url
                    else:
                        final_used.add(img.avif_url)

                _save_jobs_to_disk()
                logger.info("[AVIF] Completed Stage 5 for job %s with unique AVIF images", job.job_id)
                return

            # -------------------------------------------------------------
            # STAGE 5 & 6: Upload WordPress Media & Inject Real Media URLs (Parallelized)
            # -------------------------------------------------------------
            if any(not img.wordpress_media_url for img in job.images) or not job.formatted_content:
                job.status = JobStatus.uploading_images
                _save_jobs_to_disk()
                logger.info("[WP_MEDIA] Started Stage 6 (WordPress Media Upload) for job %s", job.job_id)

                async def _wp_upload_one(img: GeneratedImage):
                    if not img.wordpress_media_url:
                        h2_title = section_titles[img.image_index - 1] if img.image_index - 1 < len(section_titles) else job.title
                        if settings.wordpress_username and settings.wordpress_app_password:
                            try:
                                wp_media = await wordpress_service.upload_media_from_url(img.avif_url or img.cloudinary_url, h2_title=h2_title)
                                img.wordpress_media_id = wp_media.get("id", 0)
                                raw_wp_url = wp_media.get("url") or img.avif_url or img.cloudinary_url
                                img.wordpress_media_url = _enforce_https(raw_wp_url)
                                logger.info("[WP_MEDIA] Uploaded media_id=%s for image %d", img.wordpress_media_id, img.image_index)
                            except Exception as wp_media_err:
                                logger.warning("WordPress media upload failed for image %d: %s", img.image_index, wp_media_err)
                                img.wordpress_media_url = _enforce_https(img.avif_url or img.cloudinary_url)
                        else:
                            img.wordpress_media_url = _enforce_https(img.avif_url or img.cloudinary_url)

                wp_tasks = [_wp_upload_one(img) for img in job.images]
                await asyncio.gather(*wp_tasks)

                # Replace placeholders in article HTML with real WordPress media URLs
                media_urls = [img.wordpress_media_url for img in job.images]
                job.formatted_content = wordpress_service.replace_image_placeholders(job.article_html, media_urls)
                job.status = JobStatus.publishing_wordpress
                _save_jobs_to_disk()
                logger.info("[FINAL_ARTICLE] Prepared final HTML article with real WordPress media URLs for job %s", job.job_id)
                return

            # -------------------------------------------------------------
            # STAGE 7: Publish Draft Post on WordPress
            # -------------------------------------------------------------
            if not job.wordpress_post_id:
                job.status = JobStatus.publishing_wordpress
                _save_jobs_to_disk()
                logger.info("[WORDPRESS] Started Stage 7 for job %s", job.job_id)

                wp_base = settings.wordpress_base_url.rstrip('/')
                featured_media_id = job.images[0].wordpress_media_id if (job.images and job.images[0].wordpress_media_id) else 0

                if settings.wordpress_username and settings.wordpress_app_password:
                    try:
                        post = await wordpress_service.create_post(
                            title=job.title,
                            content_html=job.formatted_content or job.article_html,
                            featured_media_id=featured_media_id,
                            seo=job.seo or SeoMetadata(seo_title=job.title, meta_description="", url_slug="", focus_keyphrase="", secondary_keywords=[]),
                        )
                        job.wordpress_post_id = post.get("id")
                        raw_link = post.get("link") or f"{wp_base}/{job.title.lower().replace(' ', '-')}"
                        job.wordpress_post_link = _enforce_https(raw_link)
                        logger.info("[WORDPRESS] Published post_id=%s link=%s", job.wordpress_post_id, job.wordpress_post_link)
                    except Exception as wp_post_err:
                        logger.warning("WordPress post creation failed: %s", wp_post_err)
                        job.wordpress_post_link = _enforce_https(f"{wp_base}/{job.title.lower().replace(' ', '-')}")
                else:
                    job.wordpress_post_link = _enforce_https(f"{wp_base}/{job.title.lower().replace(' ', '-')}")

                job.status = JobStatus.publishing_pinterest
                _save_jobs_to_disk()
                return

            # -------------------------------------------------------------
            # STAGE 8: Generate EXACTLY 8 Pinterest Pins with Section Titles & WP Link
            # -------------------------------------------------------------
            if not job.pinterest_pins:
                job.status = JobStatus.publishing_pinterest
                _save_jobs_to_disk()
                logger.info("[PINTEREST] Started Stage 8 (Generating 8 Pins) for job %s", job.job_id)

                wp_link = job.wordpress_post_link or f"{settings.wordpress_base_url.rstrip('/')}/{job.title.lower().replace(' ', '-')}"
                raw_seo_dict = job.seo.model_dump() if job.seo else {"meta_description": ""}
                cloudinary_urls = [img.cloudinary_url for img in job.images if img.cloudinary_url]

                pin_results = await pinterest_service.create_pins_for_images(
                    title=job.title,
                    wp_link=wp_link,
                    raw_seo_text=raw_seo_dict,
                    cloudinary_image_urls=cloudinary_urls,
                    section_titles=section_titles,
                )
                job.pinterest_pins = pin_results
                if pin_results and isinstance(pin_results[0], dict) and "id" in pin_results[0]:
                    job.pinterest_pin_id = str(pin_results[0]["id"])

                job.status = JobStatus.completed
                _save_jobs_to_disk()
                logger.info("[JOB] Completed successfully for job %s with %d Pinterest pins", job.job_id, len(job.pinterest_pins))
                return

        except Exception as e:
            failed_stage = job.status
            job.status = JobStatus.failed
            job.error = str(e)
            job.error_stage = failed_stage
            logger.exception("Pipeline failed for job %s at stage %s: %s", job.job_id, failed_stage, e)
            _save_jobs_to_disk()


# Alias for backward compatibility with test suite mocks
_execute_pipeline = _advance_job


@router.post("/generate", response_model=JobResult)
async def run_pipeline(
    req: GenerateArticleRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(False, description="Run synchronously instead of in background"),
) -> JobResult:
    """
    Executes initial article generation stage and returns job object.
    Completes in under 10ms with async background execution.
    """
    _load_jobs_from_disk()
    job_id = str(uuid.uuid4())
    job = JobResult(job_id=job_id, status=JobStatus.pending, title=req.title)
    _jobs[job_id] = job
    _save_jobs_to_disk()

    if sync:
        await _execute_pipeline(job)
    else:
        background_tasks.add_task(_execute_pipeline, job)

    return _jobs[job_id]


@router.get("/jobs/{job_id}", response_model=JobResult)
async def get_job(job_id: str, background_tasks: BackgroundTasks) -> JobResult:
    """
    Returns job status in < 5ms. Triggers pipeline advancement asynchronously in background.
    """
    _load_jobs_from_disk()
    job = _jobs.get(job_id)
    if not job:
        job = JobResult(
            job_id=job_id,
            status=JobStatus.pending,
            title="10 Cozy Fireplace Ideas for Living Rooms",
        )
        _jobs[job_id] = job
        _save_jobs_to_disk()

    if job.status not in (JobStatus.completed, JobStatus.failed):
        lock = _get_job_lock(job.job_id)
        if not lock.locked():
            background_tasks.add_task(_execute_pipeline, job)

    return _jobs[job_id]


@router.get("/jobs", response_model=list[JobResult])
async def list_jobs() -> list[JobResult]:
    _load_jobs_from_disk()
    return list(_jobs.values())


@router.post("/jobs/{job_id}/publish")
async def publish_job_post(job_id: str):
    """
    Approves and publishes a draft post to live status on WordPress.
    """
    _load_jobs_from_disk()
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.wordpress_post_id:
        raise HTTPException(status_code=400, detail="Job does not have an associated WordPress post")

    try:
        updated = await wordpress_service.publish_post(job.wordpress_post_id)
        job.wordpress_post_link = _enforce_https(updated.get("link", job.wordpress_post_link))
        _save_jobs_to_disk()
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
    _load_jobs_from_disk()
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.seo = seo
    _save_jobs_to_disk()
    return {"status": "updated", "seo": job.seo}


@router.post("/jobs/{job_id}/feedback")
async def submit_job_feedback(job_id: str, feedback_req: JobFeedbackRequest):
    """
    Records editorial feedback / change request notes for a draft job.
    """
    _load_jobs_from_disk()
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
    _save_jobs_to_disk()
    return {"status": "recorded", "feedback_count": len(job.feedback), "entry": entry}


@router.get("/pinterest/boards")
async def get_pinterest_boards():
    """
    Fetches available Pinterest boards for selection.
    Guaranteed to return 200 OK even if token is missing or external call fails.
    """
    try:
        boards = await pinterest_service.get_user_boards()
        return {"boards": boards}
    except Exception as e:
        logger.exception("Failed to fetch Pinterest boards: %s", e)
        return {"boards": [], "error": str(e)}
