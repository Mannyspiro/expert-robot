"""Opt-in byte budgeting for plain chat prompts."""
from dataclasses import dataclass
import json

MIN_BUDGET = 256
MAX_BUDGET = 1_000_000
_INSTRUCTIONS = {"system", "developer"}
_TOOLS = {"tools", "tool_choice", "functions", "function_call"}


class ChatContextTooLarge(ValueError):
    """Required instructions and the latest turn do not fit."""


def parse_context_budget(value: str | None) -> int | None:
    if value in (None, "", "0"):
        return None
    if not value.isascii() or not value.isdecimal() or len(value) > 7:
        raise ValueError("MERLIN_CHAT_CONTEXT_BYTES must be 0 or an integer from 256 to 1000000")
    budget = int(value)
    if not MIN_BUDGET <= budget <= MAX_BUDGET:
        raise ValueError("MERLIN_CHAT_CONTEXT_BYTES must be 0 or an integer from 256 to 1000000")
    return budget


@dataclass(frozen=True)
class PackedContext:
    messages: list
    metadata: dict


def pack_chat_context(payload: dict, budget: int) -> PackedContext | None:
    """Keep prefix instructions and the longest intact suffix that fits.

    Return None for protocol shapes outside plain user/assistant turns.
    """
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages or _TOOLS.intersection(payload):
        return None
    starts = []
    prefix = 0
    for index, message in enumerate(messages):
        if (not isinstance(message, dict) or message.keys() != {"role", "content"}
                or not isinstance(role := message["role"], str)
                or not isinstance(message["content"], str)):
            return None
        if role in _INSTRUCTIONS and index == prefix:
            prefix += 1
        elif role == "user":
            starts.append(index)
        elif role != "assistant" or not starts:
            return None
    if not starts:
        return None

    # Same UTF-8 encoding and separators as the outbound gateway. Count one
    # separator per item, then use one added byte for the list delimiters.
    sizes = [len(json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1
             for message in messages]
    latest = starts[-1]
    used = 1 + sum(sizes[:prefix]) + sum(sizes[latest:])
    if used > budget:
        raise ChatContextTooLarge("Instructions and the latest user turn exceed the configured context budget.")
    for begin, end in reversed(list(zip(starts, starts[1:]))):
        size = sum(sizes[begin:end])
        if used + size > budget:
            break
        latest = begin
        used += size
    packed = messages[:prefix] + messages[latest:]
    return PackedContext(packed, {
        "budget_bytes": budget, "input_message_bytes": 1 + sum(sizes),
        "forwarded_message_bytes": used, "omitted_messages": len(messages) - len(packed),
    })
