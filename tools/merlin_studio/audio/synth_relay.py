"""Render an original synth score, formant vocals and sci-fi Foley."""

import argparse
import json
from pathlib import Path
import wave

import numpy as np
from scipy.signal import butter, sosfilt


RATE = 48000
TAU = 2*np.pi
VOWELS = {
    "ah": (790, 1290, 2600), "ee": (320, 2210, 3010),
    "ih": (420, 1870, 2800), "uh": (560, 1410, 2480),
    "oh": (490, 890, 2590), "oo": (340, 820, 2450),
    "ai": (730, 1320, 2690), "ay": (520, 1910, 2760),
    "au": (750, 1180, 2540),
}
TARGET = {"ai":"ee","ay":"ee","au":"oo"}


def clock(seconds):
    return np.arange(round(seconds*RATE),dtype=np.float64)/RATE


def envelope(t, attack, release):
    end = len(t)/RATE
    return np.sin(np.pi*.5*np.clip(t/attack,0,1))**2 * np.sin(np.pi*.5*np.clip((end-t)/release,0,1))**2


def freq(midi):
    return 440*2**((midi-69)/12)


def stereo(signal, pan=0):
    theta=(pan+1)*np.pi/4
    return signal[:,None]*np.array([np.cos(theta),np.sin(theta)])


def place(bus, clip, time, gain=1):
    at=round(time*RATE)
    count=min(len(clip),len(bus)-at)
    if count>0:
        bus[at:at+count]+=clip[:count]*gain


def echo(bus, patterns):
    dry=bus.copy()
    for time,gain in patterns:
        offset=round(time*RATE)
        bus[offset:]+=dry[:-offset,::-1]*gain


def noise(rng, t, low, high):
    sos=butter(2,[low,high],btype="bandpass",fs=RATE,output="sos")
    return sosfilt(sos,rng.normal(0,1,len(t)))


def lead_voice(midi,length,vowel,word,rng,transpose=0):
    t=clock(length)
    f=freq(midi+transpose)*(1-.018*np.exp(-t/.045))*(1+.007*np.sin(TAU*5.45*t)*np.clip((t-.13)/.34,0,1))
    phase=TAU*np.cumsum(f)/RATE
    base=np.array(VOWELS[vowel])
    finish=np.array(VOWELS[TARGET.get(vowel,vowel)])
    w=np.clip((t/length-.62)/.34,0,1)
    bands=base[:,None]+(finish-base)[:,None]*w
    result=np.zeros_like(t)
    for h in range(1,22):
        centers=f*h
        resonance=np.exp(-.5*((centers-bands[0])/130)**2)
        resonance+=.72*np.exp(-.5*((centers-bands[1])/185)**2)
        resonance+=.27*np.exp(-.5*((centers-bands[2])/220)**2)
        result+=np.sin(h*phase+.25*h)*(.21+resonance)/h**.87
    e=envelope(t,.025,.105)
    result*=e
    if word:
        air=noise(rng,t,1100,6500)
        inlet=np.exp(-t/.027)
        outlet=np.exp(-np.maximum(0,length-t)/.032)
        result+=.09*air*(inlet+outlet)*envelope(t,.006,.018)
    return result


