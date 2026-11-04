"""Engineering-aware image/video prompt compilation and ComfyUI workflow adapter.

Generative media is for visualization and communication. It is never the
source of dimensions, topology, pin numbering, tolerances, or approval data.
Exact engineering artifacts must be generated from Merlin's typed IR.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Mapping
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class EngineeringMediaBrief:
    project_name: str
    purpose: str
    audience: str = "engineering review"
    view: str = "isometric assembly"
    style: str = "clean technical visualization, neutral background"
    include_callouts: bool = False
    include_dimensions: bool = False
    duration_seconds: int = 8
    fps: int = 24
    aspect_ratio: str = "16:9"


@dataclass(frozen=True)
class EngineeringPromptPack:
    image_prompt: str
    video_prompt: str
    negative_prompt: str
    coder_prompt: str
    provenance: dict[str, Any]
    status: str = "VISUALIZATION_ONLY_NOT_ENGINEERING_SOURCE"


def _project_summary(project: Any, assembly: Any | None = None) -> dict[str, Any]:
    parts = []
    for part in sorted(project.parts, key=lambda item: item.ref):
        parts.append({
            "ref": part.ref,
            "name": part.name,
            "size_mm": list(part.size_mm),
            "position_mm": list(part.position_mm),
            "pins": [{"number": pin.number, "name": pin.name,
                      "position_mm": list(pin.position_mm) if pin.position_mm else None}
                     for pin in sorted(part.pins, key=lambda item: item.number)],
        })
    nets = [{
        "name": net.name, "class": net.net_class,
        "endpoints": sorted(net.endpoints),
        "nominal_voltage_v": net.nominal_voltage_v,
        "max_current_a": net.max_current_a,
    } for net in sorted(project.nets, key=lambda item: item.name)]
    components = []
    if assembly is not None:
        components = [{
            "part_ref": item.part_ref,
            "frame_id": item.frame_id,
            "rotation": list(item.transform.rotation),
            "translation_mm": list(item.transform.translation_mm),
        } for item in sorted(assembly.components, key=lambda item: item.part_ref)]
    return {"project": project.name, "units": project.units,
            "parts": parts, "nets": nets, "assembly_components": components}


def compile_engineering_prompts(project: Any, brief: EngineeringMediaBrief,
                                assembly: Any | None = None) -> EngineeringPromptPack:
    """Compile deterministic prompts from typed project facts, never inferred geometry."""
    if brief.duration_seconds < 1 or brief.duration_seconds > 30:
        raise ValueError("duration_seconds must be between 1 and 30")
    if brief.fps < 1 or brief.fps > 60:
        raise ValueError("fps must be between 1 and 60")
    facts = _project_summary(project, assembly)
    parts = "; ".join(
        f'{p["ref"]} {p["name"]}: {p["size_mm"]} mm, position {p["position_mm"]} mm'
        for p in facts["parts"]
    ) or "No part geometry supplied"
    nets = "; ".join(
        f'{n["name"]}: {", ".join(n["endpoints"])}'
        for n in facts["nets"]
    ) or "No electrical nets supplied"
    dimensions = "Show only dimensions explicitly present in the source data." if brief.include_dimensions else "Do not add dimensions or measurement labels."
    callouts = "Use callout placeholders only; do not invent component ratings or part numbers." if brief.include_callouts else "No text labels or callouts."
    image_prompt = (
        f"Create a {brief.view} visualization of {brief.project_name}. "
        f"Purpose: {brief.purpose}. Audience: {brief.audience}. Style: {brief.style}. "
        f"Represent only the supplied assembly facts: {parts}. Connectivity context: {nets}. "
        f"{dimensions} {callouts} Maintain physically plausible proportions and clear separation "
        "between components. If any feature is unspecified, leave it visually neutral rather than guessing. "
        "This is an explanatory visualization, not a manufacturing drawing."
    )
    video_prompt = (
        f"{brief.duration_seconds}-second engineering explainer, {brief.fps} fps, "
        f"{brief.aspect_ratio}. Begin with a stable full assembly view of {brief.project_name}; "
        "move slowly to a close-up of the named components, then trace the declared connectivity "
        "as a restrained overlay, and finish on the full assembly. No part may appear, disappear, "
        "change shape, or move relative to the assembly unless explicitly animated by source data. "
        "No invented wiring, pins, labels, dimensions, or mechanical features. "
        f"Use this source fact set: {parts}. Nets: {nets}. {brief.style}."
    )
    negative = (
        "invented components, extra connectors, fabricated pin numbers, fake dimensions, "
        "unverified wire gauge, incorrect net topology, impossible geometry, perspective distortion, "
        "illegible pseudo-text, altered part count, unsupported safety claims, certification marks"
    )
    coder_prompt = (
        "You are implementing a deterministic engineering drafting pipeline. Treat the following "
        "typed Merlin project facts as the only source of truth. Never infer missing dimensions, "
        "pin numbers, materials, wire gauges, ratings, tolerances, or standards. Generate editable "
        "vector/CAD artifacts from exact coordinates and explicit constraints; use image/video models "
        "only for presentation renders. Preserve units and coordinate frames. Emit a machine-readable "
        "assumption ledger, validation report, reproducible tests, and hashes. Reject contradictory "
        "or incomplete inputs rather than silently filling them. Do not mark outputs qualified or "
        "manufacturing-ready.\nSOURCE_FACTS_JSON:\n" +
        json.dumps(facts, sort_keys=True, indent=2, ensure_ascii=False)
    )
    return EngineeringPromptPack(
        image_prompt=image_prompt, video_prompt=video_prompt,
        negative_prompt=negative, coder_prompt=coder_prompt,
        provenance={"project_name": project.name, "units": project.units,
                    "part_count": len(project.parts), "net_count": len(project.nets),
                    "source_facts": facts},
    )


def _replace_prompt_tokens(value: Any, prompt: str, negative_prompt: str) -> Any:
    if isinstance(value, str):
        return value.replace("{{PROMPT}}", prompt).replace("{{NEGATIVE_PROMPT}}", negative_prompt)
    if isinstance(value, list):
        return [_replace_prompt_tokens(item, prompt, negative_prompt) for item in value]
    if isinstance(value, dict):
        return {key: _replace_prompt_tokens(item, prompt, negative_prompt)
                for key, item in value.items()}
    return value


class ComfyUIClient:
    """Minimal local ComfyUI API adapter; caller supplies a saved API-format workflow.

    Workflow nodes must contain {{PROMPT}} and optionally {{NEGATIVE_PROMPT}} in
    their text inputs. No cloud account or paid provider is required.
    """
    def __init__(self, base_url: str | None = None, timeout_seconds: int = 20):
        self.base_url = (base_url or os.environ.get("MERLIN_COMFYUI_URL", "http://127.0.0.1:8188")).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def queue_workflow(self, workflow: Mapping[str, Any], prompt: str,
                       negative_prompt: str = "") -> dict[str, Any]:
        if not isinstance(workflow, Mapping) or not workflow:
            raise ValueError("a non-empty ComfyUI API workflow is required")
        payload = {"prompt": _replace_prompt_tokens(dict(workflow), prompt, negative_prompt)}
        request = Request(self.base_url + "/prompt",
                          data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"},
                          method="POST")
        with urlopen(request, timeout=self.timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict) or not result.get("prompt_id"):
            raise RuntimeError("ComfyUI did not return a prompt_id")
        return result
