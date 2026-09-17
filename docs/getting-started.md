# Getting Started

This guide walks you through installing and running AgenDino.

---

## Requirements

- **Python 3.12+**
- A **Google Gemini API key** for transcription, summarization, RAG, and daily recaps
- *(Optional)* A **HiDock** device (H1, H1E, or P1) connected via USB
- *(Optional)* A **Notion API key** and parent page ID for publishing summaries

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/DStt/agendino.git
cd agendino
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

For development (includes `pytest`):

```bash
pip install -r requirements-dev.txt
```

### 4. USB permissions (Linux only)

To access HiDock devices without `sudo`, add a udev rule:

```bash
sudo tee /etc/udev/rules.d/99-hidock.rules <<EOF
SUBSYSTEM=="usb", ATTR{idVendor}=="10d6", MODE="0666"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## Configuration

Create a `.env` file in the project root:

```env
# Required for transcription/embeddings - Google Gemini API key
GEMINI_API_KEY=your-gemini-api-key

# Optional - Gemini model names (defaults shown)
GEMINI_MODEL=gemini-3.8-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-2

# Optional - DeepSeek for summaries, tasks, recaps and RAG answers
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Default AI provider for summaries and AI activities: gemini or deepseek
AI_PROVIDER=gemini

# Optional - Notion integration
NOTION_API_KEY=your-notion-integration-token
NOTION_PAGE_ID=your-notion-parent-page-id

# Optional - SQLite database name (default: agendino.db)
DATABASE_NAME=agendino.db

# Optional - Login authentication (enabled by default; first login creates the account)
AUTH_ENABLED=true

# Optional - Trust X-Forwarded-For / X-Real-IP (only behind a trusted reverse proxy)
TRUST_PROXY_HEADERS=false

# Optional - Local Whisper transcription settings
WHISPER_MODEL_SIZE=small          # tiny | base | small | medium | large-v3
WHISPER_DEVICE=cpu                # cpu | cuda
WHISPER_COMPUTE_TYPE=auto         # auto | int8 | float16 | float32
```

See [Authentication](authentication.md) for details on `AUTH_ENABLED`, [AI Providers](ai-providers.md) for Gemini/DeepSeek setup, and [Transcription](transcription.md) for Whisper settings.

## Running the Server

From the repository root (recommended):

```bash
fastapi dev run.py
```

or, equivalently, using the Makefile:

```bash
make dev
```

You can also run from `src/` directly:

```bash
cd src
fastapi dev main.py
```

The dashboard will be available at **http://127.0.0.1:8000**, and a liveness
check at **http://127.0.0.1:8000/health**.

### Docker

```bash
docker build -t agendino .
docker run --rm -p 8000:8000 --env-file .env agendino
```

Mount volumes for `settings/` and `local_recordings/` to persist data.

Interactive API docs (Swagger UI) are at **http://127.0.0.1:8000/docs**.

## Running Tests

```bash
pytest
```

---

**Next:** explore the features - start with [Recording Management](recording-management.md) or browse the full [Documentation Index](index.md).
