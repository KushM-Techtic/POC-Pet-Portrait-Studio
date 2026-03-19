from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_port: int = 9000

    shopify_store_domain: str
    shopify_api_version: str = "2026-01"
    shopify_admin_access_token: str
    shopify_poc_tag: str = "poc-ai-gen"

    # Metafields to fetch for each product
    shopify_metafield_namespace: str = "custom"
    shopify_metafield_keys_csv: str = "pet_image,template_image,style_image,pet_name,pet_type"

    gemini_api_key: str | None = None
    # Best default per Nano Banana docs: 3.1 Flash Image for general purpose.
    gemini_image_model: str = "gemini-3.1-flash-image-preview"
    # Fallback model used automatically on rate-limit/quota errors.
    gemini_fallback_model: str = "gemini-2.5-flash-image"
    # Best practice: constrain output to a portrait aspect ratio for these products.
    gemini_aspect_ratio: str = "3:4"
    # Retry/backoff to handle 429s cleanly.
    gemini_max_retries: int = 4
    gemini_initial_backoff_s: float = 2.0
    output_dir: str = "outputs"

    # Python module path for prompt (e.g. prompts.renaissance_v1); must expose get_prompt(has_style_image: bool).
    prompt_module: str = "prompts.renaissance_v1"

    # Generate-all tuning
    generate_all_first: int = 25
    generate_all_delay_ms: int = 800


settings = Settings()

