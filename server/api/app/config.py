from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Nail Mind API"
    addr: str = "0.0.0.0"
    port: int = 8080
    database_url: str = "sqlite:////app/data/nailmind.db"
    data_dir: str = "/app/data"
    public_base_url: str = "http://localhost:8080"
    allowed_origins: str = "*"
    jwt_secret: str = "replace-with-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    worker_token: str = "replace-with-a-long-random-worker-token"
    dashscope_api_key: str = ""
    openclaw_api_key: str = ""
    openclaw_base_url: str = ""
    openclaw_model: str = "mimo-v2.5-pro"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @property
    def uploads_dir(self) -> Path:
        return Path(self.data_dir) / "uploads"

    @property
    def results_dir(self) -> Path:
        return Path(self.data_dir) / "results"

    @property
    def static_dir(self) -> Path:
        return Path(self.data_dir) / "static"

    @property
    def static_styles_dir(self) -> Path:
        return self.static_dir / "styles"

    @property
    def static_hands_dir(self) -> Path:
        return self.static_dir / "hands"

    @property
    def logs_dir(self) -> Path:
        return Path(self.data_dir) / "logs"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
