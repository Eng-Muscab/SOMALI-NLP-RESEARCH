import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[1]
load_dotenv(BACKEND_DIR / ".env")


class Settings(BaseModel):
    app_name: str = Field(default="Somali NLP Research API")
    environment: str = Field(default="development")
    api_prefix: str = Field(default="/api")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    mongodb_uri: str = Field(default="mongodb://localhost:27017")
    mongo_db_name: str = Field(default="somali_nlp")
    mongodb_timeout_ms: int = Field(default=3000)
    secret_key: str = Field(default="change-me")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)
    models_dir: Path = Field(default=REPO_ROOT / "models")
    experiments_dir: Path = Field(default=REPO_ROOT / "experiments")
    uploads_dir: Path = Field(default=BACKEND_DIR / "uploads")


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _path_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    path = Path(value) if value else default
    return path if path.is_absolute() else BACKEND_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", Settings.model_fields["app_name"].default),
        environment=os.getenv("ENVIRONMENT", Settings.model_fields["environment"].default),
        api_prefix=os.getenv("API_PREFIX", Settings.model_fields["api_prefix"].default),
        cors_origins=_csv_env("CORS_ORIGINS", ["http://localhost:5173"]),
        mongodb_uri=os.getenv("MONGODB_URI", Settings.model_fields["mongodb_uri"].default),
        mongo_db_name=os.getenv("MONGO_DB_NAME", Settings.model_fields["mongo_db_name"].default),
        mongodb_timeout_ms=int(
            os.getenv(
                "MONGODB_TIMEOUT_MS",
                str(Settings.model_fields["mongodb_timeout_ms"].default),
            )
        ),
        secret_key=os.getenv("SECRET_KEY", Settings.model_fields["secret_key"].default),
        algorithm=os.getenv("ALGORITHM", Settings.model_fields["algorithm"].default),
        access_token_expire_minutes=int(
            os.getenv(
                "ACCESS_TOKEN_EXPIRE_MINUTES",
                str(Settings.model_fields["access_token_expire_minutes"].default),
            )
        ),
        models_dir=_path_env("MODELS_DIR", REPO_ROOT / "models"),
        experiments_dir=_path_env("EXPERIMENTS_DIR", REPO_ROOT / "experiments"),
        uploads_dir=_path_env("UPLOADS_DIR", BACKEND_DIR / "uploads"),
    )


settings = get_settings()

MONGODB_URI = settings.mongodb_uri
MONGO_DB_NAME = settings.mongo_db_name
MONGODB_TIMEOUT_MS = settings.mongodb_timeout_ms
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
MODELS_DIR = settings.models_dir
EXPERIMENTS_DIR = settings.experiments_dir
UPLOADS_DIR = settings.uploads_dir
