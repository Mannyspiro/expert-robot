"""Use the pinned Merlin Ideonomy enumerator for the anime audio workflow."""

import argparse
from itertools import combinations
import json
from pathlib import Path
import sys


DEFAULT = Path(__file__).resolve().parents[3]/"docs/merlin/usb/source/payload/research"
PRIMITIVES = {
    "original_score": ("composition",1),
    "formant_renderer": ("voice",1),
    "procedural_foley": ("sound_effects",1),
    "editor": ("arrangement",2),
    "documented_voicebank": ("voice",3),
    "diffusion_model": ("voice_model",4),
    "archive_stems": ("delivery",1),
    "language_phonemes": ("pronunciation",2),
}
PROPOSALS = {
    "Local formant synth and procedural Foley": (
        ("original_score","formant_renderer","procedural_foley"), (4,2,4,4)),
    "OpenUtau with a documented voicebank": (
        ("editor","documented_voicebank","language_phonemes"), (2,4,3,3)),
    "OpenUtau and a compatible DiffSinger voicebank": (
        ("editor","documented_voicebank","diffusion_model"), (1,4,3,2)),
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merlin-research",type=Path,default=DEFAULT)
    args=parser.parse_args()
    sys.path.insert(0,str(args.merlin_research))
    from merlin_ideonomy import enumerate_combination_report

    rows=[{"id":k,"domain":domain,"estimated_cost":cost} for k,(domain,cost) in PRIMITIVES.items()]
    whitelist={frozenset(pair) for group,_ in PROPOSALS.values() for pair in combinations(group,2)}
    whitelist.update({frozenset(("archive_stems","formant_renderer")),
                      frozenset(("archive_stems","editor")),frozenset(("original_score","editor"))})
    result=enumerate_combination_report(rows,whitelist,trigger="The anime has a dialogue track and needs original music and effects",
         problem="Produce editable audio locally and leave a path to clearer sung lyrics.",
         max_size=3,max_cost=9,limit=84,work_budget=84)
    candidates={frozenset(row["primitive_ids"]) for row in result["candidates"]}
    rating=[]
    for name,(group,dimensions) in PROPOSALS.items():
        if frozenset(group) not in candidates:
            raise ValueError(f"Unsupported audio combination: {name}")
        ready,clarity,control,reproduce=dimensions
        rating.append({"approach":name,"engineering_judgments_0_to_4":dimensions,
                       "pilot_priority":(4*ready+2*clarity+2*control+2*reproduce)*2.5,
                       "lyric_priority":(ready+5*clarity+3*control+reproduce)*2.5})
    result["pilot_ranking"]=sorted(rating,key=lambda x:-x["pilot_priority"])
    result["lyric_ranking"]=sorted(rating,key=lambda x:-x["lyric_priority"])
    result["bounds"]="Subjective engineering triage. Ranked production candidates have not been compared in a controlled vocal listening test."
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
