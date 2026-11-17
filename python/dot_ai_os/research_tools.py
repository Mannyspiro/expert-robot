"""Statically registered research tools; no dynamic code, repair or provider calls."""
from __future__ import annotations

from typing import Any
from .research_protocol import research_contract, research_episode_demo
from .math_lenses import mathematical_lenses_demo


def reviewed_virtual_circuit_demo(arguments: dict[str, Any]) -> dict[str, Any]:
    """Preserve the virtual tool's result contract while requiring the research loop."""
    if type(arguments) is not dict or not set(arguments) <= {"operation"} or arguments.get("operation", "demo") != "demo":
        raise ValueError("only the fixed reviewed circuit demo is available")
    episode = research_episode_demo({})
    if (episode.get("ordering") is None or episode.get("qualification") is not False
            or episode.get("promotion_authority") is not False):
        raise ValueError("required bounded research episode did not complete")
    result = dict(episode["simulation"])
    result["research_protocol"] = {key: value for key, value in episode.items() if key != "simulation"}
    return result
