"""Independent read of TT2000 and EPOCH16 fixtures by NASA CDF via SpacePy."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile

import numpy as np


def run(writer_root, reader_wheel):
    if hashlib.sha256(reader_wheel.read_bytes()).hexdigest() != '61b160bb422e3a85dac2e5ee163d3f01112524d7f30da1d64ae839ebad7cbd27':
        raise ValueError('unexpected native distribution')
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        with zipfile.ZipFile(reader_wheel) as z:
            z.extractall(root/'reader')
        os.environ['CDF_LIB']=str(root/'reader/spacepy')
        sys.path[:0]=[str(root/'reader'),str(writer_root)]
        from spacepy import pycdf
        from cdflib import cdfwrite, cdfepoch

        binary=Path(pycdf.lib.libpath).resolve()
        if binary != (root/'reader/spacepy/libcdf.so').resolve() or pycdf.lib.version[:3] != (3,9,1):
            raise ValueError('unexpected native CDF binary')
        components=[[2016,12,31,23,59,59,999,999,999],[2016,12,31,23,59,60,0,0,0],
                    [2016,12,31,23,59,60,999,999,999],[2017,1,1,0,0,0,0,0,0],[2017,1,1,0,0,0,0,0,1]]
        tt=cdfepoch.compute_tt2000(components)
        epoch16=np.array([63810000000+234567890123j,63810000001+345678901234j])
        path=root/'native.cdf'
        with cdfwrite.CDF(path) as writer:
            for name,typ,arr in [('TT',33,tt),('E16',32,epoch16)]:
                writer.write_var(dict(Variable=name,Data_Type=typ,Num_Elements=1,
                                      Rec_Vary=True,Dim_Sizes=[],Compress=6),var_data=arr)
        split=[]
        with pycdf.CDF(str(path),readonly=True) as r:
            rt=r.raw_var('TT')[...]
            re=r.raw_var('E16')[...]
            for v in rt:
                parts=[ctypes.c_double() for _ in range(9)]
                pycdf.lib._library.breakdownTT2000(int(v),*map(ctypes.byref,parts))
                split.append([int(x.value) for x in parts])
        return dict(native_version=list(pycdf.lib.version[:3]),native_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                    writer_sha256=hashlib.sha256(Path(cdfwrite.__file__).read_bytes()).hexdigest(),
                    native_epoch16_shape=list(re.shape),native_epoch16_pair_values=re.tolist(),
                    native_epoch16_matches=np.array_equal(np.column_stack((epoch16.real,epoch16.imag)),re),
                    tt2000_exact_bytes=rt.tobytes()==tt.tobytes(), native_utc_components=split,
                    native_leap_labels_match=components==split)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('writer_root',type=Path)
    parser.add_argument('reader_wheel',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.writer_root,args.reader_wheel),indent=2))
