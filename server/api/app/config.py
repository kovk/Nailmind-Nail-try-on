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
    demo_email: str = "luna@nailmind.app"
    demo_password: str = "123456"
    jwt_secret: str = "replace-with-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    worker_token: str = "replace-with-a-long-random-worker-token"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @property
    def uploads_dir(self) -> Path:
        return Path(self.data_dir) / "uploads"

    @property
    def results_dir(self) -> Path:
        return Path(self.data_dir) / "results"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
