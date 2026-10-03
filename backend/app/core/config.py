from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "PATTERN"
    environment: str = "development"
    database_url: str = "sqlite:///./pattern.db"
    cors_origins: str = "http://localhost:5173"
    ingest_api_key: str = "change-me"
    ollama_enabled: bool = False
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:14b"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
