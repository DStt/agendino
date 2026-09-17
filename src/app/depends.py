import logging
import os
from functools import lru_cache

from dotenv import load_dotenv

from controllers.CalendarController import CalendarController
from controllers.DashboardController import DashboardController
from controllers.ProactorController import ProactorController
from controllers.RAGController import RAGController
from repositories.LocalRecordingsRepository import LocalRecordingsRepository
from repositories.SqliteDBRepository import SqliteDBRepository
from repositories.SystemPromptsRepository import SystemPromptsRepository
from repositories.VectorStoreRepository import VectorStoreRepository
from services.AuthService import AuthService
from services.DailyRecapService import DailyRecapService
from services.DeepSeekService import (
    DeepSeekService,
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MAX_TOKENS,
    DEFAULT_DEEPSEEK_MODEL,
)
from services.ICalSyncService import ICalSyncService
from services.NotionService import NotionService
from services.ProactorService import ProactorService
from services.RAGService import RAGService
from services.SummarizationService import SummarizationService
from services.TaskGenerationService import TaskGenerationService
from services.TranscriptionService import TranscriptionService
from services.WhisperTranscriptionService import WhisperTranscriptionService

load_dotenv()

logger = logging.getLogger(__name__)

config = {}


def is_auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")


def get_config():
    if config.get("init", False):
        return config
    items = os.environ.items()
    for item in items:
        config[item[0]] = item[1]
    config["init"] = True
    return config


def validate_config() -> list[str]:
    """Log the effective configuration and return human-readable warnings.

    This is intentionally non-fatal: a missing Gemini key must not stop a
    DeepSeek-only deployment from starting (see the optional clients below).
    """
    cfg = get_config()
    gemini = bool(cfg.get("GEMINI_API_KEY"))
    deepseek = bool(cfg.get("DEEPSEEK_API_KEY"))
    provider = get_default_ai_provider()
    warnings: list[str] = []

    if not gemini and not deepseek:
        warnings.append("No AI provider configured: set GEMINI_API_KEY and/or DEEPSEEK_API_KEY.")
    if provider == "gemini" and not gemini:
        warnings.append("Default provider is 'gemini' but GEMINI_API_KEY is missing.")
    if provider == "deepseek" and not deepseek:
        warnings.append("Default provider is 'deepseek' but DEEPSEEK_API_KEY is missing.")
    if not gemini:
        warnings.append(
            "GEMINI_API_KEY is missing: transcription, embeddings and knowledge-base loading are disabled."
        )

    logger.info(
        "Configuration: provider=%s gemini=%s deepseek=%s auth_enabled=%s",
        provider,
        "configured" if gemini else "missing",
        "configured" if deepseek else "missing",
        is_auth_enabled(),
    )
    for warning in warnings:
        logger.warning("Configuration: %s", warning)
    return warnings


def get_root_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")


def get_template_path() -> str:
    return os.path.join(get_root_path(), "src/templates")


@lru_cache(maxsize=None)
def get_sqlite_db_repository() -> SqliteDBRepository:
    _config = get_config()
    return SqliteDBRepository(
        db_name=_config.get("DATABASE_NAME", "agendino.db"),
        db_path=os.path.join(get_root_path(), "settings"),
        init_sql_script=os.path.join(get_root_path(), "settings/db_init.sql"),
    )


@lru_cache(maxsize=None)
def get_local_recordings_repository() -> LocalRecordingsRepository:
    return LocalRecordingsRepository(local_recordings_path=os.path.join(get_root_path(), "local_recordings"))


def _deepseek_max_tokens_config() -> int:
    _config = get_config()
    try:
        return int(_config.get("DEEPSEEK_MAX_TOKENS", DEFAULT_DEEPSEEK_MAX_TOKENS))
    except (TypeError, ValueError):
        return DEFAULT_DEEPSEEK_MAX_TOKENS


def _deepseek_thinking_config() -> str | None:
    """Return "enabled"/"disabled", or None to use the API default (thinking on).

    Thinking mode is disabled by default because its hidden reasoning tokens share
    the max_tokens budget, which truncates long structured outputs.
    """
    _config = get_config()
    thinking = (_config.get("DEEPSEEK_THINKING") or "disabled").strip().lower()
    return thinking if thinking in ("enabled", "disabled") else None


def get_deepseek_service() -> DeepSeekService:
    _config = get_config()
    return DeepSeekService(
        api_key=_config.get("DEEPSEEK_API_KEY"),
        model=_config.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
        base_url=_config.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL),
        max_tokens=_deepseek_max_tokens_config(),
        thinking=_deepseek_thinking_config(),
    )


def get_default_ai_provider() -> str:
    _config = get_config()
    provider = _config.get("AI_PROVIDER", "").strip().lower()
    if provider in ("gemini", "deepseek"):
        return provider
    if _config.get("GEMINI_API_KEY"):
        return "gemini"
    if _config.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    return "gemini"


