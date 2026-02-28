FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY omni_agent ./omni_agent
COPY github_agent.py ./

EXPOSE 8000

CMD ["uvicorn", "omni_agent.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
