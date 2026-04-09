# API Reference

Full list of REST endpoints. Interactive Swagger UI is available at `http://127.0.0.1:8000/docs`.

---

## Dashboard - `/api/dashboard`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard/recordings` | List all recordings with status |
| `POST` | `/api/dashboard/upload` | Upload an audio file |
| `GET` | `/api/dashboard/audio/{name}` | Stream/download an audio file |
| `POST` | `/api/dashboard/transcribe/{name}` | Transcribe a recording |
| `GET` | `/api/dashboard/transcript/{name}` | Get stored transcript |
| `PATCH` | `/api/dashboard/transcript/{name}` | Edit stored transcript |
| `GET` | `/api/dashboard/prompts` | List available system prompts |
| `POST` | `/api/dashboard/summarize/{name}` | Summarize a recording |
| `GET` | `/api/dashboard/summaries/{name}` | Get all summaries for a recording |
| `PATCH` | `/api/dashboard/summary/{summary_id}` | Update summary title, tags, or content |
| `PATCH` | `/api/dashboard/recording/{name}` | Update recording datetime |
| `DELETE` | `/api/dashboard/recording/{name}` | Delete recording (local/db) |
| `GET` | `/api/dashboard/share/destinations` | List configured publish targets |
| `POST` | `/api/dashboard/share/summary/{id}` | Publish a summary version |
| `POST` | `/api/dashboard/tasks/generate` | Generate tasks from a summary |
| `GET` | `/api/dashboard/tasks/{summary_id}` | Get tasks for a summary |
| `PATCH` | `/api/dashboard/tasks/{task_id}` | Update a task |
| `DELETE` | `/api/dashboard/tasks/{task_id}` | Delete a task |
| `GET` | `/api/dashboard/folders` | List recording folders |
| `POST` | `/api/dashboard/folders` | Create a folder |
| `PATCH` | `/api/dashboard/folders/rename` | Rename a folder |
| `DELETE` | `/api/dashboard/folders` | Delete a folder |
| `PATCH` | `/api/dashboard/recording/{name}/move` | Move a recording to a folder |
| `PATCH` | `/api/dashboard/recordings/move` | Bulk move recordings |

## Calendar - `/api/calendar`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/calendar/month/{year}/{month}` | Get events for a month |
| `GET` | `/api/calendar/day/{date}` | Get events for a day |
| `GET` | `/api/calendar/day-detail/{date}` | Full day detail (events + recordings + summaries + recap) |
| `POST` | `/api/calendar/events` | Create a calendar event |
| `PATCH` | `/api/calendar/events/{event_id}` | Update a calendar event |
| `DELETE` | `/api/calendar/events/{event_id}` | Delete a calendar event |
| `POST` | `/api/calendar/link` | Link a recording to an event |
| `DELETE` | `/api/calendar/link` | Unlink a recording from an event |
| `POST` | `/api/calendar/recap/{date}` | Generate daily recap |
| `GET` | `/api/calendar/recap/{date}` | Get stored daily recap |
| `DELETE` | `/api/calendar/recap/{date}` | Delete daily recap |
| `GET` | `/api/calendar/shared` | List shared calendars |
| `POST` | `/api/calendar/shared` | Subscribe to a shared calendar |
| `POST` | `/api/calendar/shared/sync-all` | Sync all shared calendars |
| `POST` | `/api/calendar/shared/validate` | Validate an iCal URL |
| `PATCH` | `/api/calendar/shared/{calendar_id}` | Update a shared calendar |
| `DELETE` | `/api/calendar/shared/{calendar_id}` | Delete a shared calendar |
| `POST` | `/api/calendar/shared/{calendar_id}/sync` | Sync a single shared calendar |

## Proactor - `/api/proactor`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/proactor/analyze?start=...&end=...` | Analyze schedule for a date range |
| `POST` | `/api/proactor/analyze` | Analyze schedule (POST variant) |

## Knowledge Base - `/api/knowledge`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/knowledge/stats` | Get vector store stats |
| `GET` | `/api/knowledge/summaries` | List available summaries for the picker |
| `POST` | `/api/knowledge/load` | Load summaries into vector store |
| `POST` | `/api/knowledge/search` | Semantic search across summaries |
| `POST` | `/api/knowledge/ask` | RAG question answering |
| `POST` | `/api/knowledge/mindmap` | Generate tag-based mind map |
| `POST` | `/api/knowledge/mindmap/generate` | Generate AI-powered mind map |
| `POST` | `/api/knowledge/clear` | Clear the vector store |

## Auth - `/api/auth`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Authenticate and create session |
| `POST` | `/api/auth/logout` | Destroy session and clear cookie |

---

**Related:** [Getting Started](getting-started.md)
