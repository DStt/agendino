# Docker Deployment

This guide walks you through deploying AgenDino using Docker Compose.

---

## Requirements

- **Docker** and **Docker Compose** or **Docker Desktop** installed on your system.
- A **Google Gemini API key** for transcription, summarization, RAG, and daily recaps.
- _(Optional)_ A **Notion API key** and parent page ID for publishing summaries.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/DStt/agendino.git
cd agendino
```

## Configuration

Before running, update the `compose.yaml` file with your specific values:

- Replace `{local-dir-here}` with absolute or relative paths to local directories on your host machine:
  - For recordings: e.g., `/path/to/your/recordings`
  - For settings: e.g., `/path/to/your/settings`
  - For Traefik certificates: e.g., `/path/to/your/certs`

- Replace `{internal-ip-here}` with your server's internal IP address or domain name (e.g., `192.168.1.100` or `agendino.local`).

Create a `.env` file in the project root (same as in local setup):

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

## Running the Deployment

```bash
docker compose up -d
```

This starts the services in detached mode. AgenDino will be accessible via Traefik at the configured host (e.g., `https://{internal-ip-here}`), and the Traefik dashboard at `https://{internal-ip-here}/traefik/dashboard/`.

To view logs:

```bash
docker compose logs -f
```

To stop:

```bash
docker compose down
```

---

**Next:** explore the features - start with [Recording Management](recording-management.md) or browse the full [Documentation Index](index.md).
