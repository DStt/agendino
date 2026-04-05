from pydantic import BaseModel


class TranscribeRequestDTO(BaseModel):
    engine: str = "gemini"  # "gemini" or "whisper"

