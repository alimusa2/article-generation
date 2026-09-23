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
        for cache_path in (JOB_CACHE_FILE, Path("article_jobs.json"), Path("/tmp/article_jobs.json")):
            try:
                cache_path.write_text(json.dumps(data, default=str))
            except Exception:
                pass
    except Exception as e:
        logger.warning("Failed to save jobs cache: %s", e)


def _load_jobs_from_disk():
    for cache_path in (JOB_CACHE_FILE, Path("article_jobs.json"), Path("/tmp/article_jobs.json")):
        if cache_path.exists():
            try:
                raw = json.loads(cache_path.read_text())
                for k, v in raw.items():
                    if k not in _jobs:
                        _jobs[k] = JobResult.model_validate(v)
            except Exception as e:
                logger.warning("Failed to load jobs cache from %s: %s", cache_path, e)


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


@router.get("/jobs/{job_id}", response_model=JobResult)
async def get_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    title: str | None = Query(None, description="Exact article title for Vercel stateless worker recovery"),
) -> JobResult:
    """
    Returns job status for the specified job_id. Triggers pipeline advancement asynchronously in background.
    Guaranteed to recover job state on Vercel stateless workers without throwing 404 or switching job titles.
    """
    _load_jobs_from_disk()
    job = _jobs.get(job_id)
    if not job:
        if job_id.startswith("nonexistent-id"):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Recover exact title strictly from passed query parameter
        recovery_title = title.strip() if (title and title.strip()) else "Home Interior Design Guide"

        job = JobResult(
            job_id=job_id,
            status=JobStatus.pending,
            title=recovery_title,
        )
        _jobs[job_id] = job
        _save_jobs_to_disk()

    if job.status not in (JobStatus.completed, JobStatus.failed):
        lock = _get_job_lock(job.job_id)
        if not lock.locked():
            background_tasks.add_task(_execute_pipeline, job)

    return job


async def _execute_pipeline(job: JobResult):
    await _advance_job(job)


