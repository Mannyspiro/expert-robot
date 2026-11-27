"""Serve the verified Merlin USB payload to a loopback OpenBot daemon.

Run using the portable Python and dependencies unpacked by START_OS.sh.
"""

import argparse
import ctypes
from http.server import HTTPServer
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Merlin_Chip_USB from the verified image")
    parser.add_argument("runtime", type=Path, help="Unpacked runtime cache directory")
    parser.add_argument("--port", type=int, default=18961)
    args = parser.parse_args()
    bundle = args.bundle.resolve(strict=True)
    sys.path.insert(0, str(bundle / "simulator"))
    import usb

    library = usb.kernel_file(args.runtime.resolve(strict=True), "auto")
    dll = ctypes.CDLL(str(library))
    dll.set_kernel_threads.argtypes = [ctypes.c_int]
    dll.set_kernel_threads.restype = None
    dll.set_kernel_threads(4)
    model = usb.verified_model(usb.MODEL)
    fit = usb.fit_layouts(bundle / "simulator" / "Cell_Results.json")["tetrahedral"]
    usb.studio.MAX_CONTEXT = 1536
    usb.studio.MAX_OUTPUT = 192
    provider, _engine, _tokenizer = usb.setup_engine(args, fit, model, library)
    handler = provider.RequestHandlerClass
    provider.server_close()
    with HTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Merlin USB inference provider on 127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
