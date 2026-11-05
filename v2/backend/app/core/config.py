from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    app_name: str = '手机报价档案系统'
    environment: str = 'development'
    database_url: str = 'sqlite:///./data/quote.db'
    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=720, ge=5, le=10080)
    scrypt_n: int = 16384
    scrypt_r: int = 8
    scrypt_p: int = 1
    cors_origins: str = ''
    policy_evidence_dir: str = './data/policy-evidence'
    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(',') if x.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
