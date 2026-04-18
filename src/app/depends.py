import os

from dotenv import load_dotenv

from controllers.CalendarController import CalendarController
from controllers.DashboardController import DashboardController
from controllers.ProactorController import ProactorController
from controllers.RAGController import RAGController
from repositories.CostTrackingRepository import CostTrackingRepository
from repositories.LocalRecordingsRepository import LocalRecordingsRepository
from repositories.SqliteDBRepository import SqliteDBRepository
from repositories.SystemPromptsRepository import SystemPromptsRepository
from repositories.VectorStoreRepository import VectorStoreRepository
from services.DeepgramTranscriptionService import DeepgramTranscriptionService
from services.TranscriptionService import TranscriptionService
from services.ModelRegistry import ModelRegistry
from services.ObsidianExportService import ObsidianExportService
from services.RAGService import RAGService
from services.SummarizationService import SummarizationService
from services.TaskGenerationService import TaskGenerationService
from services.WhisperTranscriptionService import WhisperTranscriptionService
from services.DailyRecapService import DailyRecapService
from services.AuthService import AuthService
from services.ICalSyncService import ICalSyncService
from services.ProactorService import ProactorService

load_dotenv()

config = {}


def is_auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")


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


def get_deepgram_transcription_service() -> DeepgramTranscriptionService:
    _config = get_config()
    return DeepgramTranscriptionService(api_key=_config.get("DEEPGRAM_API_KEY", ""))


def get_transcription_service() -> TranscriptionService:
    _config = get_config()
    return TranscriptionService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_whisper_transcription_service() -> WhisperTranscriptionService:
    _config = get_config()
    return WhisperTranscriptionService(
        model_size=_config["WHISPER_MODEL_SIZE"],
        device=_config["WHISPER_DEVICE"],
        compute_type=_config["WHISPER_COMPUTE_TYPE"],
    )


def get_summarization_service() -> SummarizationService:
    _config = get_config()
    return SummarizationService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_task_generation_service() -> TaskGenerationService:
    _config = get_config()
    return TaskGenerationService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_system_prompts_repository() -> SystemPromptsRepository:
    return SystemPromptsRepository(prompts_path=os.path.join(get_root_path(), "system_prompts"))


def get_obsidian_export_service() -> ObsidianExportService:
    _config = get_config()
    vault_path = _config.get("OBSIDIAN_VAULT_PATH", "")
    return ObsidianExportService(vault_path=vault_path)


def get_cost_tracking_repository() -> CostTrackingRepository:
    _config = get_config()
    db_path = os.path.join(get_root_path(), "settings", _config["DATABASE_NAME"])
    return CostTrackingRepository(db_path=db_path)


def get_model_registry() -> ModelRegistry:
    _config = get_config()
    return ModelRegistry(
        deepgram_available=bool(_config.get("DEEPGRAM_API_KEY")),
        whisper_available=True,
        gemini_available=bool(_config.get("GEMINI_API_KEY")),
    )


def _build_publish_services() -> dict:
    """Build a dict of configured publish services (only includes services with valid config)."""
    services = {}
    obsidian = get_obsidian_export_service()
    if obsidian.is_configured:
        services["obsidian"] = obsidian
    return services


def get_daily_recap_service() -> DailyRecapService:
    _config = get_config()
    return DailyRecapService(api_key=_config["GEMINI_API_KEY"], model=_config["GEMINI_MODEL"])


def get_dashboard_controller() -> DashboardController:
    return DashboardController(
        sqlite_db_repository=get_sqlite_db_repository(),
        local_recordings_repository=get_local_recordings_repository(),
        deepgram_transcription_service=get_deepgram_transcription_service(),
        summarization_service=get_summarization_service(),
        task_generation_service=get_task_generation_service(),
        system_prompts_repository=get_system_prompts_repository(),
        template_path=get_template_path(),
        publish_services=_build_publish_services(),
        whisper_transcription_service=get_whisper_transcription_service(),
        gemini_transcription_service=get_transcription_service(),
        cost_tracking_repository=get_cost_tracking_repository(),
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


def get_vector_store_repository() -> VectorStoreRepository:
    _config = get_config()
    return VectorStoreRepository(
        persist_path=os.path.join(get_root_path(), "settings/vector_store"),
        api_key=_config["GEMINI_API_KEY"],
        model=_config["GEMINI_EMBEDDING_MODEL"],
    )


def get_rag_service() -> RAGService:
    _config = get_config()
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
