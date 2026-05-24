from pydantic import BaseModel


class BulkImportPreviewRequestDTO(BaseModel):
    folder_path: str
    recursive: bool = False
    transcribe_audio: bool = False


class BulkImportConfirmRequestDTO(BaseModel):
    folder_path: str
    recursive: bool = False
    transcribe_audio: bool = False
    selected_paths: list[str] | None = None
