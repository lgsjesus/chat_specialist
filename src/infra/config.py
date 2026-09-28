from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_core import MultiHostUrl

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # Banco de Dados
    DB_HOST: str
    DB_NAME: str
    DB_PASS: str
    DB_PORT: int

    # Provedor padrão: "google" ou "openai"
    AI_PROVIDER: str = "google"

    # Configurações Google Gemini
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_CHAT_MODEL: str = "gemini-2.5-flash"
    GOOGLE_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Configurações OpenAI (opcional para fallback)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_CHAT_MODEL: str = "gpt-4.1-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    @property
    def URL_DB(self) -> str:
        return str(
            MultiHostUrl.build(
                scheme="postgresql+psycopg",
                username=self.DB_NAME,
                host=self.DB_HOST,
                port=self.DB_PORT,
                path=self.DB_NAME,
                password=self.DB_PASS,
            )
        )


settings = Settings()
