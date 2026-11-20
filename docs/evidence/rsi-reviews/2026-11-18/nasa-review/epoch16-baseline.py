"""Read back two synthetic EPOCH16 records using the pinned LASP release."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

wheel = Path(sys.argv[1])
if hashlib.sha256(wheel.read_bytes()).hexdigest() != "54d3f525651e9293b65a71b29b6b0b737cfe8e8f2a9191dcb686d261b77fc4f1":
    raise ValueError("version mismatch")
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(root/"pkg")
    sys.path.insert(0,str(root/"pkg"))
    from cdflib import CDF, cdfwrite
    import numpy as np
    expected=np.array([complex(63810000000,234567890123),complex(63810000001,345678901234)])
    checks=[]
    for level in (0,6):
        path=root/f"epoch16-{level}.cdf"
        with cdfwrite.CDF(path) as writer:
            writer.write_var(dict(Variable="Epoch", Data_Type=32, Num_Elements=1,
                                  Rec_Vary=True, Dim_Sizes=[], Compress=level),var_data=expected)
        values=CDF(path).varget("Epoch")
        checks.append(dict(compression=level,expected_records=len(expected),actual_records=len(values),
                           exact=np.array_equal(values,expected),values=[[v.real,v.imag] for v in values]))
print(json.dumps(checks,indent=2))
