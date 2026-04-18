from pydantic import BaseModel


class TranscribeRequestDTO(BaseModel):
    engine: str = "deepgram"  # "deepgram" or "whisper"
