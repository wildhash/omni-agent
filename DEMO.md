# Omni-Agent Demo (Recording)

Quick steps to run the full stack for a demo video.

## 1. Environment

Ensure `.env` exists (copy from `.env.example`). For local demo:

- `OMNI_AGENT_ALLOW_INSECURE_NOAUTH=1` (no API key needed for local UI)
- `MISTRAL_API_KEY=...` (optional; enables self-heal and code improve)

## 2. Start services

**Terminal 1 – Backend (optional; only if you want to demo the REST API):**

```bash
uvicorn omni_agent.backend.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 – Gradio UI (main demo):**

```bash
pip install -r requirements-ui.txt
python -m playwright install chromium
python -m omni_agent.ui.gradio_app
```

Open **http://127.0.0.1:7860**.

## 3. Demo flow

1. **Task tab** – Try:
   - `book flight from SFO to NYC` with context `{"date": "2026-03-15"}`
   - `browse web` (simulated)
   - `screenshot` with context `{"url": "https://example.com"}` (Vision agent)

2. **Voice tab** – Type text → **Speak** (simulated TTS); optionally upload audio → **Transcribe** (simulated STT).

3. **Vision tab** – Set URL (default: the Gradio app itself). Use:
   - **Screenshot** – capture the page
   - **Analyze DOM** – screenshot + interactive elements list
   - **List Elements** – buttons/inputs/links with bounds
   - **Capture Diff** – before/after with delay (e.g. change something in another tab, then run)

## 4. Production-style run (bind to all interfaces)

```bash
GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 python -m omni_agent.ui.gradio_app
```

For a temporary public link (e.g. for remote viewers):

```bash
GRADIO_SHARE=1 python -m omni_agent.ui.gradio_app
```
