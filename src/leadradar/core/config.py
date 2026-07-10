from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_key_1: str | None = None
    groq_key_2: str | None = None
    gemini_key_1: str | None = None
    gemini_key_2: str | None = None
    gemini_key_3: str | None = None
    openrouter_key_1: str | None = None
    google_places_key: str | None = None


settings = Settings()
