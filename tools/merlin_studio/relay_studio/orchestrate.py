"""Arrange the original Merlin vocal score with local SoundFont instruments."""

import argparse
from contextlib import contextmanager
import ctypes as c
from ctypes.util import find_library
import json
from pathlib import Path
import sys
import wave

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"audio"))
from synth_relay import write


RATE = 48000
BANK_TRACKS = (
    ("Grand piano",0,.48,46),("Chamber strings",48,.37,73),
    ("Nylon guitar",24,.32,82),("Cello",42,.25,55),("Celesta",8,.25,89),
    ("Electric bass",33,.28,64),("Drum kit",None,.39,64),
)


def api():
    lib=c.CDLL(find_library("fluidsynth") or "libfluidsynth.so.3")
    ptr,integer=c.c_void_p,c.c_int
    signatures={
        "new_fluid_settings":(ptr,()),"delete_fluid_settings":(None,(ptr,)),
        "fluid_settings_setnum":(integer,(ptr,c.c_char_p,c.c_double)),
        "fluid_settings_setint":(integer,(ptr,c.c_char_p,integer)),
        "new_fluid_synth":(ptr,(ptr,)),"delete_fluid_synth":(None,(ptr,)),
        "fluid_synth_sfload":(integer,(ptr,c.c_char_p,integer)),
        "fluid_synth_program_select":(integer,(ptr,integer,integer,integer,integer)),
        "fluid_synth_cc":(integer,(ptr,integer,integer,integer)),
        "fluid_synth_noteon":(integer,(ptr,integer,integer,integer)),
        "fluid_synth_noteoff":(integer,(ptr,integer,integer)),
        "fluid_synth_write_float":(integer,(ptr,integer,ptr,integer,integer,ptr,integer,integer)),
    }
    for label,(result,args) in signatures.items():
        method=getattr(lib,label)
        method.restype=result
        method.argtypes=args
    return lib


@contextmanager
def synth(lib, font):
    settings=lib.new_fluid_settings()
    lib.fluid_settings_setnum(settings,b"synth.sample-rate",RATE)
    lib.fluid_settings_setnum(settings,b"synth.gain",.55)
    lib.fluid_settings_setint(settings,b"synth.chorus.active",0)
    engine=lib.new_fluid_synth(settings)
    try:
        bank=lib.fluid_synth_sfload(engine,str(font).encode(),1)
        if bank<0:
            raise ValueError("Could not load the SoundFont")
        yield engine,bank
    finally:
        lib.delete_fluid_synth(engine)
        lib.delete_fluid_settings(settings)


def render_track(lib, font, notes, preset, pan, beats, duration):
    data=np.zeros((round(duration*RATE),2),dtype=np.float32)
    ch=9 if preset is None else 0
    with synth(lib,font) as (engine,sfid):
        if lib.fluid_synth_program_select(engine,ch,sfid,128 if ch==9 else 0,preset or 0)!=0:
            raise ValueError("The General MIDI program is missing")
        lib.fluid_synth_cc(engine,ch,10,pan)
        lib.fluid_synth_cc(engine,ch,91,26 if ch!=9 else 12)
        intervals=[]
        for at,length,note,velocity in notes:
            begin=round(at*beats*RATE)
            end=round((at+length)*beats*RATE)
            intervals.extend([(begin,1,note,velocity),(end,0,note,0)])
        current=0
        for stop,on,note,velocity in sorted(intervals+[(len(data),2,0,0)]):
            count=stop-current
            base=data[current:].ctypes.data
            if count and lib.fluid_synth_write_float(engine,count,base,0,2,base,1,2)!=0:
                raise RuntimeError("FluidSynth failed to render a block")
            if on==1:
                lib.fluid_synth_noteon(engine,ch,note,velocity)
            elif on==0:
                lib.fluid_synth_noteoff(engine,ch,note)
            current=stop
    return data


def arrangement(plan):
    piano,strings,guitar,cello,celesta,bass,kit=([ ] for _ in BANK_TRACKS)
    for bar in range(plan["bars"]):
        at=bar*4
        root,*chord=plan["progression"][bar%len(plan["progression"])]
        for i in range(8):
            tone=chord[(i if i<4 else 6-i)%4]
            piano.append((at+i*.5,.43,tone,83-4*(i%2)))
        for i,note in enumerate(chord[1:]):
            strings.append((at+i*.04,3.75-i*.04,note,64+i*3))
        if bar not in {0,1,15}:
            for i,note in enumerate((chord[0],chord[2],chord[3],chord[1],chord[2],chord[3])):
                guitar.append((at+(.5,1,1.5,2.5,3,3.5)[i],.32,note+12,62+(i%2)*6))
        if bar>=2:
            cello.extend([(at,1.76,root+12,71),(at+2,1.22,chord[0]-12,64),
                          (at+3.25,.6,chord[1]-12,59)])
        if bar in {0,1,2,3,12,13,14,15}:
            for i in (0,1,3):
                celesta.append((at+i, .76, chord[i]+12,72-i*4))
        if bar in range(2,15):
            for i in (0,1.5,2,3.5):
                bass.append((at+i,.4,root+(12 if i==3.5 else 0),83 if i in (0,2) else 73))
        if bar in range(3,15):
            for i in range(8):
                kit.append((at+i*.5,.12,42,57 if i%2==0 else 41))
            for i in (0,2,2.5):
                kit.append((at+i,.15,36,93 if i!=2.5 else 61))
            for i in (1,3):
                kit.append((at+i,.17,38,83))
            if bar in (3,7,11,14):
                kit.append((at,.6,49,72))
    return piano,strings,guitar,cello,celesta,bass,kit


def read_voice(path,length):
    with wave.open(str(path),"rb") as stream:
        if (stream.getnchannels(),stream.getsampwidth(),stream.getframerate(),stream.getnframes())!=(2,2,RATE,length):
            raise ValueError("Voice stem must be aligned stereo PCM16 at 48 kHz")
        return np.frombuffer(stream.readframes(length),dtype="<i2").reshape(-1,2)/32768


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("score","soundfont","voice","output"):
        p.add_argument(name,type=Path)
    opts=p.parse_args()
    plan=json.loads(opts.score.read_text(encoding="utf-8"))
    beat=60/plan["bpm"]
    duration=plan["bars"]*4*beat+2
    opts.output.mkdir(parents=True,exist_ok=False)
    lib=api()
    stems={}
    for (name,preset,amount,pan),notes in zip(BANK_TRACKS,arrangement(plan),strict=True):
        stems[name]=render_track(lib,opts.soundfont,notes,preset,pan,beat,duration)*amount
    stems["Synthetic vocal"]=read_voice(opts.voice,round(duration*RATE))*.12
    instrument=sum(v for k,v in stems.items() if k!="Synthetic vocal")
    mix=instrument+stems["Synthetic vocal"]
    gain=.84/max(abs(mix).max(),abs(instrument).max(),*(abs(x).max() for x in stems.values()))
    write(opts.output/"Two_Ways_Out_Orchestral.wav",mix*gain)
    write(opts.output/"Two_Ways_Out_Orchestral_Instrumental.wav",instrument*gain)
    for name,data in stems.items():
        write(opts.output/(name.replace(" ","_")+".wav"),data*gain)
    print(json.dumps({"seconds":duration,"stems":list(stems),"gain":float(gain)}))


if __name__=="__main__":
    main()
