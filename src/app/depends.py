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
from services.NotionService import NotionService
from services.RAGService import RAGService
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
        template_path=os.path.join(get_root_path(), "src/templates/dashboard"),
        publish_services=_build_publish_services(),
        whisper_transcription_service=get_whisper_transcription_service(),
    )


def get_calendar_controller() -> CalendarController:
    return CalendarController(
        sqlite_db_repository=get_sqlite_db_repository(),
        template_path=os.path.join(get_root_path(), "src/templates/dashboard"),
        daily_recap_service=get_daily_recap_service(),
        ical_sync_service=ICalSyncService(),
    )


def get_proactor_controller() -> ProactorController:
    return ProactorController(
        sqlite_db_repository=get_sqlite_db_repository(),
        template_path=os.path.join(get_root_path(), "src/templates/dashboard"),
        proactor_service=ProactorService(),
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
        template_path=os.path.join(get_root_path(), "src/templates/knowledge"),
    )


def get_auth_service() -> AuthService:
    return AuthService(settings_path=os.path.join(get_root_path(), "settings"))

