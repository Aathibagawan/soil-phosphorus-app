import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_BYTES
from ..csv_utils import CsvError, parse_csv
from ..database import get_db, save_prediction
from ..deps import optional_client_id, rate_limit
from ..features import FEATURE_KEYS
from ..model_service import ModelNotLoaded, WindowTooShort, service
from ..schemas import PredictRequest, PredictResponse

router = APIRouter(tags=["predict"], dependencies=[Depends(rate_limit)])


def _run(rows: list[dict], single: bool, label: str | None, client_id: str, db: Session) -> PredictResponse:
    arr = np.array([[r[k] for k in FEATURE_KEYS] for r in rows], dtype="float64")
    try:
        res = service.predict(arr, single_reading=single)
    except ModelNotLoaded:
        raise HTTPException(503, "Model is not available. Train it with `python -m ml.train`.")
    except WindowTooShort as e:
        raise HTTPException(422, str(e))

    mode = "single_reading" if single else "time_series"
    row = save_prediction(
        db, client_id=client_id, label=label or None, input_mode=mode,
        rows_used=1 if single else service.window, prediction=res["prediction"], unit=res["unit"],
        inputs=res["input_summary"], warnings=res["warnings"], model_version=res["model_version"],
        latency_ms=res["latency_ms"],
    )
    return PredictResponse(
        id=row.id, prediction=res["prediction"], unit=res["unit"], input_mode=mode,
        rows_used=row.rows_used, window=service.window, attention=res["attention"],
        feature_effects=res["feature_effects"], warnings=res["warnings"],
        model_version=res["model_version"], latency_ms=res["latency_ms"], created_at=row.created_at,
    )


@router.post("/predict", response_model=PredictResponse, summary="Predict soil phosphorus from JSON")
async def predict(body: PredictRequest, client_id: str = Depends(optional_client_id),
                  db: Session = Depends(get_db)):
    if body.reading is not None:
        rows, single = [body.reading.model_dump()], True
    else:
        rows, single = [r.model_dump() for r in body.window], False
    return await run_in_threadpool(_run, rows, single, body.label, client_id, db)


@router.post("/predict/csv", response_model=PredictResponse,
             summary="Predict from an uploaded CSV of hourly readings")
async def predict_csv(file: UploadFile = File(...), label: str | None = Form(None, max_length=120),
                      client_id: str = Depends(optional_client_id), db: Session = Depends(get_db)):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (limit {MAX_UPLOAD_BYTES // 1024} KB).")
    try:
        rows = parse_csv(raw)
    except CsvError as e:
        raise HTTPException(422, {"message": str(e), "details": e.details})
    return await run_in_threadpool(_run, rows, False, label, client_id, db)
