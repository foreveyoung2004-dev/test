from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    aiai_api_key: str = os.getenv("AIAI_API_KEY", "").strip()
    aiai_base_url: str = os.getenv("AIAI_BASE_URL", "https://api.aiai.by/v1").strip()
    aiai_model: str = os.getenv("AIAI_MODEL", "gpt-oss-120b").strip()
    system_prompt: str = os.getenv(
        "SYSTEM_PROMPT",
        "Ты полезный ИИ-ассистент. Отвечай точно, понятно и по существу. "
        "Если не уверен — прямо говори об этом."
    ).strip()
    max_history_messages: int = _int("MAX_HISTORY_MESSAGES", 24)
    max_output_tokens: int = _int("MAX_OUTPUT_TOKENS", 2500)
    db_path: str = os.getenv("DB_PATH", "bot.db").strip()


settings = Settings()


def validate_settings() -> None:
    missing = []
    if not settings.telegram_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.aiai_api_key:
        missing.append("AIAI_API_KEY")
    if missing:
        raise RuntimeError(
            "Не заданы обязательные переменные окружения: " + ", ".join(missing)
        )
