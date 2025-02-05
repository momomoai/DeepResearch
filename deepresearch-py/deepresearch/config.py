from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    JINA_API_KEY: str
    BRAVE_API_KEY: str
    GOOGLE_API_KEY: str
    SEARCH_PROVIDER: str = "jina"
    STEP_SLEEP: int = 1000

    class Config:
        env_file = ".env"

modelConfigs = {
    "evaluator": {
        "model": "gemini-pro",
        "temperature": 0.1
    },
    "errorAnalyzer": {
        "model": "gemini-pro",
        "temperature": 0.1
    },
    "queryRewriter": {
        "model": "gemini-pro",
        "temperature": 0.7
    },
    "dedup": {
        "model": "gemini-pro",
        "temperature": 0.1
    }
}

settings = Settings()
