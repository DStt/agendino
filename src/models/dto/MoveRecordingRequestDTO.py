from pydantic import BaseModel


class MoveRecordingRequestDTO(BaseModel):
    folder: str


class BulkMoveRecordingsRequestDTO(BaseModel):
    names: list[str]
    folder: str