def score(plan,rng):
    beat=60/plan["bpm"]
    duration=plan["bars"]*4*beat+2
    shape=(round(duration*RATE),2)
    band=np.zeros(shape)
    voice=np.zeros(shape)
    for bar in range(plan["bars"]):
        start=bar*4*beat
        chord=plan["progression"][bar%len(plan["progression"])]
        t=clock(4*beat+.22)
        for index,note in enumerate(chord[1:]):
            f=freq(note)
            pad=np.sin(TAU*f*.998*t)+.48*np.sin(TAU*f*1.004*t)+.16*np.sin(TAU*f*2*t)
            pad*=envelope(t,.18,.44)*(.9+.1*np.sin(TAU*.5*t+index))
            place(band,stereo(pad,(index-1.5)*.44),start,.052)
        pluck=clock(beat*.31)
        for i in range(8):
            f=freq(chord[1+(i+bar)%4]+12)
            signal=(np.sin(TAU*f*pluck)+.44*np.sin(TAU*f*2.003*pluck))*np.exp(-pluck/.105)
            place(band,stereo(signal*envelope(pluck,.002,.04),(-1)**i*.56),start+i*beat*.5,.064)
        for i in range(4):
            if bar>0:
                t=clock(beat*.93)
                f=freq(chord[0]+(12 if i==3 and bar>3 else 0))
                low=(np.sin(TAU*f*t)+.24*np.sin(TAU*2*f*t))*envelope(t,.026,.08)
                place(band,stereo(low),start+i*beat,.17)
            if bar>1:
                t=clock(.20)
                kick=np.sin(TAU*(48*t+2.2*(1-np.exp(-t/.025))))*np.exp(-t/.054)
                place(band,stereo(kick),start+i*beat,.27 if i in (0,2) else .14)
                if i in (1,3):
                    snap=noise(rng,t,850,6500)*np.exp(-t/.033)+.19*np.sin(TAU*178*t)*np.exp(-t/.028)
                    place(band,stereo(snap, -.08),start+i*beat,.28)
                hat=noise(rng,t,5100,14000)*np.exp(-t/.021)
                place(band,stereo(hat,.42),start+(i+.5)*beat,.14)
    for start,length,note,word,vowel in plan["vocal"]:
        main=lead_voice(note,length*beat,vowel,word,rng)
        place(voice,stereo(main),start*beat,.48)
        if start>=32:
            harmony=lead_voice(note,length*beat,vowel,word,rng,transpose=-12)
            place(voice,stereo(harmony,-.41),start*beat+.014,.13)
    echo(voice,[(.078,.14),(.161,.12),(.263,.09),(.417,.035)])
    echo(band,[(.187,.075),(.303,.045)])
    tail=clock(duration)
    tail=np.clip((duration-tail)/1.8,0,1)[:,None]
    return band*tail,voice*tail


def effects(rng):
    t=clock(.52)
    latch=noise(rng,t,850,7800)*np.exp(-t/.024)
    latch+=.48*np.sin(TAU*415*t)*np.exp(-t/.061) + .2*np.sin(TAU*880*t)*np.exp(-t/.039)
    yield "01_Relay_Latch",stereo(latch*envelope(t,.002,.08)),.65
    t=clock(1.85)
    phase=TAU*(120*t+310*t*t)
    path=(.54*np.sin(phase)+.17*np.sin(2.013*phase)+.45*noise(rng,t,210,3500))*envelope(t,.51,.44)
    yield "02_Cooling_Path_Surge",stereo(path,.16),.68
    t=clock(1.5)
    beep=(np.sin(TAU*831*t)+.35*np.sin(TAU*1245*t))*np.maximum(0,np.sin(TAU*2.4*t))**4
    yield "03_Warning_Pulses",stereo(beep*envelope(t,.009,.18)),.5
    t=clock(2.3)
    hum=(np.sin(TAU*58*t)+.21*np.sin(TAU*116.6*t)+.35*noise(rng,t,35,155))*(.81+.19*np.sin(TAU*4.8*t))
    yield "04_Relay_Rumble",stereo(hum*envelope(t,.14,.50),-.1),.58
    t=clock(1.25)
    signal=np.sin(TAU*659.25*t)*np.exp(-t/.25)
    signal+=.74*np.sin(TAU*987.77*t)*np.exp(-t/.37)*np.clip((t-.13)/.028,0,1)
    yield "05_Stabilized_Chime",stereo(signal*envelope(t,.004,.27)),.62
    t=clock(2.15)
    wipe=noise(rng,t,420,6100)*envelope(t,.97,1.17)
    wipe+=.5*np.sin(TAU*(64*t+76*t*t))*envelope(t,.46,.88)
    yield "06_Violet_Transition",stereo(wipe,-.17),.58


def write(path, data):
    if not np.isfinite(data).all() or np.max(np.abs(data))>=1:
        raise ValueError("Invalid or clipped audio")
    with wave.open(str(path),"wb") as out:
        out.setparams((2,2,RATE,0,"NONE","not compressed"))
        out.writeframes(np.rint(data*32767).astype("<i2").tobytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    plan=json.loads(args.score.read_text(encoding="utf-8"))
    rng=np.random.default_rng(13918)
    instrument,vocals=score(plan,rng)
    gain=.83/max(np.max(np.abs(instrument+vocals)),np.max(np.abs(instrument)),np.max(np.abs(vocals)))
    write(args.output/"Two_Ways_Out_Full_Mix.wav",(instrument+vocals)*gain)
    write(args.output/"Two_Ways_Out_Instrumental.wav",instrument*gain)
    write(args.output/"Two_Ways_Out_Vocal_Stem.wav",vocals*gain)
    for name,data,peak in effects(rng):
        write(args.output/(name+".wav"),data*(peak/np.max(np.abs(data))))


if __name__=="__main__":
    main()
