# AgenDino

[![Tests](https://github.com/DStt/agendino/actions/workflows/tests.yml/badge.svg)](https://github.com/DStt/agendino/actions/workflows/tests.yml)
[![Style](https://github.com/DStt/agendino/actions/workflows/style.yml/badge.svg)](https://github.com/DStt/agendino/actions/workflows/style.yml)

AgenDino is a web-based dashboard for managing, transcribing, and summarizing audio recordings from [HiDock](https://www.hidock.com/) USB devices. It connects directly to HiDock H1, H1E, and P1 devices over USB, syncs recordings locally, transcribes them using Google Gemini or locally with Whisper, generates structured AI summaries with customizable system prompts, and optionally publishes results to Notion.

## Features

- **HiDock USB Integration** - Detects and communicates with HiDock H1 / H1E / P1 devices over USB. List, download, and delete recordings directly from the device. View device info and storage usage.
- **Local Recording Management** - Sync recordings from the device to local storage. Upload audio files (`.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm`, `.flac`, `.aac`, `.wma`) directly from the browser. Browse, play back, and manage recordings from the web dashboard. Organize recordings into virtual folders with drag-and-drop and bulk move support.
- **AI Transcription** - Two transcription engines available:
  - **Gemini** - Cloud-based transcription with automatic speaker diarization, timestamps, and speaker labels.
  - **Whisper** (local, via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) - Offline transcription running entirely on your machine. Best for long recordings where Gemini may truncate the output.
- **AI Summarization** - Generate structured summaries (title, tags, and full markdown summary) from transcripts using Gemini. Choose from multiple system prompts organized by language and category (e.g. General, Meetings, IT & Engineering). Supports multiple summary versions per recording - re-summarize with a different prompt without losing previous results. Edit summary content, titles, and tags inline.
- **AI Task Generation** - Automatically extract actionable tasks (with subtasks) from meeting summaries using Gemini. Tasks are structured as Jira-style tickets with title and description. Track task status (open/done) and manage them per summary.
- **Calendar** - Built-in calendar view with manual event creation and editing. Link recordings to calendar events to associate meeting notes with scheduled meetings. View a full day detail panel showing events, recordings, and summaries for any date.
- **Shared Calendars (iCal Sync)** - Subscribe to external calendars via iCal URL (Google Calendar, Outlook, etc.). Auto-sync on a configurable interval with support for recurring events, all-day events, and event status. Validate iCal URLs before subscribing. Assign custom colors to each calendar.
- **AI Daily Recap** - Generate an AI-powered end-of-day recap from all calendar events and meeting summaries for a given date. Recaps include a title, key highlights, a full markdown narrative, action items, and blockers.
- **Proactive Schedule Analysis** - Analyze your calendar for scheduling issues across a date range: detect overlapping events, back-to-back meetings, free-slot gaps, and overloaded days. Includes visual day timelines with meeting blocks and free slots, plus an overall schedule health score (good / fair / poor).
- **Knowledge Base (RAG)** - Retrieval-Augmented Generation powered by ChromaDB and Gemini embeddings. Load summaries into a local vector store, then search or ask natural-language questions across all your meeting knowledge. Responses include source citations with links back to the original summaries. Filter queries to specific summaries.
- **AI Mind Map** - Visualize connections across summaries as an interactive mind map. Two modes: tag-based (instant, no AI call) and AI-generated (Gemini produces a hierarchical theme → insight → source structure with cross-cutting connections).
- **Notion Publishing** - Publish summaries as rich sub-pages under a Notion parent page, complete with metadata callouts, tags, and formatted markdown content. Publish individual summary versions. The Notion page URL is saved for quick access.
- **Authentication** - Optional single-user login system, disabled by default. On first login, the credentials you enter are stored as the permanent account (PBKDF2-SHA256 hashed). Cookie-based session management (7-day expiry) with automatic IP banning on failed login attempts. Enable via `AUTH_ENABLED=true` in `.env`.
- **Web Dashboard** - Multi-page web UI built with FastAPI, Jinja2 templates, and vanilla JavaScript. Includes dedicated pages for the recording dashboard, calendar, proactive analysis, and knowledge base.

## Requirements

- **Python 3.12+**
- A **HiDock** device (H1, H1E, or P1) connected via USB *(optional - local recordings can be managed without a device)*
- A **Google Gemini API key** for transcription and summarization
- *(Optional)* A **Notion API key** and parent page ID for publishing

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/DStt/agendino.git
   cd agendino
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux / macOS
   # .venv\Scripts\activate    # Windows
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   For development (includes `pytest`):

   ```bash
   pip install -r requirements-dev.txt
   ```

4. **USB permissions (Linux only):**

   To access HiDock devices without `sudo`, add a udev rule:

   ```bash
   sudo tee /etc/udev/rules.d/99-hidock.rules <<EOF
   SUBSYSTEM=="usb", ATTR{idVendor}=="10d6", MODE="0666"
   EOF
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# Required - Google Gemini API key for transcription, summarization, RAG & recap
GEMINI_API_KEY=your-gemini-api-key

# Optional - Gemini model names (defaults shown)
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=text-embedding-001

# Optional - Notion integration
NOTION_API_KEY=your-notion-integration-token
NOTION_PAGE_ID=your-notion-parent-page-id

# Optional - SQLite database name (default: agendino.db)
DATABASE_NAME=agendino.db

# Optional - Enable login authentication (default: false)
# When enabled, all routes require a valid session cookie.
# The first login creates the permanent account.
AUTH_ENABLED=false

# Optional - Local Whisper transcription settings
# Model size: tiny, base, small (default), medium, large-v3
WHISPER_MODEL_SIZE=small
# Device: cpu (default) or cuda (requires NVIDIA GPU + CUDA toolkit)
WHISPER_DEVICE=cpu
# Compute type: auto (default), int8, float16, float32
WHISPER_COMPUTE_TYPE=auto
```

## Getting Started

1. **Start the server:**

   ```bash
   cd src
   fastapi dev main.py
   ```

   The dashboard will be available at **http://127.0.0.1:8000**.

2. **Open the dashboard** in your browser and you will see the main page.

3. **Connect your HiDock** device via USB. The dashboard will detect it automatically when you interact with the device features.

## Usage

### Syncing Recordings

1. Connect your HiDock device via USB.
2. From the dashboard, click **Sync** to download new recordings from the device to local storage and register them in the database.
3. Recordings already present locally are skipped automatically.

### Transcribing a Recording

1. Select a recording that has been synced locally.
2. Click the **Transcribe** button (microphone icon) to transcribe with Gemini (default), or click the **dropdown arrow** next to it to choose between:
   - **Gemini** - Cloud-based, includes speaker diarization and labels. May truncate very long recordings.
   - **Whisper (local)** - Runs on your machine, no cloud upload. Handles long audio files without truncation. Requires downloading the model on first use (~500 MB for `small`).
3. The transcript is saved to the database and can be viewed or edited at any time.

### Summarizing a Recording

1. Make sure the recording has been transcribed first.
2. Click **Summarize** and choose a **system prompt** from the available categories (e.g. `Generale / SintesiAdattiva`, `IT&Engineering / ...`).
3. Gemini generates a structured JSON response containing a **title**, **tags**, and a **full markdown summary**.
4. The result is saved to the database. You can edit the title, tags, and summary content inline.
5. You can re-summarize the same recording with a different prompt - each summary is saved as a separate version.

### Generating Tasks

1. After summarizing a recording, click **Generate Tasks** on any summary version.
2. Gemini extracts actionable tasks structured as Jira-style tickets, each with a title and description.
3. Broad tasks are automatically broken into subtasks.
4. Track task status (open/done), edit task details, or delete tasks. Regenerating tasks replaces previous ones for that summary.

### Publishing to Notion

1. Ensure `NOTION_API_KEY` and `NOTION_PAGE_ID` are configured in your `.env` file.
2. After summarizing a recording, click **Publish** and select **Notion** as the destination.
3. A new sub-page is created under your configured Notion parent page with the summary content, tags, and recording metadata.
4. The Notion page URL is saved in the database for quick access.

### Uploading Audio Files

1. Click the **Upload** button on the dashboard.
2. Select any supported audio file (`.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm`, `.flac`, `.aac`, `.wma`).
3. The file is saved to local storage, a database record is created, and audio duration is automatically extracted via [mutagen](https://github.com/quodlibet/mutagen).
4. Uploaded files can be transcribed and summarized just like device recordings.

### Organizing with Folders

1. Recordings can be organized into virtual folders for better structure.
2. **Create** a folder, **rename** it, or **delete** it (recordings move back to root).
3. **Drag and drop** individual recordings or **bulk move** multiple selections into a folder.

### Calendar

1. Navigate to the **Calendar** page from the sidebar.
2. **Create events** manually with title, time range, description, location, and meeting URL.
3. **Link recordings** to calendar events to associate meeting notes with scheduled meetings.
4. Click any date to open a **day detail panel** showing all events, recordings, and summaries for that date.

### Shared Calendars (iCal Sync)

1. Open the shared calendars panel from the Calendar page.
2. **Add a calendar** by pasting an iCal URL (e.g. a Google Calendar secret address or Outlook ICS link).
3. The URL is validated before subscribing — helpful hints are shown if the URL points to a login page instead of calendar data.
4. Set a **sync interval** (default: 30 minutes) and assign a **custom color**.
5. Calendars auto-sync when the interval elapses, or click **Sync** to refresh manually.
6. Recurring events are expanded automatically (±3 months window). All-day events, event status (confirmed/tentative/cancelled), locations, and meeting URLs are preserved.

### Daily Recap

1. From the Calendar day detail panel, click **Generate Recap** for any date.
2. Gemini produces a structured recap from all events and meeting summaries for that day.
3. The recap includes a **title**, **key highlights**, a **full markdown narrative**, **action items**, and **blockers**.
4. Recaps are saved to the database and can be regenerated or deleted at any time.

### Proactive Schedule Analysis

1. Navigate to the **Proactor** page from the sidebar.
2. Select a **date range** and click **Analyze**.
3. The analysis runs entirely locally (no AI call) and detects:
   - **Overlapping events** — with overlap duration and severity (low / medium / high).
   - **Back-to-back meetings** — consecutive events with less than 5 minutes between them.
   - **Free-slot gaps** — classified as short, available, or idle windows.
   - **Overloaded days** — days with more than 6 hours of meetings.
4. View **visual day timelines** showing meeting blocks and free slots with percentage-based widths.
5. An overall **schedule health score** (good / fair / poor) is calculated from the total issue count.

### Knowledge Base (RAG)

1. Navigate to the **Knowledge** page from the sidebar.
2. Click **Load Summaries** to index all your summaries into the ChromaDB vector store using Gemini embeddings.
3. Use **Search** to find semantically similar content across all indexed summaries.
4. Use **Ask** to pose natural-language questions — Gemini answers based on retrieved context, with source citations linking back to the original summaries.
5. Optionally filter queries to specific summaries using the summary picker.
6. Click **Clear** to reset the vector store and re-index from scratch.

### AI Mind Map

1. From the Knowledge page, open the **Mind Map** panel.
2. **Tag-based mode** (default) — instantly generates a graph from summary tags, no AI call needed. Summary nodes connect to shared tag nodes.
3. **AI-generated mode** — Gemini analyzes all summaries and produces a hierarchical map with a central topic, 3–7 thematic branches, key insights as leaves (with source summary IDs), and cross-cutting connections.

### Authentication

Authentication is **disabled by default**. To enable it, set `AUTH_ENABLED=true` in your `.env` file.

When enabled:

1. All routes (except `/login` and static assets) require a valid session.
2. Unauthenticated browser requests are redirected to the **login page**; API requests receive a `401` response.
3. **First login** — the very first username and password you submit become the permanent account. Credentials are hashed with PBKDF2-SHA256 (200 000 iterations) and stored in `settings/auth.json`.
4. **Subsequent logins** — credentials are verified against the stored hash. On success a session cookie (`agendino_session`) is issued, valid for **7 days**.
5. **Failed login** — the client's IP address is **permanently banned** and all future requests from that IP are blocked with `403 Forbidden`. To unban an IP, edit or delete `settings/banned_ips.json`.
6. **Logout** — destroys the session server-side and clears the cookie.

> **Tip:** Since the first login creates the account, make sure you set your desired username and password carefully — there is no built-in password reset. To start over, delete `settings/auth.json`.

### Deleting Recordings

You can selectively delete a recording from:
- **Local storage**
- The **database**

Each target is independent — you can, for example, delete the local file while keeping the database record.

### Custom System Prompts

System prompts are stored as `.txt` files under the `system_prompts/` directory, organized by language and category:

```
system_prompts/
  it/
    Generale/
      SintesiAdattiva.txt
      TLDRDirigenziale.txt
      DecisioniERischi.txt
    Riunione/
      SintesiOperativa.txt
      ActionTracker.txt
      RecapCliente.txt
    Istruzione/
      ...
    IT&Engineering/
      VerbaleIT.txt
      PostMortemLeggero.txt
      ...
```

To add a new prompt, create a `.txt` file in the appropriate category folder. It will appear automatically in the prompt selection dropdown.

Recommended prompt-writing guidelines:
- Keep prompts focused on one clear outcome (e.g. executive recap, action tracker, risk register).
- Define a strict output structure (sections and, when useful, table columns).
- Add anti-hallucination constraints (`use only transcript evidence`, `non specificato` for missing fields).
- Prefer concise, actionable language over generic prose.

## API Endpoints

### Dashboard — `/api/dashboard`

| Method   | Endpoint                                | Description                            |
|----------|-----------------------------------------|----------------------------------------|
| `GET`    | `/api/dashboard/recordings`             | List all recordings with status        |
| `POST`   | `/api/dashboard/upload`                 | Upload an audio file                   |
| `GET`    | `/api/dashboard/audio/{name}`           | Stream/download an audio file          |
| `POST`   | `/api/dashboard/transcribe/{name}`      | Transcribe a recording                 |
| `GET`    | `/api/dashboard/transcript/{name}`      | Get stored transcript                  |
| `PATCH`  | `/api/dashboard/transcript/{name}`      | Edit stored transcript                 |
| `GET`    | `/api/dashboard/prompts`                | List available system prompts          |
| `POST`   | `/api/dashboard/summarize/{name}`       | Summarize a recording                  |
| `GET`    | `/api/dashboard/summaries/{name}`       | Get all summaries for a recording      |
| `PATCH`  | `/api/dashboard/summary/{summary_id}`   | Update summary title, tags, or content |
| `PATCH`  | `/api/dashboard/recording/{name}`       | Update recording datetime              |
| `DELETE` | `/api/dashboard/recording/{name}`       | Delete recording (local/db)            |
| `GET`    | `/api/dashboard/share/destinations`     | List configured publish targets        |
| `POST`   | `/api/dashboard/share/summary/{id}`     | Publish a summary version              |
| `POST`   | `/api/dashboard/tasks/generate`         | Generate tasks from a summary          |
| `GET`    | `/api/dashboard/tasks/{summary_id}`     | Get tasks for a summary                |
| `PATCH`  | `/api/dashboard/tasks/{task_id}`        | Update a task                          |
| `DELETE` | `/api/dashboard/tasks/{task_id}`        | Delete a task                          |
| `GET`    | `/api/dashboard/folders`                | List recording folders                 |
| `POST`   | `/api/dashboard/folders`                | Create a folder                        |
| `PATCH`  | `/api/dashboard/folders/rename`         | Rename a folder                        |
| `DELETE` | `/api/dashboard/folders`                | Delete a folder                        |
| `PATCH`  | `/api/dashboard/recording/{name}/move`  | Move a recording to a folder           |
| `PATCH`  | `/api/dashboard/recordings/move`        | Bulk move recordings                   |

### Calendar — `/api/calendar`

| Method   | Endpoint                                | Description                            |
|----------|-----------------------------------------|----------------------------------------|
| `GET`    | `/api/calendar/month/{year}/{month}`    | Get events for a month                 |
| `GET`    | `/api/calendar/day/{date}`              | Get events for a day                   |
| `GET`    | `/api/calendar/day-detail/{date}`       | Full day detail (events + recordings + summaries + recap) |
| `POST`   | `/api/calendar/events`                  | Create a calendar event                |
| `PATCH`  | `/api/calendar/events/{event_id}`       | Update a calendar event                |
| `DELETE` | `/api/calendar/events/{event_id}`       | Delete a calendar event                |
| `POST`   | `/api/calendar/link`                    | Link a recording to an event           |
| `DELETE` | `/api/calendar/link`                    | Unlink a recording from an event       |
| `POST`   | `/api/calendar/recap/{date}`            | Generate daily recap                   |
| `GET`    | `/api/calendar/recap/{date}`            | Get stored daily recap                 |
| `DELETE` | `/api/calendar/recap/{date}`            | Delete daily recap                     |
| `GET`    | `/api/calendar/shared`                  | List shared calendars                  |
| `POST`   | `/api/calendar/shared`                  | Subscribe to a shared calendar         |
| `POST`   | `/api/calendar/shared/sync-all`         | Sync all shared calendars              |
| `POST`   | `/api/calendar/shared/validate`         | Validate an iCal URL                   |
| `PATCH`  | `/api/calendar/shared/{calendar_id}`    | Update a shared calendar               |
| `DELETE` | `/api/calendar/shared/{calendar_id}`    | Delete a shared calendar               |
| `POST`   | `/api/calendar/shared/{calendar_id}/sync` | Sync a single shared calendar        |

### Proactor — `/api/proactor`

| Method   | Endpoint                                | Description                            |
|----------|-----------------------------------------|----------------------------------------|
| `GET`    | `/api/proactor/analyze?start=...&end=...` | Analyze schedule for a date range    |
| `POST`   | `/api/proactor/analyze`                 | Analyze schedule (POST variant)        |

### Knowledge Base — `/api/knowledge`

| Method   | Endpoint                                | Description                            |
|----------|-----------------------------------------|----------------------------------------|
| `GET`    | `/api/knowledge/stats`                  | Get vector store stats                 |
| `GET`    | `/api/knowledge/summaries`              | List available summaries for the picker |
| `POST`   | `/api/knowledge/load`                   | Load summaries into vector store       |
| `POST`   | `/api/knowledge/search`                 | Semantic search across summaries       |
| `POST`   | `/api/knowledge/ask`                    | RAG question answering                 |
| `POST`   | `/api/knowledge/mindmap`                | Generate tag-based mind map            |
| `POST`   | `/api/knowledge/mindmap/generate`       | Generate AI-powered mind map           |
| `POST`   | `/api/knowledge/clear`                  | Clear the vector store                 |

### Auth — `/api/auth`

| Method   | Endpoint                                | Description                            |
|----------|-----------------------------------------|----------------------------------------|
| `POST`   | `/api/auth/login`                       | Authenticate and create session        |
| `POST`   | `/api/auth/logout`                      | Destroy session and clear cookie       |

Interactive API docs are available at **http://127.0.0.1:8000/docs** (Swagger UI).

## Project Structure

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

## Running Tests

```bash
pytest
```

## License

This project is for personal use.
