# Agendino

Agendino is a web-based dashboard for managing, transcribing, and summarizing audio recordings from [HiDock](https://www.hidock.com/) USB devices. It connects directly to HiDock H1, H1E, and P1 devices over USB, syncs recordings locally, transcribes them using Google Gemini or locally with Whisper, generates structured AI summaries with customizable system prompts, and optionally publishes results to Notion.

## Features

- **HiDock USB Integration** — Detects and communicates with HiDock H1 / H1E / P1 devices over USB. List, download, and delete recordings directly from the device. View device info and storage usage.
- **Local Recording Management** — Sync recordings from the device to local storage. Browse, play back, and manage `.hda` audio files from the web dashboard.
- **AI Transcription** — Two transcription engines available:
  - **Gemini** (`gemini-2.5-flash`) — Cloud-based transcription with automatic speaker diarization, timestamps, and speaker labels.
  - **Whisper** (local, via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) — Offline transcription running entirely on your machine. Best for long recordings where Gemini may truncate the output.
- **AI Summarization** — Generate structured summaries (title, tags, and full markdown summary) from transcripts using Gemini. Choose from multiple system prompts organized by language and category (e.g. General, Meetings, Education, IT & Engineering).
- **Notion Publishing** — Publish summaries as rich sub-pages under a Notion parent page, complete with metadata callouts, tags, and formatted markdown content.
- **Recording Metadata** — Edit titles and tags for any recording. Track transcription and summarization status across device, local, and database records.
- **Web Dashboard** — Single-page web UI built with FastAPI, Jinja2 templates, and vanilla JavaScript.

## Requirements

- **Python 3.12+**
- A **HiDock** device (H1, H1E, or P1) connected via USB *(optional — local recordings can be managed without a device)*
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
# Required — Google Gemini API key for transcription & summarization
GEMINI_API_KEY=your-gemini-api-key

# Optional — Notion integration
NOTION_API_KEY=your-notion-integration-token
NOTION_PAGE_ID=your-notion-parent-page-id

# Optional — SQLite database name (default: agendino.db)
DATABASE_NAME=agendino.db

# Optional — Local Whisper transcription settings
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
   - **Gemini** — Cloud-based, includes speaker diarization and labels. May truncate very long recordings.
   - **Whisper (local)** — Runs on your machine, no cloud upload. Handles long audio files without truncation. Requires downloading the model on first use (~500 MB for `small`).
3. The transcript is saved to the database and can be viewed or edited at any time.

### Summarizing a Recording

1. Make sure the recording has been transcribed first.
2. Click **Summarize** and choose a **system prompt** from the available categories (e.g. `Generale / SintesiAdattiva`, `IT&Engineering / ...`).
3. Gemini generates a structured JSON response containing a **title**, **tags**, and a **full markdown summary**.
4. The result is saved to the database. You can edit the title and tags afterwards.

### Publishing to Notion

1. Ensure `NOTION_API_KEY` and `NOTION_PAGE_ID` are configured in your `.env` file.
2. After summarizing a recording, click **Publish** and select **Notion** as the destination.
3. A new sub-page is created under your configured Notion parent page with the summary content, tags, and recording metadata.
4. The Notion page URL is saved in the database for quick access.

### Deleting Recordings

You can selectively delete a recording from:
- The **HiDock device**
- **Local storage**
- The **database**

Each target is independent — you can, for example, delete from the device while keeping the local file and database record.

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

All API routes are served under `/api/dashboard`:

| Method   | Endpoint                        | Description                          |
|----------|---------------------------------|--------------------------------------|
| `GET`    | `/api/dashboard/recordings`     | List all recordings with status      |
| `POST`   | `/api/dashboard/sync`           | Sync recordings from device          |
| `GET`    | `/api/dashboard/audio/{name}`   | Stream/download an audio file        |
| `POST`   | `/api/dashboard/transcribe/{name}` | Transcribe a recording            |
| `GET`    | `/api/dashboard/transcript/{name}` | Get stored transcript              |
| `GET`    | `/api/dashboard/prompts`        | List available system prompts        |
| `POST`   | `/api/dashboard/summarize/{name}` | Summarize a recording              |
| `GET`    | `/api/dashboard/summary/{name}` | Get stored summary                   |
| `PATCH`  | `/api/dashboard/recording/{name}` | Update title and tags              |
| `DELETE` | `/api/dashboard/recording/{name}` | Delete recording (device/local/db) |
| `GET`    | `/api/dashboard/share/destinations` | List configured publish targets  |
| `POST`   | `/api/dashboard/share/{name}`   | Publish summary to a destination     |

Interactive API docs are available at **http://127.0.0.1:8000/docs** (Swagger UI).

## Project Structure

```
agendino/
├── src/
│   ├── main.py                          # FastAPI app entrypoint
│   ├── app/
│   │   ├── router.py                    # Top-level router (API + web)
│   │   ├── depends.py                   # Dependency injection / configuration
│   │   ├── api/endpoints/dashboard.py   # REST API endpoints
│   │   └── web/dashboard.py             # HTML dashboard route
│   ├── controllers/
│   │   └── DashboardController.py       # Core business logic
│   ├── models/
│   │   ├── DBRecording.py               # Database recording model
│   │   ├── HiDockDevice.py              # USB device communication
│   │   ├── HiDockDeviceInfo.py          # Device info model
│   │   ├── HiDockDevicePacket.py        # USB packet protocol
│   │   └── HiDockRecording.py           # Device recording model
│   ├── repositories/
│   │   ├── LocalRecordingsRepository.py # Local .hda file management
│   │   ├── SqliteDBRepository.py        # SQLite database access
│   │   └── SystemPromptsRepository.py   # System prompt file loader
│   ├── services/
│   │   ├── HiDockDeviceService.py       # Device discovery
│   │   ├── TranscriptionService.py      # Gemini transcription
│   │   ├── WhisperTranscriptionService.py # Local Whisper transcription
│   │   ├── SummarizationService.py      # Gemini summarization
│   │   └── NotionService.py             # Notion API integration
│   ├── static/                          # CSS & JS assets
│   └── templates/                       # Jinja2 HTML templates
├── settings/
│   ├── agendino.db                     # SQLite database
│   └── db_init.sql                      # Database schema
├── local_recordings/                    # Synced .hda audio files
├── system_prompts/                      # Summarization prompt templates
├── tests/                               # Unit & integration tests
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
