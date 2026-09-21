"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "CRPF Tender Evaluation API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Database Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "tender_evaluation"
    DATABASE_URL: str | None = None
    TEST_DATABASE_URL: str | None = None

    # Database Connection Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Authentication & JWT Configuration
    JWT_SECRET_KEY: str = "change-me-in-development-secure-random-secret-key-32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    MIN_PASSWORD_LENGTH: int = 8

    # Object Storage & Upload Configuration
    S3_ENDPOINT: str | None = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "tender-documents"
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False
    MAX_UPLOAD_SIZE_MB: int = 50

    # Document Processing Pipeline Configuration
    MAX_DOCUMENT_PAGES: int = 200
    PROCESSING_TIMEOUT_SECONDS: int = 120
    MAX_IMAGE_PIXELS: int = 50_000_000
    PROCESSOR_VERSION: str = "1.0.0"
    MAX_JOB_ATTEMPTS: int = 3
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0

    # Redis Queue & Asynchronous Worker Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    WORKER_CONCURRENCY: int = 3
    WORKER_MAX_RETRIES: int = 3
    WORKER_TIMEOUT_SECONDS: int = 300
    DOCUMENT_PROCESSING_TIMEOUT_SECONDS: int = 300
    TESSERACT_CMD: str | None = None

    # AI Criterion & Evidence Extraction Configuration (Phases 7, 10 & 21)
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-2.5-flash"
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None
    LLM_TIMEOUT: int = 60
    LLM_FALLBACK_PROVIDER: str | None = "groq"
    LLM_FALLBACK_API_KEY: str | None = None
    LLM_FALLBACK_MODEL: str | None = "openai/gpt-oss-120b"
    VLM_PROVIDER: str = "gemini"
    VLM_MODEL: str = "gemini-2.5-flash"
    EXTRACTION_PROMPT_VERSION: str = "criterion_extraction_v1"
    EXTRACTOR_VERSION: str = "1.0.0"
    MAX_EXTRACTION_CHUNK_SIZE: int = 4000

    # Hybrid Retrieval & Search Configuration (Phase 10)
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_MODEL_VERSION: str = "v1.0"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_API_KEY: str | None = None
    LEXICAL_WEIGHT: float = 0.4
    SEMANTIC_WEIGHT: float = 0.6
    DEFAULT_TOP_K: int = 10
    RETRIEVAL_TOP_K: int = 10
    MAX_TOP_K: int = 50
    INDEXER_VERSION: str = "1.0.0"
    CHUNKER_VERSION: str = "1.0.0"
    MAX_RETRIEVAL_CHUNK_CHARS: int = 1500

    # Deterministic Rule Engine & OPA Configuration (Phase 11)
    OPA_ENABLED: bool = True
    OPA_URL: str = "http://localhost:8181"
    OPA_POLICY_PACKAGE: str = "crpf.evaluation"
    OPA_TIMEOUT_SECONDS: int = 10
    RULE_ENGINE_VERSION: str = "1.0.0"
    DEFAULT_POLICY_VERSION: str = "v1.0"
    MIN_EVALUATION_CONFIDENCE: float = 0.70

    # CORS & Security Hardening (Phase 15)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    SECURITY_HEADERS_ENABLED: bool = True

    # Rate Limiting & Abuse Protection (Phase 15)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 20
    RATE_LIMIT_REPORT_PER_MINUTE: int = 15
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120

    @property
    def database_url_str(self) -> str:
        """Return the effective database connection URL."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def validate_production_readiness(self) -> None:
        """Enforce strict security and configuration constraints in production mode."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG mode must be disabled (False) in production environment.")
            if "change-me" in self.JWT_SECRET_KEY.lower() or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("Insecure JWT_SECRET_KEY detected. Production requires a secure 32+ char secret.")
            if "*" in self.CORS_ORIGINS and self.CORS_ALLOW_CREDENTIALS:
                raise ValueError("CORS cannot allow wildcard '*' origins when credentials are enabled in production.")
            if not self.S3_BUCKET:
                raise ValueError("S3_BUCKET cannot be empty in production environment.")
            if self.S3_ACCESS_KEY in ("replace_with_s3_or_minio_access_key", ""):
                raise ValueError("S3_ACCESS_KEY must be configured with valid credentials in production.")
            if self.S3_SECRET_KEY in ("replace_with_s3_or_minio_secret_key", ""):
                raise ValueError("S3_SECRET_KEY must be configured with valid credentials in production.")
            if self.OPA_ENABLED and not self.OPA_URL:
                raise ValueError("OPA_URL must be specified when OPA_ENABLED is True in production.")


@lru_cache()
def get_settings() -> Settings:
    """Return cached instance of application settings."""
    settings = Settings()
    settings.validate_production_readiness()
    return settings
