"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Deployment mode
    deploy_mode: str = "cloud"  # "cloud" | "local"

    # App
    app_name: str = "AI Workflow Terminal"
    app_version: str = "0.8.0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    app_cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "aiwt"
    postgres_password: str = "changeme"
    postgres_db: str = "ai_workflow_terminal"

    database_url_override: str = ""

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # Vector DB
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Object Storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "changeme"
    minio_bucket: str = "ai-workflow"
    minio_secure: bool = False

    # Auth
    jwt_secret_key: str = "changeme_generate_a_random_64char_string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440
    jwt_refresh_token_expire_days: int = 30

    # LLM Providers
    llm_default_provider: str = "qwen-cloud"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    vllm_base_url: str = "http://192.168.1.23:8001"
    vllm_model: str = "qwen3.5-35b-a3b"

    # HAL Bridge
    hal_bridge_enabled: bool = False
    hal_bridge_ws_port: int = 9200

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
