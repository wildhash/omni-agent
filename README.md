# 🤖 Omni-Agent

A self-assembling, multi-modal AI OS built by an AI.

## Overview

Omni-Agent is an autonomous, multi-agent system that orchestrates specialized AI agents to handle web automation, code execution, GitHub management, documentation, and more.

## Architecture

```
omni_agent/
├── orchestrator.py       # Routes tasks to the right agent
├── agents/
│   ├── web_agent.py      # Browser automation & web interactions
│   ├── code_agent.py     # Code execution, debugging & containerization
│   └── voice_agent.py    # Simulated voice I/O primitives (TTS/STT demo)
├── backend/
│   └── main.py           # FastAPI REST API
├── ui/
│   └── gradio_app.py     # Gradio demo UI (optional)
├── github/
│   ├── issue_agent.py    # Auto-responds to GitHub issues
│   └── release_agent.py  # Automates versioned releases
└── docs/
    └── generator.py      # Auto-generates Markdown documentation
github_agent.py           # Main self-sustaining loop
```

## Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- A GitHub personal access token (for `GITHUB_TOKEN`)
- An API key for the backend (set `OMNI_AGENT_API_KEY`)

### Installation

```bash
pip install -r requirements.txt
```

Create a local `.env` file (see `.env.example`) to configure your environment.

**Required (local dev):**

- `OMNI_AGENT_API_KEY=...` (preferred for all environments; only in exceptional cases, for unsafe testing on `localhost` only, you may set `OMNI_AGENT_ALLOW_INSECURE_NOAUTH=1`)
- `GITHUB_TOKEN=...` (use a least-privileged token)
- `WEAVIATE_URL=http://localhost:8080` (HTTP is for local development)

**Optional / deployment:**

- `WEAVIATE_API_KEY`, `WEAVIATE_API_USER`
- `DOCKER_USERNAME`, `DOCKER_PASSWORD` (only if you plan to push images to Docker Hub; CI deploy uses GHCR by default)

Only `.env.example` is committed by default.

See `.env.example` for supported environment variables, defaults, and security notes.

**Never commit** your local `.env` or any file containing real secrets.

For deployments, provide secrets via your deployment environment (Docker secrets, CI secrets, etc.), not committed files.

### Running with Docker Compose

```bash
docker-compose up --build
```

Note: the `Dockerfile` is optimized for running the FastAPI service and only copies `omni_agent/` into the image.

For a more production-like setup (Weaviate API key auth enabled):

```bash
docker-compose -f docker-compose.prod.yml up --build
```

### Running locally

```bash
uvicorn omni_agent.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Security defaults

Some capabilities are intentionally disabled by default because they can be dangerous if exposed via the API:

- To enable `CodeAgent` Python execution: set `OMNI_AGENT_ENABLE_CODE_EXEC=1`
- To enable `CodeAgent` Docker builds: set `OMNI_AGENT_ENABLE_DOCKER_BUILD=1`
- To allow `SelfHealer` to write files: set `OMNI_AGENT_ENABLE_SELF_HEAL_APPLY=1`
- To activate generated agents (import/execute from disk): set `OMNI_AGENT_ENABLE_GENERATED_AGENTS=1`
- To run without API authentication (local dev only): set `OMNI_AGENT_ALLOW_INSECURE_NOAUTH=1`

**Dangerous environment flags:** the `OMNI_AGENT_*` flags above are for isolated local development only. Do not enable them in any exposed, shared, staging, or production environment, including Docker containers bound to `0.0.0.0` or otherwise reachable over a network.

`OMNI_AGENT_ALLOW_INSECURE_NOAUTH` disables API key checking entirely (and ignores `OMNI_AGENT_API_KEY`).

**Warning:** Combining `OMNI_AGENT_ALLOW_INSECURE_NOAUTH` with code execution or Docker builds effectively exposes unauthenticated remote code execution. The application does not currently prevent this combination at runtime; this is intended only for tightly controlled, single-user local experiments.

## API

| Method | Endpoint  | Description                    |
|--------|-----------|-------------------------------|
| POST   | /task     | Delegate a task to an agent    |
| GET    | /memory   | Recall past task interactions  |

### Example

```bash
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OMNI_AGENT_API_KEY" \
  -d '{"task": "book flight from SFO to NYC", "context": {"date": "2026-03-15"}}'
```

You can also force a specific agent by setting `context.agent` to one of: `web`, `code`, `voice`.

## Testing

```bash
pytest tests/
```

## Gradio UI (optional)

```bash
pip install -r requirements-ui.txt
python -m omni_agent.ui.gradio_app
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
