FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install -r requirements.txt

# The repository-root build context includes all committed offline JSON caches.
COPY backend/ ./
RUN python -c "import json; from pathlib import Path; [json.loads(Path(p).read_text()) for p in ('data/scenario.json', 'data/matrix.json', 'data/paths.json', 'forecast/history.json', 'forecast/forecast.json')]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
