from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "oversea-amazon-mvp"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/oversea"
    redis_url: str = "redis://localhost:6379/0"
    debug_mode: bool = True
    use_live_apify: bool = False
    apify_timeout_seconds: int = 240
    apify_snapshot_fallback: bool = False
    apify_snapshot_keyword: str = "desk lamp"
    apify_api_token: str | None = None
    apify_amazon_scraper_actor_id: str | None = None
    apify_token: str | None = None
    apify_api_key: str | None = None
    apify_amazon_search_actor: str | None = None
    apify_actor_id: str | None = None
    apify_amazon_actor_id: str | None = None
    apify_amazon_crawler_actor_id: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:
        if not self.apify_api_token:
            self.apify_api_token = self.apify_token or self.apify_api_key
        if not self.apify_amazon_scraper_actor_id:
            self.apify_amazon_scraper_actor_id = (
                self.apify_amazon_search_actor
                or self.apify_actor_id
                or self.apify_amazon_actor_id
                or self.apify_amazon_crawler_actor_id
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
