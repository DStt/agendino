from pydantic import BaseModel


class MindMapRequestDTO(BaseModel):
    summary_ids: list[int] | None = None
    provider: str | None = None
