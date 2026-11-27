"""Compare modeled DSP layouts and run exact fixed-point stem mixing."""

import argparse
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import sys
import wave

import numpy as np


RATE=48_000
CLOCK=24_000_000
SCENARIOS=(8,24,48)
QUANTA=(64,128,256)
BUDGET_KIB=128
ROOT=Path(__file__).resolve().parents[3]
RESEARCH=ROOT/"docs/merlin/usb/source/payload/research"
LAYOUTS=(
    {"name":"Shared DSP", "lanes":1, "banks":1, "slots_per_sample":30, "base_cycles":1700, "cost":1},
    {"name":"Four-lane banked DSP", "lanes":4, "banks":4, "slots_per_sample":24, "base_cycles":2200,"cost":4},
    {"name":"Eight-lane banked DSP", "lanes":8, "banks":8, "slots_per_sample":24,"base_cycles":3200,"cost":8},
)


def scenario(layout, channels, block):
    # Slots describe the virtual instruction and SRAM schedules, not measured IPC.
    cluster=(channels+min(layout["lanes"],layout["banks"])-1)//min(layout["lanes"],layout["banks"])
    mix_cycles=layout["base_cycles"]+block*(layout["slots_per_sample"]*cluster+38)
    capacity=block*CLOCK//RATE
    scratch=(2*2*4*block*(channels+1)+channels*128)
    return {"tracks":channels,"quantum":block,"required_cycles":mix_cycles,"cycle_budget":capacity,
            "deadline_met":mix_cycles<=capacity,"load_percent":round(100*mix_cycles/capacity,2),
            "buffer_ms":round(1000*block/RATE,3),"scratch_bytes":scratch,
            "scratch_within_budget":scratch<=BUDGET_KIB*1024}


def ideonomy(research_path):
    sys.path.insert(0,str(research_path.resolve()))
    from merlin_ideonomy import enumerate_combination_report
    ideas={"serial_dsp":("compute",1),"banked_dsp":("compute",3),"wide_dsp":("compute",5),
           "double_buffer":("memory",1),"q23_accumulation":("numeric",1),"fixed_quantum":("timing",1)}
    rows=[{"id":k,"domain":domain,"estimated_cost":cost} for k,(domain,cost) in ideas.items()]
    pairs={frozenset((a,b)) for a,b in combinations(ideas,2) if ideas[a][0]!=ideas[b][0]}
    return enumerate_combination_report(rows,pairs,trigger="Mixing latency and staging SRAM compete",
        problem="Compare audio-DSP layouts under a callback budget",max_size=3,max_cost=8,limit=64,work_budget=35)


def read(path):
    with wave.open(str(path),"rb") as w:
        if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(RATE,2,2):
            raise ValueError("Use aligned stereo 48 kHz PCM16 stems")
        return np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").reshape(-1,2).astype(np.int64)


def mix_reference(stems,gains):
    desired=np.stack(stems,axis=0)
    return np.sum(desired*gains[:,None,:],axis=0,dtype=np.int64)


def mix_banked(stems,gains,quantum,lanes):
    data=np.empty_like(stems[0])
    for start in range(0,len(data),quantum):
        end=min(len(data),start+quantum)
        bins=np.zeros((lanes,end-start,2),dtype=np.int64)
        for index,(track,gain) in enumerate(zip(stems,gains,strict=True)):
            bins[index%lanes]+=track[start:end]*gain
        data[start:end]=bins.sum(axis=0,dtype=np.int64)
    return data


def validate(paths):
    stems=[read(p) for p in paths]
    gains=np.full((len(stems),2),1<<23,dtype=np.int64)
    # Use different gains and pans, including anti-phase coefficients, in the arithmetic control.
    varied=((np.arange(2*len(stems),dtype=np.int64).reshape(-1,2)*7919)%(1<<22))+(1<<20)
    varied[0,1]=-varied[0,1]
    takes=[]
    for label,c in (("unity",gains),("varied_gain_and_pan",varied)):
        exact=mix_reference(stems,c)
        for lanes,block in product((1,4,8),QUANTA):
            custom=mix_banked(stems,c,block,lanes)
            if not np.array_equal(exact,custom):
                raise ValueError(f"PCM mismatch for {lanes} lanes at {block} samples")
        takes.append({"test":label,"frames":len(exact),"all_layouts_bit_exact":True,
            "accumulator_sha256":hashlib.sha256(exact.astype("<i8").tobytes()).hexdigest()})
    return {"sample_rate":RATE,"track_count":len(stems),"tests":takes}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("destination",type=Path)
    p.add_argument("stems",type=Path,nargs="+")
    p.add_argument("--merlin-research",type=Path,default=RESEARCH)
    opts=p.parse_args()
    if not 1<=len(opts.stems)<=48:
        p.error("Use one to 48 stems")
    options=[]
    for candidate in LAYOUTS:
        for block in QUANTA:
            scenarios=[scenario(candidate,n,block) for n in SCENARIOS]
            peak=max(x["load_percent"] for x in scenarios)
            memory=max(x["scratch_bytes"] for x in scenarios)
            options.append({"name":candidate["name"],"quantum":block,"symbolic_cost":candidate["cost"],
                "worst_load_percent":peak,"scratch_kib":round(memory/1024,2),
                "passes":all(x["deadline_met"] and x["scratch_within_budget"] for x in scenarios)
                         and peak<=75 and block==128,
                "scenarios":scenarios})
    ranking=sorted((r for r in options if r["passes"]),key=lambda r:(r["symbolic_cost"],r["worst_load_percent"]))
    result={
        "status":"cycle-budget model, not RTL or measured silicon",
        "assumptions":{"preferred_quantum":128,"clock_hz":CLOCK,"sample_rate":RATE,"srambudget_kib":BUDGET_KIB,
                       "worst_load_limit_percent":75,"latency_scope":"one DSP buffer only",
                       "tracks_are_stereo":True,"track_cost_includes_gain_pan_and_reserve_for_EQ":True,
                       "modeled_options":LAYOUTS},
        "preferred_quantum":128,"ranking":ranking,"all_options":options,
        "fixed_point_check":validate(opts.stems),"ideonomy":ideonomy(opts.merlin_research),
    }
    with opts.destination.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,indent=2)
        stream.write("\n")


if __name__=="__main__":
    main()
