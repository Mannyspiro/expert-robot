"""Compose a reference-tuned score, forest ambience, effects, and narration."""

import argparse
import json
from pathlib import Path

import wave

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt


RATE=48_000
SECONDS=18
TAU=2*np.pi
FLOAT_LINES=(
    (1.05,"Follow the lanterns. The forest keeps time in a thousand small movements."),
    (9.15,"Under the roots, the old relay is still awake. Listen for the light."),
)
CHORDS=((48,55,60,63,67),(44,51,55,60,63),(46,53,57,60,62),(48,55,60,62,67))
MELODY=((0.0,72,1.18),(.9,75,.65),(1.49,79,1.62),(3.7,74,.95),(5.1,70,1.06),
        (6.24,72,1.92),(8.14,67,1.1),(9.48,75,1.15),(10.42,79,1.0),
        (11.54,82,1.5),(13.35,79,.95),(14.14,74,1.2),(15.05,72,2.7))


def t(seconds):
    return np.arange(round(RATE*seconds))/RATE


def stereo(data,pan=0):
    theta=(pan+1)*np.pi/4
    return data[:,None]*np.array([np.cos(theta),np.sin(theta)])


def add(bus,take,at,gain=1):
    start=round(at*RATE)
    n=min(len(take),len(bus)-start)
    if n>0:
        bus[start:start+n]+=take[:n]*gain


def window(times,attack,release):
    return np.minimum(1,times/attack)**1.5*np.clip((len(times)/RATE-times)/release,0,1)**1.5


def band(rng,frames,a,b):
    return sosfilt(butter(2,[a,b],btype="bandpass",fs=RATE,output="sos"),rng.normal(0,1,frames))


def echo(stem):
    dry=stem.copy()
    for delay,amount in ((.10,.10),(.19,.13),(.33,.085),(.57,.04)):
        size=round(delay*RATE)
        stem[size:]+=dry[:-size,::-1]*amount


def pitch(midi,c5):
    return c5*2**((midi-72)/12)


def score(c5):
    total=SECONDS*RATE
    music=np.zeros((total,2))
    for ci,chord in enumerate(CHORDS):
        for i,n in enumerate(chord):
            time=t(4.90)
            tone=pitch(n,c5)
            phi=TAU*tone*time
            wavelet=np.sin(phi)+.28*np.sin(phi*2.002)+.12*np.sin(phi*3*.998)
            wavelet*=window(time,.75,.95)*(.87+.13*np.sin(TAU*.61*time+i))
            add(music,stereo(wavelet,(-1)**i*.39),ci*4.26,.064 if i else .08)
    for i,(at,n,length) in enumerate(MELODY):
        clock=t(length)
        fundamental=pitch(n,c5)
        phi=TAU*fundamental*clock
        note=(np.sin(phi)+.61*np.sin(2.006*phi)*np.exp(-clock/1.0)
              +.20*np.sin(3.982*phi)*np.exp(-clock/.19))
        note*=window(clock,.031,.48)*np.exp(-clock/2.2)
        add(music,stereo(note,(-1)**i*.16),at,.118)
    echo(music)
    return music


def sound_design():
    rng=np.random.default_rng(88)
    length=SECONDS*RATE
    times=t(SECONDS)
    env=window(times,.50,1.08)
    wind=np.zeros((length,2))
    for side in range(2):
        leafy=band(rng,length,105,800)*(.27+.17*np.sin(TAU*.21*times+side))
        leafy+=.36*band(rng,length,660,4400)*(.32+.25*np.sin(TAU*.39*times+side))
        wind[:,side]=leafy*env*.17
    fx=np.zeros_like(wind)
    for i,at in enumerate((.21,4.4,6.58,12.07,13.08,15.27)):
        u=t(.34)
        crack=band(rng,len(u),380,7800)*np.exp(-u/.047)
        damp=band(rng,len(u),140,940)*np.exp(-u/.12)
        add(fx,stereo((crack+.6*damp)*window(u,.006,.08),(-1)**i*.45),at,.12)
    for i,at in enumerate((.8,3.7,7.5,12.4)):
        u=t(.43)
        phi=TAU*(1190*u+680*u*u-1170*u**3)
        chirp=(np.sin(phi)+.31*np.sin(phi*2))*window(u,.049,.135)
        add(fx,stereo(chirp,(-1)**i*.67),at,.047)
    u=t(2.60)
    ring=(np.sin(TAU*528*u)+.34*np.sin(TAU*792*u)+.1*np.sin(TAU*1320.4*u))
    add(fx,stereo(ring*window(u,.28,1.25)*np.exp(-u/2)),14.10,.067)
    echo(fx)
    return wind,fx


def speech(models):
    from kokoro_onnx import Kokoro
    engine=Kokoro(str(models/"kokoro-v1.0.int8.onnx"),str(models/"voices-v1.0.bin"))
    voice=np.zeros((SECONDS*RATE,2))
    cues=[]
    for start,line in FLOAT_LINES:
        signal,hz=engine.create(line,voice="af_heart",speed=.97,lang="en-us")
        samples=resample_poly(signal,RATE,hz)
        if start+len(samples)/RATE>SECONDS:
            raise ValueError("Narration exceeds the cut")
        samples*=.38/max(.0001,float(np.max(np.abs(samples))))
        add(voice,stereo(samples),start)
        cues.append({"start":start,"end":round(start+len(samples)/RATE,3),"text":line})
    return voice,cues


def write(path,data):
    if not np.isfinite(data).all() or np.max(np.abs(data))>=1:
        raise ValueError("PCM exceeds the available range")
    with wave.open(str(path),"wb") as wav:
        wav.setparams((2,2,RATE,0,"NONE","not compressed"))
        wav.writeframes(np.rint(data*32767).astype("<i2").tobytes())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("models",type=Path)
    p.add_argument("output",type=Path)
    o=p.parse_args()
    o.output.mkdir(parents=True,exist_ok=False)
    music=score(528.)
    standard=score(440*2**((72-69)/12))
    voice,cues=speech(o.models)
    ambience,effects=sound_design()
    identity={"voice":"af_heart","sample_rate":RATE,"timeline_seconds":SECONDS,"score_C5_hz":528.0,
              "comparison_C5_hz":440*2**((72-69)/12),"comparison_A4_hz":440.0,
              "tuned_A4_hz":pitch(69,528),"cues":cues,
              "tuning_scope":"Equal temperament anchored at C5. Pitch is artistic, not a biological intervention."}
    times=t(SECONDS)
    duck=np.ones(len(times))*.82
    for cue in cues:
        attack=np.clip((times-cue["start"]+.28)/.28,0,1)
        release=np.clip((cue["end"]+.47-times)/.47,0,1)
        duck-=.57*np.minimum(attack,release)
    mix=music*duck[:,None]+voice+ambience+effects
    identity["score_duck_gain_range"]=[float(duck.min()),float(duck.max())]
    gain=.84/max(np.max(np.abs(mix)),np.max(np.abs(standard)),np.max(np.abs(music)))
    for name,data in (("Forest_Mix_528",mix),("Score_C5_528",music),("Score_A4_440",standard),
                      ("Narration",voice),("Canopy_Ambience",ambience),("Forest_and_Relay_FX",effects)):
        write(o.output/(name+".wav"),data*gain)
    (o.output/"Sound_Cues.json").write_text(json.dumps(identity,indent=2)+"\n")


if __name__=="__main__":
    main()
