"""Experiment with exact held-frame reuse and previous-frame RGB residuals."""

import argparse
from contextlib import closing
from hashlib import sha256
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import zlib

import numpy as np
from PIL import Image


def png(pixels, size):
    with io.BytesIO() as file:
        Image.frombytes("RGB", size, pixels).save(file, format="PNG", compress_level=3)
        return file.getvalue()


def xor(left, right):
    return np.bitwise_xor(np.frombuffer(left, dtype=np.uint8),
                          np.frombuffer(right, dtype=np.uint8)).tobytes()


def raw_frames(file, size):
    length = size[0]*size[1]*3
    while chunk := file.read(length):
        if len(chunk) != length:
            raise ValueError("Truncated RGB frame")
        yield chunk


def pack(source, target, size, mode, interval):
    if target.exists():
        raise FileExistsError(target)
    if mode not in {"png","dedup","delta"}:
        raise ValueError("Unknown archive mode")
    if len(size) != 2 or not all(1 <= n <= 4096 for n in size) or not 1 <= interval <= 120:
        raise ValueError("Frame dimensions or keyframe interval outside supported bounds")
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=".frame-cache-") as folder:
        staged = Path(folder)/"archive.sqlite3"
        counts = {}
        with closing(sqlite3.connect(staged)) as conn, source.open("rb") as raw, conn:
            conn.execute("CREATE TABLE format (width INTEGER, height INTEGER, mode TEXT, interval INTEGER, frame_count INTEGER)")
            conn.execute("INSERT INTO format VALUES (?, ?, ?, ?, 0)",(*size,mode,interval))
            conn.execute("""CREATE TABLE frames (
                id INTEGER PRIMARY KEY, kind TEXT, digest TEXT, payload BLOB, base INTEGER)""")
            owned = {}
            previous = None
            for i, frame in enumerate(raw_frames(raw, size)):
                digest = sha256(frame).hexdigest()
                base = None
                if mode == "dedup" and digest in owned:
                    kind, data, base = "reference", b"", owned[digest]
                elif mode == "delta" and i % interval and frame == previous:
                    kind, data = "hold", b""
                else:
                    kind, data = "png", png(frame, size)
                    if mode == "delta" and i % interval:
                        residual = zlib.compress(xor(previous, frame), level=3)
                        if len(residual) < len(data):
                            kind, data = "delta", residual
                    if mode == "dedup":
                        owned[digest] = i
                conn.execute("INSERT INTO frames VALUES (?, ?, ?, ?, ?)",(i,kind,digest,data,base))
                counts[kind] = counts.get(kind,0)+1
                previous = frame
            if not counts:
                raise ValueError("No input frames")
            conn.execute("UPDATE format SET frame_count=?",(i+1,))
        target.hardlink_to(staged)
    return counts


def read_format(conn):
    width,height,mode,interval,frame_count = conn.execute("SELECT * FROM format").fetchone()
    if not (1 <= width <= 4096 and 1 <= height <= 4096 and mode in {"png","dedup","delta"} and 1 <= interval <= 120 and frame_count > 0):
        raise ValueError("Invalid cache format")
    return (width,height),mode,interval,frame_count


def read_pixels(record, size, previous=None):
    frame,kind,digest,data,base = record
    length = size[0]*size[1]*3
    if kind == "png":
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or image.size != size or image.mode != "RGB":
                raise ValueError("Invalid PNG base")
            pixels = image.tobytes()
    elif previous is not None and kind == "delta":
        inflater = zlib.decompressobj()
        residual = inflater.decompress(data, length+1)
        if len(residual) != length or not inflater.eof or inflater.unused_data:
            raise ValueError("Invalid RGB residual")
        pixels = xor(previous,residual)
    elif previous is not None and kind in {"hold","reference"} and data == b"":
        pixels = previous
    else:
        raise ValueError(f"Unusable frame record {frame}: {kind}")
    if sha256(pixels).hexdigest() != digest:
        raise ValueError(f"Frame {frame} failed its SHA-256 check")
    return pixels


def reference(conn, record, size):
    index = record[-1]
    if type(index) is not int or not 0 <= index < record[0]:
        raise ValueError("Invalid frame reference")
    base = conn.execute("SELECT * FROM frames WHERE id=? AND kind='png'",(index,)).fetchone()
    if base is None:
        raise ValueError("Referenced base frame is missing")
    return read_pixels(record,size,read_pixels(base,size))


def decode(archive, index=None):
    with closing(sqlite3.connect(archive.resolve().as_uri()+"?mode=ro",uri=True)) as conn:
        size,mode,interval,frame_count = read_format(conn)
        if index is None:
            rows = conn.execute("SELECT * FROM frames ORDER BY id")
            first = 0
        else:
            if not 0 <= index < frame_count:
                raise ValueError("Frame index is outside the archive")
            first = index
            if mode == "delta":
                base = conn.execute("""SELECT max(id) FROM frames
                                      WHERE id BETWEEN ? AND ? AND kind='png'""",
                                    (max(0,index-interval+1),index)).fetchone()[0]
                if base is None:
                    raise ValueError("Missing checkpoint")
                first = base
            rows = conn.execute("SELECT * FROM frames WHERE id BETWEEN ? AND ? ORDER BY id",(first,index))
        previous = None
        expected = first
        for record in rows:
            if record[0] != expected:
                raise ValueError("Missing frame in archive")
            previous = (reference(conn,record,size) if record[1] == "reference" else
                        read_pixels(record,size,previous))
            if index is None or record[0] == index:
                yield previous
            expected += 1
        if expected != (frame_count if index is None else index+1):
            raise ValueError("Requested frames were not found")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation",required=True)
    encode = sub.add_parser("pack")
    encode.add_argument("source",type=Path)
    encode.add_argument("archive",type=Path)
    encode.add_argument("--size",nargs=2,type=int,required=True)
    encode.add_argument("--mode",choices=("png","dedup","delta"),required=True)
    encode.add_argument("--checkpoint",type=int,default=24)
    restore = sub.add_parser("restore")
    restore.add_argument("archive",type=Path)
    restore.add_argument("output",type=Path)
    restore.add_argument("--frame",type=int,help="Restore only this zero-based frame")
    o = parser.parse_args()
    if o.operation == "pack":
        print(json.dumps(pack(o.source,o.archive,tuple(o.size),o.mode,o.checkpoint)))
    else:
        with tempfile.TemporaryDirectory(dir=o.output.parent) as folder:
            staged = Path(folder)/"restored.rgb"
            with staged.open("wb") as stream:
                for pixels in decode(o.archive,o.frame):
                    stream.write(pixels)
            o.output.hardlink_to(staged)


if __name__ == "__main__":
    main()
