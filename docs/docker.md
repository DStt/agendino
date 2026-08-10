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

All configuration lives in a `.env` file in the project root. Copy the template and fill it in:

```bash
cp .env.example .env
```

`compose.yaml` reads these values and mounts `./local_recordings`, `./settings`, and `./certs`
from the repo — you no longer edit paths or IPs directly in `compose.yaml`. At minimum set
`GEMINI_API_KEY`. See [Authentication](authentication.md) for `AUTH_ENABLED`,
[Transcription](transcription.md) for Whisper, and the GPU section below for `GPU=1`.

### `INTERNAL_IP` — how the app is reached

`INTERNAL_IP` is the host (IP or domain) that Traefik routes the app on. It's substituted into
Traefik's `Host(...)` rules for both the app and the Traefik dashboard:

```env
INTERNAL_IP=192.168.1.100      # or a domain, e.g. agendino.local
```

It directly controls who can reach the app and at what address:

- **You must open the app at exactly this host.** With `INTERNAL_IP=192.168.1.100`, the app is
  served at `https://192.168.1.100`. Traefik matches the request's `Host` header against this
  value — if it doesn't match, Traefik returns **404** and the app is unreachable *even though
  the containers are running*.
- **The default `127.0.0.1` is localhost-only** — reachable only from the server itself. Other
  devices on the network cannot connect.
