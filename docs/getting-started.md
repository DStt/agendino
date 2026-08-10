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

Copy the example env file and fill it in — at minimum set `GEMINI_API_KEY`:

```bash
cp .env.example .env
```

Every variable (Gemini, summarization provider, Whisper, Notion, auth, deployment/tuning) is
documented in `.env.example`. For a local (non-Docker) run, set `WHISPER_DEVICE=cuda` there to
use a GPU. See [Authentication](authentication.md) for `AUTH_ENABLED` and
[Transcription](transcription.md) for Whisper settings.

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
