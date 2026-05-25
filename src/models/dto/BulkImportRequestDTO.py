from pydantic import BaseModel


class BulkImportPreviewRequestDTO(BaseModel):
    folder_path: str
    recursive: bool = False


class BulkImportConfirmRequestDTO(BaseModel):
    folder_path: str
    recursive: bool = False
    selected_pair_ids: list[str] | None = None
