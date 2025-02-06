from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    JINA_API_KEY: str
    SEARCH_PROVIDER: str = "jina"
    STEP_SLEEP: int = 100

    class Config:
        env_file = ".env"

modelConfigs = {
    "evaluator": {
        "model": "deepseek-ai/DeepSeek-V3",
        "temperature": 0.1
    },
    "errorAnalyzer": {
        "model": "deepseek-ai/DeepSeek-V3",
        "temperature": 0.1
    },
    "queryRewriter": {
        "model": "deepseek-ai/DeepSeek-V3",
        "temperature": 0.7
    },
    "dedup": {
        "model": "deepseek-ai/DeepSeek-V3",
        "temperature": 0.1
    }
}

try:
    settings = Settings(_env_file=".env")
except Exception as e:
    settings = Settings()
