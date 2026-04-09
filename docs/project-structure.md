# Project Structure

Overview of the directory layout and module responsibilities.

---

```
agendino/
├── src/
│   ├── main.py                            # FastAPI app entrypoint
│   ├── app/
│   │   ├── router.py                      # Top-level router (API + web)
│   │   ├── depends.py                     # Dependency injection / configuration
│   │   ├── auth_middleware.py             # Session & IP-ban middleware
│   │   ├── api/endpoints/
│   │   │   ├── auth.py                    # Login / logout endpoints
│   │   │   ├── dashboard.py               # Recording management endpoints
│   │   │   ├── calendar.py                # Calendar & shared-calendar endpoints
│   │   │   ├── proactor.py                # Schedule analysis endpoints
│   │   │   └── knowledge.py               # RAG / mind-map endpoints
│   │   └── web/
│   │       ├── dashboard.py               # HTML pages (home, calendar, proactor)
│   │       ├── knowledge.py               # Knowledge base HTML page
│   │       └── login.py                   # Login HTML page
│   ├── controllers/
│   │   ├── DashboardController.py         # Recording, summary, task & folder logic
│   │   ├── CalendarController.py          # Calendar events, shared cals, daily recap
│   │   ├── ProactorController.py          # Proactive schedule analysis
│   │   └── RAGController.py               # Knowledge base & mind map
│   ├── models/
│   │   ├── DBRecording.py                 # Recording model
│   │   ├── DBSummary.py                   # Summary version model
│   │   ├── DBTask.py                      # Task / subtask model
│   │   ├── DBCalendarEvent.py             # Calendar event model
│   │   ├── DBSharedCalendar.py            # Shared calendar subscription model
│   │   ├── DBDailyRecap.py                # Daily recap model
│   │   └── dto/                           # Request DTOs (Pydantic models)
│   ├── repositories/
│   │   ├── LocalRecordingsRepository.py   # Local audio file management
│   │   ├── SqliteDBRepository.py          # SQLite database access
│   │   ├── SystemPromptsRepository.py     # System prompt file loader
│   │   └── VectorStoreRepository.py       # ChromaDB vector store wrapper
│   ├── services/
│   │   ├── AuthService.py                 # Authentication & session management
│   │   ├── TranscriptionService.py        # Gemini transcription
│   │   ├── WhisperTranscriptionService.py # Local Whisper transcription
│   │   ├── SummarizationService.py        # Gemini summarization
│   │   ├── TaskGenerationService.py       # Gemini task extraction
│   │   ├── DailyRecapService.py           # Gemini daily recap generation
│   │   ├── RAGService.py                  # RAG Q&A & mind map generation
│   │   ├── ICalSyncService.py             # iCal feed fetching & parsing
│   │   ├── ProactorService.py             # Schedule overlap/gap analysis
│   │   └── NotionService.py               # Notion API integration
│   ├── static/                            # CSS & JS assets
│   └── templates/                         # Jinja2 HTML templates
├── docs/                                  # Documentation (you are here)
├── settings/
│   ├── agendino.db                        # SQLite database
│   ├── db_init.sql                        # Database schema
│   └── vector_store/                      # ChromaDB persistent storage
├── local_recordings/                      # Synced & uploaded audio files
├── system_prompts/                        # Summarization prompt templates
├── tests/                                 # Unit & integration tests
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

## Layer Responsibilities

| Layer | Purpose |
|-------|---------|
| **`app/api/endpoints/`** | HTTP request handling - validation, response formatting |
| **`app/web/`** | Jinja2 template rendering for the web UI |
| **`controllers/`** | Business logic orchestration - coordinates services and repositories |
| **`services/`** | External integrations and AI logic - Gemini, Whisper, Notion, iCal |
| **`repositories/`** | Data access - SQLite, local files, ChromaDB, system prompts |
| **`models/`** | Data structures - database models and Pydantic DTOs |

---

**Related:** [Getting Started](getting-started.md) · [API Reference](api-reference.md)
