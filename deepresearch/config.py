from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    OPENAI_MODEL: str  # 添加默认模型设置
    OPENAI_BASE_URL: str
    JINA_API_KEY: str
    SEARCH_PROVIDER: str = "jina"
    STEP_SLEEP: int = 100

    class Config:
        env_file = ".env"

try:
    settings = Settings(_env_file=".env")
except Exception as e:
    settings = Settings()

modelConfigs = {
    "evaluator": {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.1
    },
    "errorAnalyzer": {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.1
    },
    "queryRewriter": {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.7
    },
    "dedup": {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.1
    }
}
