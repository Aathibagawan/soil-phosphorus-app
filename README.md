---
title: Soil Phosphorus Predictor
emoji: 🌱
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# 🌱 Soil Phosphorus Predictor

A PSO-tuned **CNN-BiLSTM-Attention** model served as a production-style web app:
FastAPI backend, validated inputs, per-browser results history, Docker image, CI, and one-click deployment.

> Based on the project *"An Attention-Enhanced PSO-CNN-BiLSTM Model for Precise Soil Phosphorus Content Prediction"*
> (University College of Engineering Thirukkuvalai, Anna University, 2026).

## What it does

| Capability | Where |
|---|---|
| Model served over a REST API (`/api/predict`, `/api/predict/csv`) | `app/routers/predict.py` |
| Input validation (physical ranges, missing/extra fields, NaN/inf, CSV line-level errors) | `app/schemas.py`, `app/csv_utils.py` |
| Out-of-training-range warnings + attention & feature-sensitivity explanations | `app/model_service.py` |
| Results history (list, detail, delete, clear, stats, CSV export) | `app/routers/history.py`, `frontend/history.html` |
| Web UI: predict, history, model report page | `frontend/` (plain HTML/JS, no build step) |
| Auto-generated API docs | `/docs` |
| Containerised, health-checked, rate-limited | `Dockerfile`, `/api/health` |
| Tests + CI | `tests/`, `.github/workflows/ci.yml` |

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 7860      # → http://localhost:7860
pytest -q
```

Or with Docker (history persists in a named volume):

```bash
docker compose up --build                       # → http://localhost:7860
```

## Deploy

### Option A — Hugging Face Spaces (recommended; free, 16 GB RAM)
1. Create a new Space at huggingface.co/new-space → **SDK: Docker**.
2. Push this repo to it:
   ```bash
   git init && git add . && git commit -m "Initial deploy"
   git remote add space https://huggingface.co/spaces/<your-username>/<space-name>
   git push space main
   ```
   The YAML block at the top of this README tells Spaces to build the `Dockerfile` and route port 7860.
3. History survives only as long as the container does (free Spaces storage is ephemeral). For permanent history,
   add a **Space secret** `DATABASE_URL` pointing to a free hosted Postgres (Neon, Supabase), e.g.
   `postgresql://user:pass@host/db`.

### Option B — Render
`render.yaml` is a Blueprint (Docker web service + Postgres). TensorFlow needs roughly 1 GB RAM, so the
free 512 MB web tier will not start the model; the Blueprint uses the `starter` plan.
New → Blueprint → select the repo.

### Option C — any Docker host (Fly.io, Railway, Cloud Run, a VPS)
The image listens on `$PORT` (default 7860), exposes `/api/health`, and needs no other services.

## API

```bash
# single reading (repeated across the 72-hour window — approximate)
curl -X POST localhost:7860/api/predict -H 'Content-Type: application/json' -d '{
  "reading": {"soil_temperature":17.5,"soil_humidity":31,"electrical_conductivity":54,
              "ph":7.1,"air_temperature":20,"air_humidity":75,"light_intensity":70000}}'

# 72+ hourly rows from a CSV (most accurate)
curl -X POST localhost:7860/api/predict/csv -F file=@window.csv -F label="North plot"
```

History endpoints need an `X-Client-Id` header (the browser UI generates one automatically; no login):
`GET /api/history`, `GET /api/history/{id}`, `GET /api/history/stats`, `GET /api/history/export.csv`,
`DELETE /api/history/{id}`, `DELETE /api/history`. Full schema at `/docs`.

Validation failures return `422` with `{"error":"validation_error","detail":[{"field":"reading.ph","message":"..."}]}`.

### Configuration (environment variables)
| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `7860` | Listen port (Docker) |
| `DATABASE_URL` | SQLite in `./data` | Use Postgres for persistent history |
| `CORS_ORIGINS` | *(none)* | Comma-separated origins if the UI is hosted elsewhere |
| `RATE_LIMIT_PER_MIN` | `60` | Per-IP limit on prediction endpoints (0 = off) |
| `MAX_HISTORY_PER_CLIENT` | `500` | Oldest rows are pruned beyond this |
| `ARTIFACT_DIR` | `./artifacts` | Where `model.keras` + `metadata.json` live |

## Retrain the model

```bash
pip install -r requirements-train.txt
python -m ml.train --quick                      # ~2 min smoke run (what ships in artifacts/)
python -m ml.train                              # full PSO search (8 particles × 10 iterations; slow on CPU)
python -m ml.train --data my_sensor_data.csv    # your real data
```

Your CSV needs hourly rows with columns `Soil_Temperature, Soil_Humidity, Electrical_Conductivity, pH,
Air_Temperature, Air_Humidity, Light_Intensity, Phosphorus` (+ optional `timestamp`).
Training rewrites `artifacts/model.keras` and `artifacts/metadata.json`; commit both and redeploy.
If your sensors use different units, edit `app/features.py` (validation limits and labels live there).

## Project layout

```
app/        FastAPI service (routers, schemas, DB, model service)
frontend/   Static UI served by FastAPI (index, history, about)
ml/         Data generator + training script (PSO + CNN-BiLSTM-Attention)
artifacts/  Trained model + metadata (scalers, ranges, metrics) used at serve time
tests/      API tests (validation, prediction, history, CSV)
```

## Important limitations

* **The shipped model is trained on synthetic data** (ported from the project notebooks) with a *quick* PSO search.
  The UI says so on every page. Retrain on real sensor + lab data before relying on any number.
* The research report cites RMSE 8.74 mg/kg / R² 0.924. Those figures do **not** come from this pipeline; the app reports
  only metrics computed by `ml/train.py` on a held-out chronological test set.
* On the synthetic data a Ridge regression baseline matches the deep model — the About page shows this openly.
* Single-reading mode repeats one reading for 72 hours; it is an approximation and is flagged in the UI and history.
* Anonymous history is keyed to a browser-held ID, not a login. Add authentication before storing sensitive data.
* Decision-support estimate only; not a substitute for laboratory soil analysis.
