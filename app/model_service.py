"""Loads the trained network once and turns raw sensor windows into predictions."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from .features import FEATURES, FEATURE_KEYS

log = logging.getLogger("soilp.model")


class ModelNotLoaded(RuntimeError):
    pass


class WindowTooShort(ValueError):
    pass


class ModelService:
    def __init__(self) -> None:
        self.meta: dict[str, Any] | None = None
        self._explain = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ loading
    @property
    def loaded(self) -> bool:
        return self._explain is not None and self.meta is not None

    @property
    def window(self) -> int:
        return int(self.meta["window"]) if self.meta else 0

    def load(self, artifact_dir: Path) -> None:
        model_path, meta_path = artifact_dir / "model.keras", artifact_dir / "metadata.json"
        if not (model_path.exists() and meta_path.exists()):
            log.warning("Model artifacts not found in %s - run `python -m ml.train` first.", artifact_dir)
            return
        import keras
        from . import layers  # noqa: F401  (registers custom layers)

        meta = json.loads(meta_path.read_text())
        if list(meta["features"]) != list(FEATURE_KEYS):
            raise RuntimeError("metadata.json features do not match app/features.py - retrain or fix the feature table.")

        model = keras.saving.load_model(model_path, compile=False)
        scores = model.get_layer("attention_scores").output
        self._explain = keras.Model(model.input, [model.output, scores])
        self.meta = meta
        self._run(np.zeros((1, self.window, len(FEATURE_KEYS)), dtype="float32"))   # warm-up
        log.info("Loaded model %s (window=%d)", meta["model_version"], self.window)

    # --------------------------------------------------------------- inference
    def _run(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        with self._lock:
            pred, att = self._explain(x, training=False)
        return np.asarray(pred).reshape(len(x)), np.asarray(att).reshape(len(x), -1)

    def _check_range(self, raw: np.ndarray) -> list[str]:
        out = []
        for i, f in enumerate(FEATURES):
            tr = self.meta["train_range"][f.key]
            span = max(tr["max"] - tr["min"], 1e-9)
            lo, hi = tr["min"] - 0.1 * span, tr["max"] + 0.1 * span
            vmin, vmax = float(raw[:, i].min()), float(raw[:, i].max())
            if vmin < lo or vmax > hi:
                bad = vmin if vmin < lo else vmax
                out.append(f"{f.label} = {bad:.3g} {f.unit} is outside the range seen in training "
                           f"({tr['min']:.3g}-{tr['max']:.3g}); the prediction may be unreliable.")
        return out

    def predict(self, rows: np.ndarray, single_reading: bool) -> dict[str, Any]:
        """rows: (n, F) raw sensor values, oldest first. Returns prediction + explanations."""
        if not self.loaded:
            raise ModelNotLoaded("Model artifacts are not loaded.")
        t0 = time.perf_counter()
        W, F = self.window, len(FEATURE_KEYS)

        if single_reading:
            raw = np.repeat(rows[:1], W, axis=0)
        else:
            if len(rows) < W:
                raise WindowTooShort(f"At least {W} hourly rows are required; got {len(rows)}.")
            raw = rows[-W:]

        sx, sy = self.meta["scaler_x"], self.meta["scaler_y"]
        scaled = ((raw - np.array(sx["mean"])) / np.array(sx["std"])).astype("float32")

        # batch = [actual window] + [window with feature i set to its training mean] for each i
        batch = np.repeat(scaled[None], F + 1, axis=0)
        for i in range(F):
            batch[i + 1, :, i] = 0.0          # 0 in scaled space == training mean
        preds, att = self._run(batch)
        preds = preds * sy["std"] + sy["mean"]
        prediction = float(preds[0])
        effects = [{"feature": f.key, "label": f.label, "effect": float(prediction - preds[i + 1])}
                   for i, f in enumerate(FEATURES)]

        # attention is over pooled steps (MaxPool=2) -> stretch back to hourly resolution
        a = att[0]
        a = np.repeat(a, max(1, W // len(a)))[:W]
        if len(a) < W:
            a = np.pad(a, (0, W - len(a)), mode="edge")
        a = a / a.sum()

        warnings = self._check_range(raw)
        if single_reading:
            warnings.insert(0, f"Single reading repeated across the {W}-hour window (steady-state assumption). "
                               f"For best accuracy provide {W} hourly readings.")
        if self.meta.get("synthetic_data"):
            warnings.append("Model was trained on synthetic demo data - not for real agronomic decisions.")

        return {
            "prediction": prediction,
            "unit": self.meta["target_unit"],
            "attention": a.round(6).tolist(),
            "feature_effects": effects,
            "warnings": warnings,
            "model_version": self.meta["model_version"],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "input_summary": {
                "mean": {k: round(float(v), 4) for k, v in zip(FEATURE_KEYS, raw.mean(0))},
                "last": {k: round(float(v), 4) for k, v in zip(FEATURE_KEYS, raw[-1])},
            },
        }


service = ModelService()
