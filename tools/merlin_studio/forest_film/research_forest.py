"""Run Merlin's Ideonomy module against the forest film production choices."""

from itertools import combinations
import json
from pathlib import Path
import sys

default = Path(__file__).resolve().parents[3]/"docs/merlin/usb/source/payload/research"
sys.path.insert(0,str(default))
from merlin_ideonomy import enumerate_combination_report


def main():
    items = {
      "seeded_world": ("geometry",2), "mist_composite": ("lighting",1),
      "cut_local_inbetween": ("motion",2), "native_24fps": ("motion",4),
      "vocal_cues": ("narration",1), "designed_ambience": ("sound",1),
      "528_anchor": ("music",1), "440_control": ("evaluation",1),
    }
    compatible = (
      ("seeded_world","mist_composite","cut_local_inbetween"),
      ("seeded_world","mist_composite","native_24fps"),
      ("vocal_cues","designed_ambience","528_anchor"),
      ("528_anchor","440_control"),
    )
    pairs={frozenset(pair) for group in compatible for pair in combinations(group,2)}
    inventory=[{"id":name,"domain":domain,"estimated_cost":cost}
               for name,(domain,cost) in items.items()]
    result=enumerate_combination_report(inventory,pairs,trigger="Build cinematic forests in a bounded CPU render window",
           problem="Compare scene, delivery and sound design strategies for a repeatable short film.",
           max_size=3,max_cost=7,limit=84,work_budget=84)
    result["pilot_choices"]={
      "image":"Build with a seed for editability, render from an animated 3D camera, and interpolate only inside shots.",
      "audio":"Mix independent score, atmosphere, designed effects and narration. Retain an A4=440 comparison score.",
      "deferred":"Higher-sample native-24 fps render, independently reviewed perceptual comparison, and any clinical experiment.",
      "scope":"Engineering estimates. Chemistry, health, and biological efficacy are outside the experiment."}
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
