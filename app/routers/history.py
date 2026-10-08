import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import Prediction, get_db
from ..deps import required_client_id
from ..features import FEATURE_KEYS
from ..schemas import HistoryItem, HistoryPage, HistoryStats

router = APIRouter(prefix="/history", tags=["history"])


def _own(client_id: str):
    return Prediction.client_id == client_id


@router.get("", response_model=HistoryPage, summary="List this browser's past predictions (newest first)")
def list_history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                 client_id: str = Depends(required_client_id), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Prediction).where(_own(client_id))) or 0
    rows = db.scalars(select(Prediction).where(_own(client_id))
                      .order_by(Prediction.id.desc()).limit(limit).offset(offset)).all()
    return HistoryPage(items=[HistoryItem.model_validate(r, from_attributes=True) for r in rows],
                       total=total, limit=limit, offset=offset)


@router.get("/stats", response_model=HistoryStats)
def stats(client_id: str = Depends(required_client_id), db: Session = Depends(get_db)):
    agg = db.execute(select(func.count(), func.avg(Prediction.prediction), func.min(Prediction.prediction),
                            func.max(Prediction.prediction)).where(_own(client_id))).one()
    recent = db.scalars(select(Prediction).where(_own(client_id)).order_by(Prediction.id.desc()).limit(50)).all()
    return HistoryStats(
        count=agg[0], mean=agg[1], min=agg[2], max=agg[3], unit=recent[0].unit if recent else None,
        series=[{"id": r.id, "created_at": r.created_at.isoformat(), "prediction": r.prediction}
                for r in reversed(recent)])


@router.get("/export.csv", summary="Download all of this browser's predictions as CSV")
def export_csv(client_id: str = Depends(required_client_id), db: Session = Depends(get_db)):
    rows = db.scalars(select(Prediction).where(_own(client_id)).order_by(Prediction.id.asc())).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at_utc", "label", "input_mode", "rows_used", "prediction", "unit",
                "model_version", *[f"mean_{k}" for k in FEATURE_KEYS], "warnings"])
    for r in rows:
        w.writerow([r.id, r.created_at.isoformat(), r.label or "", r.input_mode, r.rows_used,
                    round(r.prediction, 4), r.unit, r.model_version,
                    *[r.inputs.get("mean", {}).get(k, "") for k in FEATURE_KEYS], " | ".join(r.warnings or [])])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="phosphorus_predictions.csv"'})


@router.get("/{item_id}", response_model=HistoryItem)
def get_item(item_id: int, client_id: str = Depends(required_client_id), db: Session = Depends(get_db)):
    row = db.scalar(select(Prediction).where(Prediction.id == item_id, _own(client_id)))
    if not row:
        raise HTTPException(404, "Prediction not found.")
    return HistoryItem.model_validate(row, from_attributes=True)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, client_id: str = Depends(required_client_id), db: Session = Depends(get_db)):
    res = db.execute(delete(Prediction).where(Prediction.id == item_id, _own(client_id)))
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Prediction not found.")


@router.delete("", status_code=204, summary="Delete all of this browser's history")
def clear(client_id: str = Depends(required_client_id), db: Session = Depends(get_db)):
    db.execute(delete(Prediction).where(_own(client_id)))
    db.commit()
