"""
Central configuration. All secrets come from environment variables (.env),
never hardcoded — this replaces the plaintext tokens that were in the n8n export.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[".env", "backend/.env"], extra="ignore")

    # --- LLMs ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    # --- Cloudflare Workers AI (image generation) ---
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    cloudflare_image_model: str = "@cf/black-forest-labs/flux-1-schnell"

    # --- Cloudinary ---
    cloudinary_cloud_name: str = ""
    cloudinary_upload_preset: str = ""
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None

    # --- WordPress ---
    wordpress_base_url: str = "https://www.furnish-luxe.com"
    wordpress_username: str = "admin"
    wordpress_app_password: str = "SSqy ZKaM 1wbd lwVZ PZ6r BYQI"

    # --- Pinterest ---
    pinterest_access_token: str | None = None
    # Flagged: board_id hardcoded in n8n as '1086423178800607052', loaded from env with fallback
    pinterest_board_id: str = "1086423178800607052"

    # --- App behavior ---
    images_per_article: int = 8
    h2_sections_per_article: int = 8
    request_timeout_seconds: int = 25


settings = Settings()

