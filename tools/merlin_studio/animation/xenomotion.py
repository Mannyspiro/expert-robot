"""Compile sparse 2D camera poses and acting events into a verified frame plan."""

import argparse
from bisect import bisect_right
from fractions import Fraction
import json
from pathlib import Path

from exposure import time_value


def ease(t):
    """Simplex weight in [0,1] with zero speed at both ends."""
    return t*t*(3-2*t)


def blend(left, right, t):
    weight = ease(t)
    return tuple((1-weight)*a + weight*b for a,b in zip(left,right,strict=True))


def rectangle(values):
    x0,y0,x1,y1 = map(time_value,values)
    if not (x0 < x1 and y0 < y1):
        raise ValueError("A region must have a positive width and height")
    return x0,y0,x1,y1


def viewport(crop, ratio):
    x,y,width = crop
    half = width/2
    height = half*ratio
    return x-half,y-height,x+half,y+height


def margins(crop, region, art_size, ratio, padding):
    x0,y0,x1,y1 = viewport(crop,ratio)
    a,b,c,d = region
    horizontal = (x1-x0)*padding
    vertical = (y1-y0)*padding
    return (x0,y0,art_size[0]-x1,art_size[1]-y1,
            a-x0-horizontal,b-y0-vertical,x1-c-horizontal,y1-d-vertical)


def autoframe(camera, region, art, ratio, padding):
    """Project a requested crop onto the exact feasible camera region."""
    x,y,width = camera
    left,top,right,bottom = region
    art_w,art_h = map(Fraction,art)
    minimum = max(right-left,(bottom-top)/ratio)/(1-2*padding)
    maximum = min(art_w,art_h/ratio)
    if padding:
        maximum = min(maximum,left/padding,(art_w-right)/padding,
                      top/(ratio*padding),(art_h-bottom)/(ratio*padding))
    if minimum > maximum:
        raise ValueError("The protected region cannot fit inside the art at this margin")
    width=min(max(width,minimum),maximum)
    def center(value, span, extent, near, far):
        interior=span*(Fraction(1,2)-padding)
        low=max(span/2,far-interior)
        high=min(extent-span/2,near+interior)
        return min(max(value,low),high)
    return (center(x,width,art_w,left,right),
            center(y,width*ratio,art_h,top,bottom),width)


def camera_samples(shot, art, ratio, padding):
    start,end = shot["start"],shot["end"]
    region = rectangle(shot["guard"])
    keys = [(item[0],tuple(map(time_value,item[1:]))) for item in shot["keys"]]
    frames = [frame for frame,_ in keys]
    if (not keys or any(type(f) is not int for f in frames) or frames!=sorted(set(frames))
            or frames[0]!=start or frames[-1]>=end or (len(keys)>1 and frames[-1]!=end-1)):
        raise ValueError(f"{shot['name']}: camera keys must start at the shot's first frame and end at its last moving frame")
    auto=shot.get("autoframe",False)
    if type(auto) is not bool:
        raise ValueError("autoframe must be true or false")
    key_margins=[]
    adjustments=[]
    for index,(frame,camera) in enumerate(keys):
        if len(camera)!=3 or camera[2]<=0:
            raise ValueError("Each camera pose needs a center and positive width")
        if auto:
            fitted=autoframe(camera,region,art,ratio,padding)
            if fitted!=camera:
                adjustments.append({"frame":frame,"requested":[float(x) for x in camera],
                                    "fitted":[float(x) for x in fitted]})
            camera=fitted
            keys[index]=(frame,camera)
        clearance=min(margins(camera,region,art,ratio,padding))
        if clearance < 0:
            raise ValueError(f"{shot['name']}, camera key {frame}: shot leaves artwork or crops its protected region")
        key_margins.append(clearance)
    certified_clearance = min(key_margins)
    for frame in range(start,end):
        index=bisect_right(frames,frame)-1
        left_time,left=keys[index]
        camera=left
        if index+1<len(keys):
            right_time,right=keys[index+1]
            camera=blend(left,right,Fraction(frame-left_time,right_time-left_time))
        yield frame,camera,certified_clearance,adjustments


def compile_plan(plan):
    art=tuple(plan["art_size"])
    output=tuple(plan["size"])
    if len(art)!=2 or len(output)!=2 or any(type(n) is not int or n<=0 for n in (*art,*output)):
        raise ValueError("Art and output sizes must be positive pixel dimensions")
    if any(n%2 or n>4096 for n in output):
        raise ValueError("Output dimensions must be even and at most 4096")
    expected=plan["frames"]
    fps=time_value(plan["fps"])
    start=time_value(plan["audio_start"])
    padding=time_value(plan["safe_margin"])
    if type(expected) is not int or not 1<=expected<=24000 or not 1<=fps<=120 or start<0 or not 0<=padding<Fraction(1,2):
        raise ValueError("Invalid clip length, rate, audio start, or framing margin")
    eyes=plan["eyes"]
    actors={actor:[0]*expected for actor in eyes}
    events=plan["blinks"]
    last_end={}
    for event in events:
        actor=event["actor"]
        a,peak,b=(event[key] for key in ("start","closed","end"))
        if (actor not in actors or any(type(n) is not int for n in (a,peak,b))
                or not last_end.get(actor,0)<=a<peak<b<expected):
            raise ValueError(f"Invalid or overlapping blink for {actor}")
        last_end[actor]=b
        for f in range(a,b+1):
            t=Fraction(f-a,peak-a) if f<=peak else Fraction(b-f,b-peak)
            actors[actor][f]=float(ease(t))
    ratio=Fraction(output[1],output[0])
    cursor=0
    samples=[]
    guards=[]
    names=set()
    for shot in plan["shots"]:
        a,b=shot["start"],shot["end"]
        name=shot["name"]
        if not name or name in names or type(a) is not int or type(b) is not int or a!=cursor or not a<b<=expected:
            raise ValueError("Shots must have unique names and cover the timeline contiguously")
        names.add(name)
        for frame,camera,clearance,adjustments in camera_samples(shot,art,ratio,padding):
            samples.append({"frame":frame,"shot":name,"crop":[float(x) for x in viewport(camera,ratio)],
                            "blink":{k:v[frame] for k,v in actors.items() if v[frame]}})
        guards.append({"shot":name,"minimum_certified_clearance_px":float(clearance),
                       "guard_px":shot["guard"],"auto_fitted_keys":adjustments})
        cursor=b
    if cursor!=expected:
        raise ValueError("Shots do not cover the full timeline")
    return {"fps":str(fps),"audio_start":str(start),"art_size":art,"size":output,
            "authored_camera_keys":sum(len(s["keys"]) for s in plan["shots"]),"authored_blinks":len(events),
            "certificate":{"method":"exact rational affine margins at all keys and convex interpolation",
                           "safe_margin_fraction":str(padding),"shots":guards},
            "frames":samples}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    try:
        original=json.loads(args.plan.read_text(encoding="utf-8"))
        result=compile_plan(original)
        with args.output.open("x",encoding="utf-8") as stream:
            json.dump(result,stream,indent=2)
            stream.write("\n")
    except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError) as exc:
        p.exit(1,f"{exc}\n")
    print(json.dumps({"frames":len(result["frames"]),"keys":result["authored_camera_keys"],
                      "blinks":result["authored_blinks"],"certified_framing":True}))


if __name__=="__main__":
    main()