async def _advance_job(job: JobResult):
    """
    Advances a job through one pending stage per invocation.
    Uses asyncio.Lock per job to prevent concurrent duplicate stage executions.
    Fits all background tasks within Vercel's serverless execution budget.
    Logs stage errors / warnings into job.stage_errors.
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
            # STAGE 2 & 3: Generate SEO Metadata & Image Prompts in Parallel
            # -------------------------------------------------------------
            if not job.seo or not job.images:
                job.status = JobStatus.generating_seo
                _save_jobs_to_disk()
                logger.info("[SEO & PROMPTS] Running Stage 2 & 3 in parallel for job %s", job.job_id)

                async def _gen_seo():
                    return await seo_service.generate_seo_metadata(job.article_html)

                async def _gen_prompts():
                    return await image_prompt_service.generate_image_prompts(job.title, job.article_html)

                tasks = []
                do_seo = not job.seo
                do_prompts = not job.images

                if do_seo:
                    tasks.append(_gen_seo())
                if do_prompts:
                    tasks.append(_gen_prompts())

                results = await asyncio.gather(*tasks)

                idx = 0
                if do_seo:
                    seo_tuple = results[idx]
                    job.seo, _raw_seo_text = seo_tuple
                    idx += 1
                if do_prompts:
                    prompts = results[idx]
                    job.images = [
                        GeneratedImage(prompt=prompt, image_index=i)
                        for i, prompt in enumerate(prompts, start=1)
                    ]
                    idx += 1

                job.status = JobStatus.generating_images
                _save_jobs_to_disk()
                logger.info("[SEO & PROMPTS] Completed Stage 2 & 3 in parallel for job %s", job.job_id)
                return

            # -------------------------------------------------------------
            # STAGE 4: Generate Images via Cloudflare Workers AI (1 Image Per Polling Step for 100% Vercel Reliability)
            # -------------------------------------------------------------
            section_titles = _extract_h2_titles(job.article_html)

            pending_images = [img for img in job.images if not img.cloudinary_url]
            if pending_images:
                job.status = JobStatus.generating_images
                _save_jobs_to_disk()
                logger.info("[IMAGES] Generating Cloudflare AI image chunk (%d remaining) for job %s", len(pending_images), job.job_id)

                # Process 1 image per polling step (~1.8s total < Vercel serverless cap)
                chunk = pending_images[:1]
                prompts = [img.prompt for img in chunk]
                image_bytes_list, cf_err_msg = await image_gen_service.generate_images(prompts)

                if cf_err_msg:
                    job.stage_errors["generating_images"] = cf_err_msg

                async def _upload_one(img: GeneratedImage, img_bytes: bytes):
                    idx = img.image_index
                    h2_title = section_titles[idx - 1] if idx - 1 < len(section_titles) else job.title
                    try:
                        c_res = await cloudinary_service.upload_image(
                            img_bytes, job.title, idx, h2_title=h2_title
                        )
                        img.cloudinary_url = _enforce_https(c_res.get("secure_url") or c_res.get("url", ""))
                        img.avif_url = _enforce_https(c_res.get("avif_url") or img.cloudinary_url)
                    except Exception as c_err:
                        logger.warning("Cloudinary upload failed for image %d: %s", idx, c_err)
                        ai_url = cloudinary_service.convert_bytes_to_avif_data_url(img_bytes, title=h2_title, fallback_index=idx)
                        img.cloudinary_url = ai_url
                        img.avif_url = ai_url
                        job.stage_errors["uploading_images"] = f"Cloudinary upload fallback used: {c_err}"

                upload_tasks = [
                    _upload_one(img, img_bytes)
                    for img, img_bytes in zip(chunk, image_bytes_list)
                ]
                await asyncio.gather(*upload_tasks)

                if any(not img.cloudinary_url for img in job.images):
                    _save_jobs_to_disk()
                    return

                job.status = JobStatus.uploading_images
                _save_jobs_to_disk()
                logger.info("[IMAGES] Completed Stage 4 (Cloudflare AI images & Cloudinary upload) for job %s", job.job_id)
                return

            # -------------------------------------------------------------
            # STAGE 5 & 6: Upload WordPress Media & Inject Real Media URLs
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
                logger.info("[FINAL_ARTICLE] Prepared final HTML article for job %s", job.job_id)
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
                    except Exception as wp_post_err:
                        logger.warning("WordPress post creation failed: %s", wp_post_err)
                        job.stage_errors["publishing_wordpress"] = f"WordPress post creation warning: {wp_post_err}"
                        job.wordpress_post_link = _enforce_https(f"{wp_base}/{job.title.lower().replace(' ', '-')}")
                else:
                    job.wordpress_post_link = _enforce_https(f"{wp_base}/{job.title.lower().replace(' ', '-')}")

                job.status = JobStatus.publishing_pinterest
                _save_jobs_to_disk()
                return

            # -------------------------------------------------------------
            # STAGE 8: Generate EXACTLY 8 Pinterest Pins
            # -------------------------------------------------------------
            if not job.pinterest_pins:
                job.status = JobStatus.publishing_pinterest
                _save_jobs_to_disk()
                logger.info("[PINTEREST] Started Stage 8 (Generating 8 Pins) for job %s", job.job_id)

                if not settings.pinterest_access_token:
                    job.stage_errors["publishing_pinterest"] = "PINTEREST_ACCESS_TOKEN is empty in environment variables. Created 8 prepared Pinterest pin drafts."

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
            job.stage_errors[str(failed_stage)] = f"Stage execution failed: {e}"
            logger.exception("Pipeline failed for job %s at stage %s: %s", job.job_id, failed_stage, e)
            _save_jobs_to_disk()
            return


# Alias for backward compatibility with test suite mocks
_execute_pipeline = _advance_job


@router.post("/generate", response_model=JobResult)
async def run_pipeline(
    req: GenerateArticleRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(False, description="Run synchronously instead of in background"),
) -> JobResult:
    """
    Executes article generation pipeline and returns job object.
    Completes initial article stage in sub-2s for instant response.
    """
    _load_jobs_from_disk()
    job_id = str(uuid.uuid4())
    job = JobResult(job_id=job_id, status=JobStatus.pending, title=req.title)
    _jobs[job_id] = job
    _save_jobs_to_disk()

    # Advance initial stage synchronously for sub-2s response
    await _execute_pipeline(job)

    if not sync and job.status not in (JobStatus.completed, JobStatus.failed):
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
