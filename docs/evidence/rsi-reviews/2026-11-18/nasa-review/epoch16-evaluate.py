"""Single-process suite. Run in a fresh process on each pinned isolated tree."""
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import time

import cdflib
from cdflib import CDF, cdfwrite
import numpy as np


def measure():
    path=Path(__file__).with_name('epoch16-protocol.json')
    spec=json.loads(path.read_bytes())
    results=[]
    start=time.perf_counter()
    with tempfile.TemporaryDirectory() as folder:
        for case in ('training','heldout_scalar','heldout_list','heldout_2d','unchanged_integer'):
            pairs=np.asarray(spec[case])
            if case=='unchanged_integer':
                values=pairs.astype(np.int32)
                argument=values
                data_type=4
            else:
                values=pairs[...,0]+1j*pairs[...,1]
                argument=values[0] if case=='heldout_scalar' else values.tolist() if case=='heldout_list' else values
                data_type=32
            for level in spec['compression']:
                filename=Path(folder)/f'{case}-{level}.cdf'
                row={'case':case,'compression':level}
                try:
                    with cdfwrite.CDF(filename) as writer:
                        writer.write_var(dict(Variable='Science',Data_Type=data_type,Num_Elements=1,Rec_Vary=True,
                                              Dim_Sizes=list(values.shape[1:]),Compress=level),var_data=argument)
                    reader=CDF(filename)
                    out=reader.varget('Science')
                    row.update(shape=list(out.shape),lastrec=int(reader.varinq('Science').Last_Rec),
                               passed=bool(values.dtype==out.dtype and np.array_equal(values,out)
                               and reader.varinq('Science').Last_Rec==len(values)-1))
                except (TypeError,ValueError,IndexError,AttributeError) as exc:
                    row.update(passed=False,error_type=type(exc).__name__,error_message=str(exc))
                results.append(row)
    return {'cdflib':cdflib.__version__,'writer_sha256':hashlib.sha256(Path(cdfwrite.__file__).read_bytes()).hexdigest(),
            'fixture_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'numpy':np.__version__,
            'python':platform.python_version(),'wall_seconds':round(time.perf_counter()-start,6),
            'results':results,'pass_count':sum(row['passed'] for row in results)}
if __name__=='__main__':
    print(json.dumps(measure(),indent=2))
