from fastapi import APIRouter, HTTPException

from .. import __version__
from ..features import FEATURES
from ..model_service import service

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    """Liveness/readiness probe (used by Docker, Render and uptime monitors)."""
    return {"status": "ok" if service.loaded else "degraded", "model_loaded": service.loaded,
            "api_version": __version__,
            "model_version": service.meta["model_version"] if service.meta else None}


@router.get("/model/info")
def model_info():
    """Everything the UI needs: features + limits, window size, metrics, curves."""
    if not service.loaded:
        raise HTTPException(503, "Model not loaded. Train it with `python -m ml.train`.")
    m = service.meta
    return {
        "model_version": m["model_version"], "architecture": m["architecture"],
        "trained_at": m["trained_at"], "data_source": m["data_source"],
        "synthetic_data": m["synthetic_data"], "window": m["window"],
        "target_unit": m["target_unit"], "target_range": m["target_range"],
        "hyperparameters": m["hyperparameters"], "metrics": m["metrics"],
        "train_range": m["train_range"], "test_curve": m["test_curve"], "loss_curve": m["loss_curve"],
        "features": [{"key": f.key, "label": f.label, "unit": f.unit, "min": f.min, "max": f.max,
                      "default": f.default} for f in FEATURES],
    }


@router.get("/model/sample")
def sample_window():
    """A real held-out 72-hour window (plus the true next value) for the 'try an example' button."""
    if not service.loaded:
        raise HTTPException(503, "Model not loaded.")
    return {"keys": [f.key for f in FEATURES], **service.meta["sample"]}
