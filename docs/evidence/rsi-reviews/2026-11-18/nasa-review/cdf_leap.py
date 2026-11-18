"""Run with Python, numpy and a local wheel matching the PyPI attestation."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
import zipfile

WHEEL_SHA256 = '54d3f525651e9293b65a71b29b6b0b737cfe8e8f2a9191dcb686d261b77fc4f1'


def measure(wheel):
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != WHEEL_SHA256:
        raise ValueError('Unexpected wheel digest')
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(root/'pkg')
        sys.path.insert(0, str(root/'pkg'))
        from cdflib import CDF, cdfepoch, cdfwrite
        import cdflib
        import numpy as np

        groups = {
            'development': ([[2016,12,30,12,0,0,0,0,i] for i in (0,1)], [1]),
            'held_out': ([[2016,12,31,23,59,59,999,999,999],
                          [2016,12,31,23,59,60,0,0,0],
                          [2016,12,31,23,59,60,999,999,999],
                          [2017,1,1,0,0,0,0,0,0],[2017,1,1,0,0,0,0,0,1]], [1,999999999,1,1])
        }
        results = {}
        for name,(components,expected) in groups.items():
            raw = cdfepoch.compute_tt2000(components)
            path = root / (name+'.cdf')
            with cdfwrite.CDF(path) as writer:
                writer.write_var({'Variable':'Epoch','Data_Type':33,'Num_Elements':1,
                                  'Rec_Vary':True,'Dim_Sizes':[]}, var_data=raw)
            recovered = CDF(path).varget('Epoch')
            projected = cdfepoch.to_datetime(recovered)
            results[name] = {'records':len(recovered),'expected_deltas':expected,
                'measured_deltas':np.diff(recovered).tolist(),
                'roundtrip':raw.dtype==recovered.dtype and raw.tobytes()==recovered.tobytes(),
                'distinct_raw':len(np.unique(recovered)),'distinct_projection':len(np.unique(projected)),
                'projected_values':[str(v) for v in projected],
                'oracle_pass':np.diff(recovered).tolist()==expected}
        return {'wheel_sha256':WHEEL_SHA256,'source_commit':'cf7553fe93c0684ae461fffb1df0a0b9daa23219',
                'protocol_sha256':hashlib.sha256(Path(__file__).with_name('protocol.json').read_bytes()).hexdigest(),
                'python':platform.python_version(),'numpy':np.__version__,'cdflib':cdflib.__version__,
                'wall_seconds':round(time.perf_counter()-started,6),'results':results}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel',type=Path)
    print(json.dumps(measure(parser.parse_args().wheel),indent=2))
