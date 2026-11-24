"""Small bounded numeric CSV analysis over public research evidence only."""
import csv
import io
import math
from statistics import mean,median
from .research_ingest import Evidence,MAX_BYTES

MAX_ROWS=1000
MAX_COLUMNS=32

def analyze_numeric_csv(evidence, column):
    if not isinstance(evidence,Evidence) or evidence.data_class!="public_research":
        raise PermissionError("public research evidence required")
    if not isinstance(column,str) or not column:
        raise ValueError("column required")
    if evidence.bytes>MAX_BYTES:
        raise ValueError("evidence exceeds limit")
    reader=csv.DictReader(io.StringIO(evidence.text))
    fields=reader.fieldnames
    if not fields or len(fields)>MAX_COLUMNS or len(fields)!=len(set(fields)):
        raise ValueError("invalid CSV headers")
    if column not in fields:
        raise KeyError(column)
    values=[]
    missing=0
    rows=0
    for row in reader:
        rows+=1
        if rows>MAX_ROWS:
            raise ValueError("row limit exceeded")
        if None in row or any(key is None for key in row):
            raise ValueError("ragged CSV")
        raw=row[column].strip()
        if not raw:
            missing+=1
            continue
        try:
            value=float(raw)
        except ValueError as exc:
            raise ValueError("non-numeric value") from exc
        if not math.isfinite(value):
            raise ValueError("non-finite value")
        values.append(value)
    return {
        "data_class":"public_research",
        "source_sha256":evidence.sha256,
        "column":column,
        "rows":rows,
        "valid_count":len(values),
        "missing_count":missing,
        "mean":mean(values) if values else None,
        "median":median(values) if values else None,
        "min":min(values) if values else None,
        "max":max(values) if values else None,
        "units":"unspecified",
        "claims_verified":0,
    }
