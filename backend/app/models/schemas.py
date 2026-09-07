from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    writing_article = "writing_article"
    generating_seo = "generating_seo"
    generating_image_prompts = "generating_image_prompts"
    generating_images = "generating_images"
    uploading_images = "uploading_images"
    publishing_wordpress = "publishing_wordpress"
    publishing_pinterest = "publishing_pinterest"
    completed = "completed"
    failed = "failed"


class GenerateArticleRequest(BaseModel):
    title: str = Field(..., min_length=3, description="Article title/keyword, same as the n8n form field")


class SeoMetadata(BaseModel):
    seo_title: str
    meta_description: str
    url_slug: str
    focus_keyphrase: str
    secondary_keywords: list[str]


class GeneratedImage(BaseModel):
    prompt: str
    image_index: int
    cloudinary_url: str | None = None
    avif_url: str | None = None
    wordpress_media_id: int | None = None
    wordpress_media_url: str | None = None


class JobFeedbackRequest(BaseModel):
    notes: str = Field(..., min_length=1, description="Editorial review feedback notes")
    category: str | None = "general"


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    title: str
    article_html: str | None = None
    formatted_content: str | None = None
    seo: SeoMetadata | None = None
    images: list[GeneratedImage] = []
    wordpress_post_id: int | None = None
    wordpress_post_link: str | None = None
    pinterest_pin_id: str | None = None
    pinterest_pins: list[dict] = []
    feedback: list[dict] = []
    error: str | None = None
    error_stage: JobStatus | None = None

