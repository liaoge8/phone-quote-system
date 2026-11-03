"""应用配置：从环境变量 / .env 文件读取（pydantic-settings）。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "手机报价管理系统"
    # 登录密码（单管理员模式），默认 8888 与前端演示密码一致
    ADMIN_PASSWORD: str = "8888"
    # JWT 签名密钥，生产环境必须更换
    SECRET_KEY: str = "change-me-in-production"
    # Token 有效期（分钟）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    # 数据库连接串：默认 SQLite；生产可切 PostgreSQL
    DATABASE_URL: str = "sqlite:///./data.db"

    # 大模型：OpenAI 兼容接口，默认 DeepSeek
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"


settings = Settings()
