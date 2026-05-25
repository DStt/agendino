from pydantic import BaseModel


class CreateCollectionRequestDTO(BaseModel):
    name: str
    description: str | None = None


class SetRecordingCollectionsRequestDTO(BaseModel):
    collection_ids: list[int]
