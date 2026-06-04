from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bridge_token: str = "dev-bridge-token"
    admin_token: str = "dev-admin-token"
    database_url: str = "sqlite:///./data/mcserver.db"
    server_name: str = "main"
    ai_name: str = "Guide"
    ai_trigger: str = "chat"
    llm_provider: str = "mock"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "llama3.2:3b"


settings = Settings()
