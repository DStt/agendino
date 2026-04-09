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
# Required - Google Gemini API key
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
AUTH_ENABLED=false

# Optional - Local Whisper transcription settings
WHISPER_MODEL_SIZE=small          # tiny | base | small | medium | large-v3
WHISPER_DEVICE=cpu                # cpu | cuda
WHISPER_COMPUTE_TYPE=auto         # auto | int8 | float16 | float32
```

See [Authentication](authentication.md) for details on `AUTH_ENABLED` and [Transcription](transcription.md) for Whisper settings.

## Running the Server

```bash
cd src
fastapi dev main.py
```

The dashboard will be available at **http://127.0.0.1:8000**.

Interactive API docs (Swagger UI) are at **http://127.0.0.1:8000/docs**.

## Running Tests

```bash
pytest
```

---

**Next:** explore the features - start with [Recording Management](recording-management.md) or browse the full [Documentation Index](index.md).
