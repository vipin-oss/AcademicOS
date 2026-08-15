# AcademicOS backend image (V3 M19, ADR-066).
#
#   docker build -t academicos-backend -f backend/Dockerfile backend
#
# The app is a single FastAPI/uvicorn process; Postgres + Qdrant are separate
# services (see docker-compose.yml). No secrets are baked into the image —
# configuration is injected via environment at run time.
FROM python:3.12-slim

WORKDIR /app

# System deps for the pinned psycopg2-binary build (avoid source builds).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The app binds 0.0.0.0 so the reverse proxy / compose network can reach it.
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
