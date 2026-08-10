# Knowledge Base & Mind Map

Retrieval-Augmented Generation (RAG) for searching and querying your meeting knowledge, plus interactive mind maps.

![Knowledge Base](screenshots/knowledge-base.png)

---

## Overview

The Knowledge page lets you search or ask natural-language questions across your entire meeting knowledge base, backed by a local vector store (ChromaDB). It also includes an interactive mind map for visualizing connections between summaries.

Embeddings and answers can run on **Gemini** (cloud) or **offline** (Ollama, or in-process for non-Docker dev) — see [Docker → Local knowledge base](docker.md) for the `EMBEDDING_PROVIDER` / `RAG_PROVIDER` settings.

## Setup

New summaries are **indexed automatically** when they're generated, so search and Ask stay current on their own. Use **Load Summaries** on the Knowledge page to backfill summaries created before indexing was enabled, or to rebuild after switching the embedding model. Embeddings are stored in `settings/vector_store/`.

## Semantic Search

Use **Search** to find content across all indexed summaries by meaning, not just keywords.

- Enter a natural-language query.
- Results are ranked by semantic similarity.
- Each result links back to the source summary.

## Question Answering (RAG)

Use **Ask** to pose natural-language questions:

1. Type your question (e.g. "What decisions were made about the migration timeline?").
2. Relevant summary chunks are retrieved from the vector store.
3. The configured model (Gemini, or a local Ollama model) answers based on the retrieved context.
4. The response includes **source citations** with links back to the original summaries.

## Filtering

Optionally filter queries to specific summaries using the **summary picker**. This narrows the search scope when you're looking for information from a particular meeting.

## Clearing the Vector Store

Click **Clear** to reset the vector store and re-index from scratch. Useful after deleting or regenerating summaries.

---

## Mind Map

Visualize connections across summaries as an interactive graph.

![Mind Map](screenshots/mind-map.png)

### Tag-Based Mode (Default)

- Generates a graph **instantly** - no AI call needed.
- Summary nodes connect to shared tag nodes.
- Great for a quick overview of topic clusters.

### AI-Generated Mode

- The configured model (Gemini or local Ollama) produces a **hierarchical map**:
  - Central topic
  - Thematic branches (count scales with how many summaries you have)
  - Key insights as leaf nodes (with source summary IDs)
  - Cross-cutting connections between themes
- For large knowledge bases, summaries are **clustered by embedding** and each cluster is labelled separately, so the map covers the whole base instead of only what fits in one prompt. Requires summaries to be loaded/indexed first.

---

**Related:** [Summarization](summarization.md) · [Daily Recap](daily-recap.md)