- **To allow LAN/remote access**, set it to the server's **LAN IP** (e.g. `192.168.1.100`) or a
  **domain** that resolves to the server (via DNS or each client's hosts file).
- The TLS certificate in `certs/` should be valid for this host/name, or browsers will show a
  warning.

Changing `INTERNAL_IP` takes effect on the next `docker compose up -d` (the containers are
recreated and Traefik re-reads the routing labels).

## Running the Deployment

```bash
docker compose up -d
```

This starts the services in detached mode. AgenDino is served by Traefik at the host you set in
`INTERNAL_IP` (e.g. `https://192.168.1.100`), and the Traefik dashboard at
`https://<INTERNAL_IP>/traefik/dashboard/`. See [`INTERNAL_IP`](#internal_ip--how-the-app-is-reached) above.

To view logs:

```bash
docker compose logs -f
```

To stop:

```bash
docker compose down
```

## GPU acceleration (optional)

Local Whisper transcription runs on the **celery** worker. By default it runs on **CPU**.
You can optionally run it on an **NVIDIA GPU** by layering in `compose.gpu.yaml`.

> GPU support targets **Linux** hosts. The container image is Linux-based regardless of where
> Docker runs.

### Host prerequisites

1. NVIDIA driver installed — `nvidia-smi` works on the host.
2. Install the **NVIDIA Container Toolkit** and configure the Docker runtime:
   ```bash
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```
3. Verify Docker can see the GPU:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
   ```

### Enable GPU

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

Or make it the default so you don't have to pass the flags. `.env.example` ships with:

```env
#GPU=1
COMPOSE_FILE=compose.yaml${GPU:+:compose.gpu.yaml}
```

Uncomment `GPU=1`, then plain `docker compose up -d` loads the GPU override automatically.
(You don't set `WHISPER_DEVICE` — base `auto` resolves to CUDA once the GPU is reserved.)

### Disable GPU

Run plain `docker compose up -d` (CPU mode), or re-comment the `GPU=1` line in `.env`.

**Notes on `COMPOSE_FILE`:**
- A command-line `-f` overrides `COMPOSE_FILE`, so you can still force CPU with
  `docker compose -f compose.yaml up -d` even when the `.env` default is GPU.
- It is "sticky": once set, **every** `docker compose` command uses both files. On a host
  without a working GPU, plain `docker compose up` then fails on the GPU reservation — use the
  base file only on non-GPU hosts.
- The path separator is `:` on Linux (`;` on Windows).

`compose.gpu.yaml` sets `WHISPER_COMPUTE_TYPE=float16` and `WHISPER_MODEL_SIZE=turbo`,
which suit a modern GPU sharing VRAM with Ollama. Raise to `large-v3` if you have the VRAM; for older
cards, adjust these — see [Transcription → GPU compatibility](transcription.md).

### Local knowledge base (Ollama)

The `ollama` service (in `compose.yaml`) provides offline **embeddings** (`EMBEDDING_PROVIDER=ollama`,
`OLLAMA_EMBEDDING_MODEL`, default `bge-m3`) and **answer generation** (`RAG_PROVIDER=local`,
`OLLAMA_MODEL`, default `qwen2.5:7b`). The app reaches it by service name at `http://ollama:11434` —
no `host.docker.internal` / `OLLAMA_HOST` setup. Models bind-mount to `settings/ollama_models`
(auto-created on first `up`).

**Recommended generation model for both modes:** `qwen2.5:7b` — strong synthesis + reliable JSON
(used by `/ask` and the AI mind map), fits the RTX 3080 GPU and runs acceptably on CPU (e.g. Ryzen 7
5700G + 32 GB). For snappier CPU responses, use `qwen2.5:3b`.

The container **auto-pulls** `OLLAMA_EMBEDDING_MODEL` and `OLLAMA_MODEL` on startup (idempotent — only
the first start downloads; later starts are instant). So the **first** `up` takes a few minutes while
the models download, and embeddings/answers return errors until they finish. To pull a different model
manually: `docker compose exec ollama ollama pull <model>`.

Because embeddings live in the Ollama container, one model is shared across all `agendino` web
workers, and the `agendino` image carries no `torch`/`sentence-transformers`.

**GPU & VRAM.** `GPU=1` reserves the GPU for `ollama` and `celery` (Whisper) — **not** `agendino`
(the web service loads no model). There is **no cross-container GPU queue**: CUDA time-slices compute
but VRAM is additive, so overflow is a hard CUDA OOM, not a graceful wait. Budget on a 10 GB card
shared with a desktop (~5 GB free): `bge-m3` ~1.5 GB + `qwen2.5:7b` ~4.7 GB + Whisper `turbo` ~1.5 GB
+ the `OLLAMA_CONTEXT_LENGTH=8192` KV cache. Use a smaller LLM (`qwen2.5:3b`), shorter context, or a
smaller Whisper model if you run transcription and `/ask` at the same time. Changing
`EMBEDDING_PROVIDER`/`OLLAMA_EMBEDDING_MODEL` triggers a one-time vector-store re-embed (reload
summaries from the Knowledge page).

**Knowledge base sizing.** `OLLAMA_CONTEXT_LENGTH=8192` (set on the `ollama` service) lets `/ask` see
the full top-k retrieved summaries instead of clipping to the first ~4096 tokens; lower it on small
cards. Embeddings use Ollama's native `/api/embed` with `num_batch=8192` (an embedding model processes
the whole input in one batch, so a long summary would otherwise fail with "input … too large to
process"); summaries longer than 8192 tokens are truncated to the model context. The **AI mind map**
clusters summary embeddings and labels one branch per cluster (re-clustered each generation, branch
count scales with corpus size), so it represents the whole knowledge base at any scale — but it reads
from the vector store, so summaries must be **embedded** first (automatic on summarize; "Load
summaries" backfills existing ones / repairs after a reset).

## Concurrency tuning (CPU vs GPU)

`CELERY_CONCURRENCY` controls how many transcription/summarization jobs run in **parallel**
on the worker. Set it in `.env` or the `celery` service `environment:` (default `1`). Jobs for
the *same* recording are deduplicated by a lock, so this only speeds up processing of
*different* recordings at once.

> Uploads scale separately via `WEB_CONCURRENCY` (web workers) — a different knob with a
> different bottleneck.

**To change it safely:** raise `CELERY_CONCURRENCY` by 1, recreate the worker
(`docker compose up -d` — no rebuild needed for an env change), start 2+ transcriptions on
different files, and watch the limiting resource before going higher.

| Mode | Limited by | Recommended | Why |
|------|-----------|-------------|-----|
| **CPU** | Cores / RAM | **1–2** | faster-whisper already multithreads internally; stacking workers oversubscribes the CPU and can be *slower*. Each worker also loads its own model into RAM. |
| **GPU** | VRAM | **1–2** (start at 1) | Each worker loads its own model copy into VRAM and they share one GPU's compute. Estimate `floor(free_VRAM / model_VRAM)`. On a 10 GB card with `large-v3` float16 (~3 GB), 1–2 is safe; an OOM crashes the task. |

---

**Next:** explore the features - start with [Recording Management](recording-management.md) or browse the full [Documentation Index](index.md).
