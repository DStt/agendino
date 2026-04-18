from dataclasses import dataclass


@dataclass
class CostMetadata:
    operation: str      # transcription, summarization, task_generation, daily_recap, rag_query, embedding, comparison
    engine: str         # deepgram, whisper, gemini
    model: str          # specific model identifier
    input_units: float  # audio minutes (transcription) or input tokens (LLM)
    output_units: float # output tokens (0 for transcription)
    cost_usd: float
