import datetime
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    telegram_user_id: int

    llm_provider: str = "gemini"  # claude | openai | gemini
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_gemini_api_key: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "idea-bot/1.0"

    product_hunt_token: str = ""

    discovery_hour: int = 2
    discovery_minute: int = 0

    data_api_url: str = "http://data-api:8001"
    data_api_key: str = ""
    memory_agent_url: str = "http://memory-agent:8002"

    github_token: str = ""
    github_repo: str = ""  # format: "owner/repo"

    home_location: str = ""  # e.g. "Moscow, Russia" — fallback if not set via /sethome

    @property
    def discovery_time(self) -> datetime.time:
        return datetime.time(self.discovery_hour, self.discovery_minute, tzinfo=datetime.timezone.utc)


settings = Settings()
