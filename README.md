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
│   └── code_agent.py     # Code execution, debugging & containerization
├── backend/
│   └── main.py           # FastAPI REST API
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

Create a local `.env` file (see `.env.example`) to configure `GITHUB_TOKEN`, `WEAVIATE_URL`, and API auth. Some flags are intentionally dangerous (for example `OMNI_AGENT_ALLOW_INSECURE_NOAUTH`, `OMNI_AGENT_ENABLE_CODE_EXEC`, and `OMNI_AGENT_ENABLE_DOCKER_BUILD`) and should stay disabled outside isolated local development.

### Running with Docker Compose

```bash
docker-compose up --build
```

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

Only enable these in trusted environments (e.g. local development). Exposing them in a deployed API can lead to remote code execution.

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

## Testing

```bash
pytest tests/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
