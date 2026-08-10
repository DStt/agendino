import os

from dotenv import load_dotenv

from controllers.CalendarController import CalendarController
from controllers.DashboardController import DashboardController
from controllers.ProactorController import ProactorController
from controllers.RAGController import RAGController
from repositories.LocalRecordingsRepository import LocalRecordingsRepository
from repositories.SqliteDBRepository import SqliteDBRepository
from repositories.SystemPromptsRepository import SystemPromptsRepository
from repositories.VectorStoreRepository import VectorStoreRepository
from repositories.embedders import GeminiEmbedder, LocalEmbedder, OllamaEmbedder
from services.ClaudeSummarizationService import ClaudeSummarizationService
from services.NotionService import NotionService
from services.RAGService import OllamaRAGService, RAGService
from services.SummarizationService import SummarizationService
from services.TaskGenerationService import TaskGenerationService
from services.TranscriptionService import TranscriptionService
from services.WhisperTranscriptionService import WhisperTranscriptionService
from services.DailyRecapService import DailyRecapService
from services.AuthService import AuthService
from services.ICalSyncService import ICalSyncService
from services.ProactorService import ProactorService

load_dotenv()

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


def get_root_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")


def get_template_path() -> str:
    return os.path.join(get_root_path(), "src/templates")


def get_sqlite_db_repository() -> SqliteDBRepository:
    _config = get_config()
    return SqliteDBRepository(
        db_name=_config["DATABASE_NAME"],
        db_path=os.path.join(get_root_path(), "settings"),
        init_sql_script=os.path.join(get_root_path(), "settings/db_init.sql"),
    )


def get_local_recordings_repository() -> LocalRecordingsRepository:
    return LocalRecordingsRepository(local_recordings_path=os.path.join(get_root_path(), "local_recordings"))


def get_transcription_service() -> TranscriptionService:
    _config = get_config()
    # Optional per-task override; falls back to the shared GEMINI_MODEL.
    model = _config.get("GEMINI_TRANSCRIPTION_MODEL") or _config["GEMINI_MODEL"]
    return TranscriptionService(api_key=_config["GEMINI_API_KEY"], model=model)


def get_whisper_transcription_service() -> WhisperTranscriptionService:
    _config = get_config()
    return WhisperTranscriptionService(
        model_size=_config.get("WHISPER_MODEL_SIZE", "small"),
        device=_config.get("WHISPER_DEVICE", "auto"),
        compute_type=_config.get("WHISPER_COMPUTE_TYPE", "auto"),
    )


def get_summarization_service():
    """Return the configured summarization service (Gemini by default, or Claude).

    Transcription is unaffected — Claude has no audio input, so it is summarization-only.
    """
    _config = get_config()
    provider = _config.get("SUMMARIZATION_PROVIDER", "gemini").lower()
    if provider == "claude":
        api_key = _config.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "SUMMARIZATION_PROVIDER=claude requires ANTHROPIC_API_KEY to be set"
            )
        return ClaudeSummarizationService(
            api_key=api_key,
            model=_config.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        )
    return SummarizationService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_task_generation_service() -> TaskGenerationService:
    _config = get_config()
    return TaskGenerationService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_system_prompts_repository() -> SystemPromptsRepository:
    return SystemPromptsRepository(prompts_path=os.path.join(get_root_path(), "system_prompts"))


def get_notion_service() -> NotionService:
    _config = get_config()
    return NotionService(
        api_key=_config["NOTION_API_KEY"],
        parent_page_id=_config["NOTION_PAGE_ID"],
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
    return DailyRecapService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


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
        vector_store_repository=get_vector_store_repository(),
        auth_enabled=is_auth_enabled(),
    )


def get_calendar_controller() -> CalendarController:
    return CalendarController(
        sqlite_db_repository=get_sqlite_db_repository(),
        template_path=get_template_path(),
        daily_recap_service=get_daily_recap_service(),
        ical_sync_service=ICalSyncService(),
        auth_enabled=is_auth_enabled(),
    )


def get_proactor_controller() -> ProactorController:
    return ProactorController(
        sqlite_db_repository=get_sqlite_db_repository(),
        template_path=get_template_path(),
        proactor_service=ProactorService(),
        auth_enabled=is_auth_enabled(),
    )


# Cache the embedder (a local model must not reload per request); do NOT cache the vector store —
# a cached collection handle goes stale across the mismatch reset's delete/recreate.
_embedder = None


def get_embedder():
    """Return the configured embedder (Gemini cloud by default, or a local sentence-transformers model)."""
    global _embedder
    if _embedder is None:
        _config = get_config()
        provider = _config.get("EMBEDDING_PROVIDER", "gemini").lower()
        if provider == "ollama":
            _embedder = OllamaEmbedder(
                base_url=_config.get("OLLAMA_BASE_URL", "http://localhost:11434"),
                model=_config.get("OLLAMA_EMBEDDING_MODEL", "bge-m3"),
            )
        elif provider == "local":
            _embedder = LocalEmbedder(
                model_name=_config.get("LOCAL_EMBEDDING_MODEL", "BAAI/bge-m3"),
                device=_config.get("LOCAL_EMBEDDING_DEVICE", "auto"),
            )
        else:
            _embedder = GeminiEmbedder(
                api_key=_config["GEMINI_API_KEY"],
                model=_config["GEMINI_EMBEDDING_MODEL"],
            )
    return _embedder


def get_vector_store_repository() -> VectorStoreRepository:
    return VectorStoreRepository(
        persist_path=os.path.join(get_root_path(), "settings/vector_store"),
        embedder=get_embedder(),
    )


def get_rag_service():
    """RAG generation service. `ollama`/`local` are synonyms (Ollama); unset follows EMBEDDING_PROVIDER."""
    _config = get_config()
    embedding_provider = _config.get("EMBEDDING_PROVIDER", "gemini").lower()
    default_provider = "ollama" if embedding_provider == "ollama" else "gemini"
    provider = (_config.get("RAG_PROVIDER") or default_provider).lower()
    if provider in ("ollama", "local"):
        return OllamaRAGService(
            base_url=_config.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=_config.get("OLLAMA_MODEL", "qwen2.5:7b"),
        )
    return RAGService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_rag_controller() -> RAGController:
    return RAGController(
        sqlite_db_repository=get_sqlite_db_repository(),
        vector_store_repository=get_vector_store_repository(),
        rag_service=get_rag_service(),
        template_path=get_template_path(),
        auth_enabled=is_auth_enabled(),
    )


def get_auth_service() -> AuthService:
    return AuthService(settings_path=os.path.join(get_root_path(), "settings"))
