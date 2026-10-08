"""Parse an uploaded CSV of hourly sensor readings into validated rows."""
from __future__ import annotations

import csv
import io

from pydantic import ValidationError

from .features import FEATURES
from .schemas import Reading


class CsvError(ValueError):
    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.details = details or []


def _norm(h: str) -> str:
    return h.strip().lower().replace(" ", "_").replace("-", "_")


def parse_csv(raw: bytes) -> list[dict]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvError("File must be UTF-8 encoded text (CSV).")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CsvError("CSV is empty or has no header row.")

    headers = {_norm(h): h for h in reader.fieldnames if h}
    colmap, missing = {}, []
    for f in FEATURES:
        src = next((headers[a] for a in f.csv_aliases if a in headers), None)
        if src is None:
            missing.append(f"{f.key} (accepted headers: {', '.join(f.csv_aliases)})")
        else:
            colmap[f.key] = src
    if missing:
        raise CsvError("CSV is missing required column(s).", missing)

    rows, errors = [], []
    for n, rec in enumerate(reader, start=2):          # header is line 1
        try:
            candidate = {k: float(str(rec[src]).strip()) for k, src in colmap.items()}
            rows.append(Reading(**candidate).model_dump())
        except (ValueError, TypeError, KeyError):
            errors.append(f"line {n}: non-numeric or empty value")
        except ValidationError as e:
            for err in e.errors():
                errors.append(f"line {n}: {err['loc'][0]} - {err['msg']}")
        if len(errors) >= 20:
            errors.append("... (stopped after 20 errors)")
            break
    if errors:
        raise CsvError("CSV contains invalid values.", errors)
    if not rows:
        raise CsvError("CSV has a header but no data rows.")
    return rows
