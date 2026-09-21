from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600

    # 熔断器配置
    cb_failure_threshold: int = 3      # 连续失败多少次后熔断
    cb_recovery_timeout: float = 30.0  # 熔断后多少秒进入半开探测

    # SQL Server 配置（Windows 身份验证）
    mssql_server: str = "localhost"
    mssql_port: int = 1433
    mssql_driver: str = "ODBC Driver 17 for SQL Server"
    mssql_db: str = "rag_demo"
    # 留空则用 Windows 身份验证（Trusted_Connection）
    mssql_user: str = ""
    mssql_password: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
