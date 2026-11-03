"""Local-only model execution for the Merlin council.

Opening calls are isolated from other role outputs. Optional second rounds
expose the completed opening transcript for cross-examination. This adapter
cannot access remote providers, tools, promotion, or merge authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from typing import Any
from urllib.request import Request, urlopen

from .council import build_deliberation_packets


MAX_COUNCIL_RESPONSE = 256_000


def _model_call(endpoint: str, model: str, packet: dict[str, Any],
                prior_positions: list[dict[str, str]] | None = None) -> dict[str, Any]:
    persona = packet["persona"]
    system = (
        "You are participating in a simulated expert council. Adopt the role below as a "
        "reasoning perspective, not as a claim of personhood. Be candid, vivid, specific, "
        "and evidence-disciplined. Clearly label evidence, assumptions, uncertainty, and "
        "what would change your mind. Never invent citations, experiments, tool use, or "
        "implementation results. Do not claim authority to approve, deploy, or promote."
        "\nROLE: " + json.dumps(persona, ensure_ascii=False)
        + "\nROLE INSTRUCTIONS: " + packet["instructions"]
    )
    user = "QUESTION:\n" + packet["question"] + "\n\nSHARED CONTEXT:\n" + packet["shared_context"]
    if prior_positions is not None:
        user += "\n\nOTHER COUNCIL OPENING POSITIONS (for cross-examination only):\n"
        user += json.dumps(prior_positions, ensure_ascii=False)
        user += "\nChallenge the strongest disagreement, update your stance only if warranted, and explain why."
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.65,
        "max_tokens": 900,
        "stream": False,
    }
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(endpoint, data=encoded, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=180) as response:
        body = response.read(MAX_COUNCIL_RESPONSE + 1)
    if len(body) > MAX_COUNCIL_RESPONSE:
        raise ValueError("council model response exceeded size limit")
    result = json.loads(body.decode("utf-8"))
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("local model returned no choices")
    message = choices[0].get("message", {})
    text = message.get("content")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("local model returned an empty council response")
    return {
        "persona_id": persona["persona_id"],
        "persona_title": persona["title"],
        "content": text,
        "response_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "provider": "local_openai_compatible",
        "model": result.get("model") or model,
        "usage": result.get("usage") if isinstance(result.get("usage"), dict) else None,
    }


def run_local_council(question: str, context: str = "", verbosity: str = "lively",
                      rounds: int = 1) -> dict[str, Any]:
    """Run six independent local openings, optionally followed by one debate round."""
    if type(rounds) is not int or rounds not in (1, 2):
        raise ValueError("rounds must be 1 or 2")
    if os.environ.get("MERLIN_MODEL_QUALIFIED") != "1":
        raise RuntimeError("local model is not qualified; council execution is disabled")
    from urllib.parse import urlsplit\n    endpoint = os.environ.get("MERLIN_MODEL_URL", "http://127.0.0.1:8080/v1/chat/completions")\n    parsed = urlsplit(endpoint)\n    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:\n        raise ValueError("council model endpoint must be loopback-only")
    model = os.environ.get("MERLIN_MODEL_NAME", "local-model").strip() or "local-model"
    packets = build_deliberation_packets(question, context, verbosity)
    openings = [_model_call(endpoint, model, packet) for packet in packets]
    debates: list[dict[str, Any]] = []
    if rounds == 2:
        for packet in packets:
            others = [row for row in openings if row["persona_id"] != packet["persona"]["persona_id"]]
            debates.append(_model_call(endpoint, model, packet, others))
    return {
        "schema": "merlin-council-transcript/1",
        "provider": "local_openai_compatible",
        "model": model,
        "rounds_requested": rounds,
        "opening_positions": openings,
        "cross_examination": debates,
        "opening_independence": "Each opening call received only the shared question/context and its own role packet.",
        "promotion_authorized": False,
        "authority_expansion": False,
    }
