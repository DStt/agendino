from dataclasses import dataclass


@dataclass
class EngineInfo:
    id: str
    name: str
    type: str        # 'transcription', 'summarization', 'both'
    available: bool


class ModelRegistry:
    def __init__(self, deepgram_available: bool, whisper_available: bool, gemini_available: bool):
        self._engines = [
            EngineInfo(id="deepgram", name="Deepgram Nova", type="transcription", available=deepgram_available),
            EngineInfo(id="whisper", name="Whisper (local)", type="transcription", available=whisper_available),
            EngineInfo(id="gemini", name="Gemini", type="both", available=gemini_available),
        ]

    def get_transcription_engines(self) -> list[EngineInfo]:
        return [e for e in self._engines if e.available and e.type in ("transcription", "both")]

    def get_summarization_engines(self) -> list[EngineInfo]:
        return [e for e in self._engines if e.available and e.type in ("summarization", "both")]

    def get_all_available(self) -> list[EngineInfo]:
        return [e for e in self._engines if e.available]

    def to_dict_list(self, engines: list[EngineInfo] | None = None) -> list[dict]:
        targets = engines or self.get_all_available()
        return [{"id": e.id, "name": e.name, "type": e.type} for e in targets]
