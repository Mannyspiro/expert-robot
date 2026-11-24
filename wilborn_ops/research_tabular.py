"""Small bounded numeric CSV analysis over public research evidence only."""
import csv
import io
import math
from statistics import mean,median
from .research_ingest import DATA_CLASS,validate_evidence

MAX_ROWS=1000
MAX_COLUMNS=32

def analyze_numeric_csv(evidence, column):
    evidence=validate_evidence(evidence)
    if not isinstance(column,str) or not column:
        raise ValueError("column required")
    reader=csv.DictReader(io.StringIO(evidence.text))
    fields=reader.fieldnames
    if not fields or len(fields)>MAX_COLUMNS or len(fields)!=len(set(fields)) or any(not field.strip() for field in fields):
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
        if None in row or any(value is None for value in row.values()):
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
        "data_class":DATA_CLASS,
        "source_authenticity_verified":False,
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
