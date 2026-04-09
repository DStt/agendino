# Custom System Prompts

Add and organize your own summarization prompts to shape how Gemini generates summaries.

---

## Overview

System prompts are stored as `.txt` files under the `system_prompts/` directory, organized by **language** and **category**. They appear automatically in the prompt selection dropdown when summarizing a recording.

## Directory Structure

```
system_prompts/
  en/
    General/
      AdaptiveSummary.txt
      ExecutiveTLDR.txt
      DecisionsAndRisks.txt
    Meeting/
      OperationalSummary.txt
      ActionTracker.txt
      ClientRecap.txt
    IT&Engineering/
      ITMinutes.txt
      LightPostMortem.txt
  it/
    Generale/
      SintesiAdattiva.txt
      TLDRDirigenziale.txt
    Riunione/
      SintesiOperativa.txt
      ActionTracker.txt
    IT&Engineering/
      VerbaleIT.txt
      PostMortemLeggero.txt
```

## Adding a New Prompt

1. Create a `.txt` file in the appropriate `language/category/` folder.
2. Write the prompt content - this is sent to Gemini as the system instruction.
3. Save the file. It will appear in the dropdown immediately (no restart needed).

### Example

To add an English "Risk Register" prompt:

```
system_prompts/en/Meeting/RiskRegister.txt
```

## Prompt-Writing Guidelines

- **Focus on one clear outcome** - e.g. executive recap, action tracker, risk register.
- **Define a strict output structure** - specify sections and, when useful, table columns.
- **Add anti-hallucination constraints** - e.g. "use only transcript evidence", "write 'not specified' for missing fields".
- **Prefer concise, actionable language** over generic prose.

## How Prompts Are Used

When you click **Summarize** on a recording:

1. You select a prompt from the dropdown (organized as `Language / Category / PromptName`).
2. The prompt text is sent to Gemini as the system instruction.
3. The transcript is sent as the user message.
4. Gemini returns a structured JSON response (title, tags, summary) shaped by your prompt.

---

**Related:** [Summarization](summarization.md)
