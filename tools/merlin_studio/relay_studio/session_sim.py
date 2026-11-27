"""Run an illustrative recording session through the modeled audio chip."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import wave

import numpy as np
from scipy.signal import butter, sosfilt

from chip_study import RATE, mix_banked, mix_reference, read, scenario, LAYOUTS


SECONDS=4
Q23=1<<23


def pcm16(signal):
    return np.rint(np.clip(signal,-1,32767/32768)*32768).astype(np.int64)


def simulated_adc():
    t=np.arange(SECONDS*RATE)/RATE
    active=np.clip((t-.24)*25,0,1)*np.clip((2.15-t)*20,0,1)
    voice=(np.sin(2*np.pi*220*t)+.21*np.sin(2*np.pi*447*t))*active*.068
    stereo=np.stack((voice,voice*.92),axis=-1)
    return pcm16(stereo)


def timeline(stems):
    duration=SECONDS*RATE
    clips=[]
    for id,stereo in enumerate(stems):
        result=np.zeros((duration,2),dtype=np.int64)
        source_start=RATE//20+id*240
        offset=id*360
        count=min(duration-offset,len(stereo)-source_start)
        if count>0:
            result[offset:offset+count]=stereo[source_start:source_start+count]
        clips.append(result)
    return clips


def effects(track,amount_db):
    high=butter(1,2800,btype="highpass",fs=RATE,output="sos")
    shelf=10**(amount_db/20)-1
    signal=track/32768
    return pcm16(signal+shelf*sosfilt(high,signal,axis=0))


def run(stems,out):
    recorded=simulated_adc()
    takes=timeline([read(p) for p in stems])
    takes.append(recorded)
    processed=[effects(take,1.5 if i%2==0 else -1.5) for i,take in enumerate(takes)]
    pan=np.linspace(-.28,.28,len(takes))[:,None]
    gain=np.rint(Q23*.64*np.concatenate((1-.5*pan,1+.5*pan),axis=1)).astype(np.int64)
    expected=mix_reference(processed,gain)
    accum=mix_banked(processed,gain,128,4)
    if not np.array_equal(accum,expected):
        raise RuntimeError("The virtual session did not match the reference mixer")
    muted=processed.copy()
    muted[-1]=np.zeros_like(recorded)
    difference=int(np.max(np.abs(accum-mix_banked(muted,gain,128,4))))
    if difference==0:
        raise RuntimeError("The microphone take did not reach the master output")
    raw=accum/Q23
    peak=float(np.max(np.abs(raw)))
    gain=min(1,30000/max(1,peak))
    pcm=np.rint(raw*gain).astype("<i2")
    with out.open("xb") as stream, wave.open(stream,"wb") as w:
        w.setparams((2,2,RATE,0,"NONE","not compressed"));w.writeframes(pcm.tobytes())
    report={"virtual_microphone_samples":len(recorded),"soundfont_stems":len(stems),"session_tracks":len(takes),
            "fps_audio":RATE,"frames":len(pcm),"sample_peak":int(np.max(np.abs(pcm))),
            "reference_accumulator_exact":True,"muted_mic_control_changes_output":True,
            "pcm_sha256":sha256(pcm.tobytes()).hexdigest(),
            "scheduling":scenario(LAYOUTS[1],len(takes),128),
            "stages":["virtual ADC","clip trim and placement","track presence effect","pan and gain",
                      "banked Q23 sum","master level","PCM WAV export"],
            "scope":"Digital simulation of a session path. Presence filter is illustrative and not the browser filter implementation."}
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path)
    p.add_argument("stems",type=Path,nargs="+")
    opts=p.parse_args()
    if not 1<=len(opts.stems)<=47:
        p.error("Use one to 47 external stems; the simulator adds a virtual take")
    run(opts.stems,opts.output)
