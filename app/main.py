"""FastAPI application: JSON API under /api, static web UI at /."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import ARTIFACT_DIR, CORS_ORIGINS, FRONTEND_DIR
from .database import init_db
from .model_service import service
from .routers import history, meta, predict

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("soilp")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    service.load(ARTIFACT_DIR)
    yield


app = FastAPI(
    title="Soil Phosphorus Prediction API",
    version=__version__,
    description=("Predicts soil phosphorus content from 72 hours of soil/air sensor data with a "
                 "PSO-tuned CNN-BiLSTM-Attention network. Interactive docs below."),
    lifespan=lifespan,
)

if CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


def _loc(loc: tuple) -> str:
    return ".".join(str(p) for p in loc if p not in ("body", "query", "header"))


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    """Flatten pydantic errors into [{field, message}] so the UI can show them next to inputs."""
    detail = [{"field": _loc(e["loc"]), "message": e["msg"].removeprefix("Value error, ")}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "validation_error", "detail": detail})


app.include_router(meta.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(history.router, prefix="/api")

# Static UI last, so /api/* and /docs take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")
