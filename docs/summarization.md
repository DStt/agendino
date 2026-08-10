# Summarization

Generate structured AI summaries from transcripts using Google Gemini or Anthropic Claude, with customizable system prompts.

![Summarization](screenshots/summarization.png)

---

## Overview

Once a recording has been transcribed, you can generate a structured summary using Gemini. Summaries include a **title**, **tags**, and a **full markdown body**. You can create multiple summary versions per recording using different system prompts.

## How It Works

1. Make sure the recording has been transcribed first.
2. Click **Summarize** and choose a **system prompt** from the available categories (e.g. `Generale / SintesiAdattiva`, `IT&Engineering / VerbaleIT`).
3. Gemini generates a structured JSON response containing:
   - **Title** - a concise summary title.
   - **Tags** - relevant keywords for categorization.
   - **Summary** - full markdown content with sections, bullet points, and structure defined by the prompt.
4. The result is saved to the database.

## Multiple Summary Versions

You can re-summarize the same recording with a different prompt at any time. Each summary is saved as a separate version - previous summaries are never overwritten.

This is useful when you want different perspectives on the same meeting (e.g. an executive recap vs. a detailed action tracker).

## Editing Summaries

After generation, you can inline-edit:
- **Title** - click to edit.
- **Tags** - add, remove, or modify tags.
- **Content** - edit the full markdown body.

All changes are saved to the database.

## Choosing a Provider

Summarization can run on either Google Gemini (default) or Anthropic Claude. The
provider is selected app-wide via environment variables in `.env`:

| Variable | Default | Options |
|----------|---------|---------|
| `SUMMARIZATION_PROVIDER` | `gemini` | `gemini`, `claude` |
| `ANTHROPIC_API_KEY` | — | Required when provider is `claude` |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | `claude-sonnet-4-6`, `claude-opus-4-8`, `claude-haiku-4-5` |

Restart the app after changing these. Both providers return the same structured
title / tags / summary, so existing system prompts work unchanged either way.

> **Note:** Claude is only available for summarization. Its API cannot accept audio,
> so **transcription** always uses Gemini or Whisper regardless of this setting.

### Claude Models

When `SUMMARIZATION_PROVIDER=claude`, the model is chosen with `CLAUDE_MODEL`:

| `CLAUDE_MODEL` | Best for | Relative cost |
|----------------|----------|---------------|
| `claude-sonnet-4-6` *(default)* | Balanced speed, quality, and cost — recommended for most summarization. | $ |
| `claude-opus-4-8` | Highest quality on long or complex transcripts where accuracy matters most. | $$$ |
| `claude-haiku-4-5` | Fastest and cheapest, for short recordings or high volume. | ¢ |

To set the model, add the variable to your `.env` file and restart the app. For
example, to use the most capable model:

```dotenv
SUMMARIZATION_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-opus-4-8
```

If `CLAUDE_MODEL` is omitted, it defaults to `claude-sonnet-4-6`. Use the exact model
ID strings above (no date suffixes). You can point `CLAUDE_MODEL` at any current
Claude model ID your API key has access to.

## System Prompts

Summaries are shaped by the system prompt you choose. See [Custom System Prompts](custom-system-prompts.md) for how to add your own.

---

**Related:** [Transcription](transcription.md) · [Task Generation](task-generation.md) · [Custom System Prompts](custom-system-prompts.md)
