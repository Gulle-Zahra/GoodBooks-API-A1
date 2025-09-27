# GoodBooks API (MongoDB) — Assignmnet 1

**What this repo contains**
- `/app` — FastAPI app (server entrypoint `app/main.py`)
- `/ingest` — idempotent CSV → Mongo ingestion scripts (samples + chunked importer)
- `/tests` — pytest test suite (HTTP tests run against running server)
- `docker-compose.yml` — starts MongoDB + API (one command)
- `openapi.json` — optional OpenAPI export (generated from running server)
- `postman_collection.json` — Postman collection you can import 
- `DESIGN.md` — short design note (schema, indexes, trade-offs)
- `README.md` — this file


### Prerequisites
- Docker Desktop (Windows / macOS / Linux)
- Docker Compose (v2)
- (Optional) Python 3.11+ if you want to run ingest scripts locally

### 1. Start :
From repo root:
```bash
docker compose up --build -d
