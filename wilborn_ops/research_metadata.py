"""Typed metadata gate for descriptive public dataset comparisons."""
from dataclasses import dataclass
from .research_ingest import Evidence
from .research_compare import compare_public_series

@dataclass(frozen=True)
class DatasetMetadata:
    source_sha256: str
    geography: str
    period: str
    population: str
    measure: str
    unit: str

    def __post_init__(self):
        if any(not isinstance(v,str) or not v.strip() or len(v)>128
               for v in (self.source_sha256,self.geography,self.period,
                         self.population,self.measure,self.unit)):
            raise ValueError("complete dataset metadata required")
        if len(self.source_sha256)!=64 or any(c not in "0123456789abcdef" for c in self.source_sha256):
            raise ValueError("invalid evidence hash")

def compare_with_metadata(left: Evidence, right: Evidence, left_meta: DatasetMetadata,
                          right_meta: DatasetMetadata, column: str):
    if not isinstance(left_meta,DatasetMetadata) or not isinstance(right_meta,DatasetMetadata):
        raise TypeError("typed metadata required")
    if left.sha256 != left_meta.source_sha256 or right.sha256 != right_meta.source_sha256:
        raise PermissionError("metadata/evidence hash mismatch")
    fields=("geography","period","population","measure","unit")
    mismatches=[field for field in fields
                if getattr(left_meta,field)!=getattr(right_meta,field)]
    if mismatches:
        return {
            "data_class":"public_research",
            "comparable":False,
            "mismatched_dimensions":mismatches,
            "difference_of_means":None,
            "claims_verified":0,
            "warning":"Comparison blocked due to incompatible dataset metadata.",
        }
    result=compare_public_series(left,right,column,unit=left_meta.unit,comparable=True)
    result["comparable"]=True
    result["mismatched_dimensions"]=[]
    result["metadata_assurance"]="caller-supplied, not independently verified"
    return result
