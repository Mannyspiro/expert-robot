"""Conservative comparison of bounded public research numeric summaries.

This does not establish causal effects, equivalent populations or factual truth.
"""
import math
from .research_tabular import analyze_numeric_csv
from .research_ingest import DATA_CLASS,validate_evidence

def compare_public_series(left, right, column, *, unit, comparable=False):
    left,right=validate_evidence(left),validate_evidence(right)
    if left.sha256 == right.sha256:
        raise ValueError("distinct source contents required")
    if not isinstance(unit,str) or not unit.strip() or len(unit)>64:
        raise ValueError("explicit unit required")
    if type(comparable) is not bool:
        raise ValueError("comparability must be explicit")
    a=analyze_numeric_csv(left,column)
    b=analyze_numeric_csv(right,column)
    result={
        "data_class":DATA_CLASS,
        "source_authenticity_verified":False,
        "column":column,
        "unit":unit,
        "sources":[{"url":left.url,"sha256":left.sha256,"rows":a["rows"],
                    "valid_count":a["valid_count"],"missing_count":a["missing_count"]},
                   {"url":right.url,"sha256":right.sha256,"rows":b["rows"],
                    "valid_count":b["valid_count"],"missing_count":b["missing_count"]}],
        "comparable_assumed":comparable,
        "claims_verified":0,
        "warning":"Source independence, sampling, units and population equivalence are not independently verified.",
    }
    if not comparable or not a["valid_count"] or not b["valid_count"]:
        result["difference_of_means"]=None
        result["relative_difference_percent"]=None
        result["interpretation"]="insufficient comparability or observations"
        return result
    difference=b["mean"]-a["mean"]
    if not math.isfinite(difference):
        raise ValueError("non-finite comparison")
    result["difference_of_means"]=difference
    result["relative_difference_percent"]=(difference/a["mean"]*100
                                          if a["mean"]!=0 else None)
    if result["relative_difference_percent"] is not None and not math.isfinite(result["relative_difference_percent"]):
        raise ValueError("non-finite relative difference")
    result["interpretation"]="descriptive difference only; no causal inference"
    return result
