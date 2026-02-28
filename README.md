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

### Installation

```bash
pip install -r requirements.txt
```

### Running with Docker Compose

```bash
docker-compose up --build
```

### Running locally

```bash
uvicorn omni_agent.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## API

| Method | Endpoint  | Description                    |
|--------|-----------|-------------------------------|
| POST   | /task     | Delegate a task to an agent    |
| GET    | /memory   | Recall past task interactions  |

### Example

```bash
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
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