def get_ai_config() -> dict:
    """Describe the AI providers available to the UI (names, models, configured flag)."""
    _config = get_config()
    return {
        "ok": True,
        "default_provider": get_default_ai_provider(),
        "providers": [
            {
                "id": "gemini",
                "name": "Gemini AI",
                "model": _config.get("GEMINI_MODEL", "gemini-3.8-flash"),
                "configured": bool(_config.get("GEMINI_API_KEY")),
            },
            {
                "id": "deepseek",
                "name": "DeepSeek AI",
                "model": _config.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
                "configured": bool(_config.get("DEEPSEEK_API_KEY")),
            },
        ],
    }


def get_transcription_service() -> TranscriptionService:
    _config = get_config()
    return TranscriptionService(
        api_key=_config.get("GEMINI_API_KEY", ""),
        model=_config.get("GEMINI_MODEL", "gemini-3.8-flash"),
    )


@lru_cache(maxsize=None)
def get_whisper_transcription_service() -> WhisperTranscriptionService:
    _config = get_config()
    return WhisperTranscriptionService(
        model_size=_config.get("WHISPER_MODEL_SIZE", "small"),
        device=_config.get("WHISPER_DEVICE", "cpu"),
        compute_type=_config.get("WHISPER_COMPUTE_TYPE", "auto"),
    )


def get_summarization_service() -> SummarizationService:
    _config = get_config()
    return SummarizationService(
        api_key=_config.get("GEMINI_API_KEY"),
        model=_config.get("GEMINI_MODEL", "gemini-3.8-flash"),
        deepseek_service=get_deepseek_service(),
        default_provider=get_default_ai_provider(),
    )


def get_task_generation_service() -> TaskGenerationService:
    _config = get_config()
    return TaskGenerationService(
        api_key=_config.get("GEMINI_API_KEY"),
        model=_config.get("GEMINI_MODEL", "gemini-3.8-flash"),
        deepseek_service=get_deepseek_service(),
        default_provider=get_default_ai_provider(),
    )


@lru_cache(maxsize=None)
def get_system_prompts_repository() -> SystemPromptsRepository:
    return SystemPromptsRepository(prompts_path=os.path.join(get_root_path(), "system_prompts"))


@lru_cache(maxsize=None)
def get_notion_service() -> NotionService:
    _config = get_config()
    return NotionService(
        api_key=_config.get("NOTION_API_KEY", ""),
        parent_page_id=_config.get("NOTION_PAGE_ID", ""),
    )


def _build_publish_services() -> dict:
    """Build a dict of configured publish services (only includes services with valid config)."""
    services = {}
    notion = get_notion_service()
    if notion.is_configured:
        services["notion"] = notion
    return services


def get_daily_recap_service() -> DailyRecapService:
    _config = get_config()
    return DailyRecapService(
        api_key=_config.get("GEMINI_API_KEY"),
        model=_config.get("GEMINI_MODEL", "gemini-3.8-flash"),
        deepseek_service=get_deepseek_service(),
        default_provider=get_default_ai_provider(),
    )


def get_dashboard_controller() -> DashboardController:
    return DashboardController(
        sqlite_db_repository=get_sqlite_db_repository(),
        local_recordings_repository=get_local_recordings_repository(),
        transcription_service=get_transcription_service(),
        summarization_service=get_summarization_service(),
        task_generation_service=get_task_generation_service(),
        system_prompts_repository=get_system_prompts_repository(),
        template_path=get_template_path(),
        publish_services=_build_publish_services(),
        whisper_transcription_service=get_whisper_transcription_service(),
        auth_enabled=is_auth_enabled(),
        deepseek_service=get_deepseek_service(),
        default_ai_provider=get_default_ai_provider(),
    )


def get_calendar_controller() -> CalendarController:
    return CalendarController(
        sqlite_db_repository=get_sqlite_db_repository(),
        template_path=get_template_path(),
        daily_recap_service=get_daily_recap_service(),
        ical_sync_service=ICalSyncService(),
        auth_enabled=is_auth_enabled(),
        ai_config=get_ai_config(),
    )


def get_proactor_controller() -> ProactorController:
    return ProactorController(
        sqlite_db_repository=get_sqlite_db_repository(),
        template_path=get_template_path(),
        proactor_service=ProactorService(),
        auth_enabled=is_auth_enabled(),
    )


@lru_cache(maxsize=None)
def get_vector_store_repository() -> VectorStoreRepository:
    _config = get_config()
    return VectorStoreRepository(
        persist_path=os.path.join(get_root_path(), "settings/vector_store"),
        api_key=_config.get("GEMINI_API_KEY", ""),
        model=_config.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2"),
    )


def get_rag_service() -> RAGService:
    _config = get_config()
    return RAGService(
        api_key=_config.get("GEMINI_API_KEY"),
        model=_config.get("GEMINI_MODEL", "gemini-3.8-flash"),
        deepseek_service=get_deepseek_service(),
        default_provider=get_default_ai_provider(),
    )


def get_rag_controller() -> RAGController:
    return RAGController(
        sqlite_db_repository=get_sqlite_db_repository(),
        vector_store_repository=get_vector_store_repository(),
        rag_service=get_rag_service(),
        template_path=get_template_path(),
        auth_enabled=is_auth_enabled(),
        ai_config=get_ai_config(),
    )


def get_auth_service() -> AuthService:
    return AuthService(settings_path=os.path.join(get_root_path(), "settings"))
