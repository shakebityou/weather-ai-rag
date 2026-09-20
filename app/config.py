from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600

    class Config:
        env_file = ".env"


settings = Settings()
