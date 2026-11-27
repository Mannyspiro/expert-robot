"""Export the original vocal score to standard MIDI, preserving lyric events."""

import argparse
import json
from pathlib import Path
import struct


DIVISION = 480


def variable(value):
    if not 0<=value<2**28:
        raise ValueError("MIDI delta is out of bounds")
    blocks=[value&127]
    while value>127:
        value >>= 7
        blocks.append((value&127)|128)
    return bytes(reversed(blocks))


def meta(kind,text):
    raw=text.encode("utf-8")
    return bytes((255,kind))+variable(len(raw))+raw


def track(events):
    time=0
    out=bytearray()
    for tick,_,data in sorted(events):
        out.extend(variable(tick-time)+data)
        time=tick
    out.extend(b"\x00\xff\x2f\x00")
    return b"MTrk"+struct.pack(">I",len(out))+out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("score",type=Path)
    p.add_argument("out",type=Path)
    args=p.parse_args()
    score=json.loads(args.score.read_text(encoding="utf-8"))
    tempo=round(60_000_000/score["bpm"])
    master=track([(0,0,meta(3,score["title"])),(0,1,b"\xff\x51\x03"+tempo.to_bytes(3,"big"))])
    events=[(0,0,meta(3,"Vocal melody"))]
    for start,duration,note,lyric,_ in score["vocal"]:
        at,end=round(start*DIVISION),round((start+duration)*DIVISION)
        if lyric:
            events.append((at,1,meta(5,lyric)))
        events.extend(((at,2,bytes((144,note,92))),(end,0,bytes((128,note,0)))))
    with args.out.open("xb") as stream:
        stream.write(b"MThd"+struct.pack(">IHHH",6,1,2,DIVISION)+master+track(events))


if __name__=="__main__":
    main()
