"""Local-only model execution for the Merlin council.

Opening calls are isolated from other role outputs. Optional second rounds
expose the completed opening transcript for cross-examination. This adapter
cannot access remote providers, tools, promotion, or merge authority.
"""
from __future__ import annotations

from hashlib import sha256
from http.client import HTTPConnection
import json
import os
import re
from typing import Any
from urllib.parse import urlsplit

from .council import build_deliberation_packets
from .skeptical_scientist_policy import SCIENTIFIC_POLICY


MAX_COUNCIL_RESPONSE = 256_000


def _loopback_endpoint(endpoint: str) -> tuple[str, int, str]:
    """Bind localhost to IPv4 loopback; use http://[::1] for IPv6.

    Validate the original text before urlsplit can discard control characters.
    No DNS name, URL credentials, fragment or malformed port reaches transport.
    """
    if (not isinstance(endpoint, str) or not endpoint
            or any(ord(char) < 33 or ord(char) > 126 for char in endpoint)
            or "\\" in endpoint or "#" in endpoint
            or re.search(r"%(?![0-9a-fA-F]{2})", endpoint)):
        raise ValueError("invalid council model endpoint")
    parsed = urlsplit(endpoint)
    authority = re.fullmatch(r"(127\.0\.0\.1|localhost|\[::1\])(?::([0-9]{1,5}))?",
                             parsed.netloc, flags=re.IGNORECASE)
    if parsed.scheme != "http" or authority is None:
        raise ValueError("council model endpoint must be loopback-only")
    port = int(authority.group(2)) if authority.group(2) is not None else 80
    if not 1 <= port <= 65535:
        raise ValueError("invalid council model endpoint port")
    host = "::1" if authority.group(1) == "[::1]" else "127.0.0.1"
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    return host, port, target


def _council_system(packet: dict[str, Any]) -> str:
    persona = packet["persona"]
    return (
        "You are participating in a simulated expert council. Adopt the role below as a "
        "reasoning perspective, not as a claim of personhood. Be candid, vivid, specific, "
        "and evidence-disciplined. Clearly label evidence, assumptions, uncertainty, and "
        "what would change your mind. Never invent citations, experiments, tool use, or "
        "implementation results. Do not claim authority to approve, deploy, or promote."
        "\nROLE: " + json.dumps(persona, ensure_ascii=False)
        + "\nROLE INSTRUCTIONS: " + packet["instructions"]
        + "\nHOST-OWNED SKEPTICAL SCIENTIST POLICY (NON-AUTHORIZING):\n"
        + SCIENTIFIC_POLICY
    )


def _model_call(endpoint: str, model: str, packet: dict[str, Any],
                prior_positions: list[dict[str, str]] | None = None) -> dict[str, Any]:
    host, port, target = _loopback_endpoint(endpoint)
    persona = packet["persona"]
    system = _council_system(packet)
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
    # Direct numeric loopback avoids urllib's redirects, environment proxies and
    # global opener. The 180-second socket timeout is not a total wall deadline.
    connection = HTTPConnection(host, port, timeout=180)
    try:
        connection.request("POST", target, body=encoded,
                           headers={"Content-Type": "application/json"})
        with connection.getresponse() as response:
            if not 200 <= response.status < 300:
                raise ValueError("local council model returned HTTP status " + str(response.status))
            body = response.read(MAX_COUNCIL_RESPONSE + 1)
    finally:
        connection.close()
    if len(body) > MAX_COUNCIL_RESPONSE:
        raise ValueError("council model response exceeded size limit")
    result = json.loads(body.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("local model returned an invalid response object")
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("local model returned no choices")
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        raise ValueError("local model returned an invalid message")
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
                      rounds: int = 1, *, visual_specialist_only: bool = False) -> dict[str, Any]:
    """Run the research council or a single visual design consultation."""
    if type(rounds) is not int or rounds not in (1, 2):
        raise ValueError("rounds must be 1 or 2")
    if visual_specialist_only and rounds != 1:
        raise ValueError("a single specialist has no second-round debate partner")
    if os.environ.get("MERLIN_MODEL_QUALIFIED") != "1":
        raise RuntimeError("local model is not qualified; council execution is disabled")
    endpoint = os.environ.get("MERLIN_MODEL_URL", "http://127.0.0.1:8080/v1/chat/completions")
    _loopback_endpoint(endpoint)
    model = os.environ.get("MERLIN_MODEL_NAME", "local-model").strip() or "local-model"
    packets = (build_deliberation_packets(question, context, verbosity, visual_specialist_only=True)
               if visual_specialist_only else build_deliberation_packets(question, context, verbosity))
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
