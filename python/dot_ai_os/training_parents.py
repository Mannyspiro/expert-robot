"""Choose up to two training parents for the next local research episode."""

import json
from itertools import combinations

from ._vendor.gepa_utils import remove_dominated_programs
from .cross_agent_review import ARMS, CrossAgentReviewer


def choose_parents(correct_cases, *, limit=2):
    """Keep complementary training behavior within the host's exploration budget."""
    if type(limit) is not int or limit not in (1, 2):
        raise ValueError("the research budget allows one or two parents")
    if set(correct_cases) != set(ARMS):
        raise ValueError("require outcomes for the baseline and both coders")

    # Prefer the baseline, then coder A, when training behavior is identical.
    masks = [frozenset(correct_cases[arm]) for arm in ARMS]
    representatives = {}
    for index, mask in enumerate(masks):
        if mask:
            representatives.setdefault(mask, index)
    if not representatives:
        return ["baseline"]

    frontier = {}
    for mask, index in representatives.items():
        for case in sorted(mask):
            frontier.setdefault(case, set()).add(index)
    front = remove_dominated_programs(frontier, scores=[len(mask) for mask in masks])
    preferred = set().union(*front.values())
    candidates = sorted(representatives.values())
    # GEPA can remove a parent whose wins are spread over several others.
    # With only two slots, check the tiny full space so this cannot cost coverage.
    def score(batch):
        covered = set().union(*(masks[index] for index in batch))
        return (len(covered), -len(batch), len(preferred.intersection(batch)))

    options = (batch for size in range(1, limit + 1)
               for batch in combinations(candidates, size))
    return [ARMS[index] for index in max(options, key=score)]


def plan_training_parents(reviewer: CrossAgentReviewer, protocol_ref, *, limit=2):
    """Read a verified completed review. Return proposal inputs for training only."""
    review = reviewer.status(protocol_ref)
    if "observation_ref" not in review:
        raise ValueError("training planning requires a completed review")
    registry = reviewer.registry
    protocol = json.loads(registry.read_artifact_ref(protocol_ref)["content"])
    observation = json.loads(registry.read_artifact_ref(review["observation_ref"])["content"])
    expected = protocol["train_labels"]
    matches = {arm: {case for case, label in expected.items()
                     if observation["predictions"][arm][case] == label} for arm in ARMS}
    arms = choose_parents(matches, limit=limit)
    refs = {"baseline": protocol["workflow"]["specification"]["context_refs"][0],
            **observation["candidate_refs"]}
    covered = set().union(*(matches[arm] for arm in arms))
    return {"schema": "dot-training-parent-plan/1", "target": protocol["target"],
            "budget": limit, "parents": [{"arm": arm, "candidate_ref": refs[arm]} for arm in arms],
            "train_cases": len(expected), "train_cases_covered": len(covered),
            "uncovered_train_ids": sorted(expected.keys() - covered),
            "promotion_authority": False}
