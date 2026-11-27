"""Use Merlin's release research module to catalogue frame reuse ideas."""

from hashlib import sha256
import itertools
import json

from ideonomy import MERLIN_RESEARCH

import sys
sys.path.insert(0,str(MERLIN_RESEARCH))
from merlin_ideonomy import enumerate_combination_report


def main():
    catalogue = {
        "source_layers": ("art", 1),
        "motion_recipe": ("animation", 1),
        "content_identity": ("verification", 1),
        "image_reference": ("storage", 1),
        "pixel_residual": ("prediction", 2),
        "periodic_base": ("recovery", 1),
        "motion_prediction": ("prediction", 3),
        "strict_decode": ("verification", 1),
    }
    rows=[{"id":name,"domain":domain,"estimated_cost":cost}
          for name,(domain,cost) in catalogue.items()]
    plans={
        "regenerate": {"source_layers","motion_recipe","content_identity"},
        "dedup": {"content_identity","image_reference"},
        "delta": {"pixel_residual","periodic_base","strict_decode"},
        "x264rgb_inter": {"motion_prediction","periodic_base","strict_decode"},
        "ffv1_intra": {"image_reference","strict_decode"},
    }
    pairs={frozenset(pair) for plan in plans.values() for pair in itertools.combinations(plan,2)}
    report=enumerate_combination_report(rows,pairs, trigger="Repetitive RGB frames in the animated pilot",
        problem="Reduce storage while reproducing the full frame sequence exactly.",
        max_size=3,max_cost=6,limit=84,work_budget=84)
    report["proposed_methods"]={name:sorted(v) for name,v in plans.items()}
    report["release_enumerator_sha256"]=sha256((MERLIN_RESEARCH/"merlin_ideonomy.py").read_bytes()).hexdigest()
    report["epistemic_order"]=[
        "Require an exact frame match for intermediates.",
        "Rank ready-to-decode candidates by measured bytes within each motion regime.",
        "Keep layered source for editable projects. Its regeneration cost is not decoded-cache retrieval.",
    ]
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
