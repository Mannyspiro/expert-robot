# Lightweight Merlin chat profile

Keep the existing Merlin runtime and its provider qualification checks. Start with an opt-in byte budget for plain text chat. Tool and attachment capabilities continue through their established paths. This is the first optimization slice, with a known measurement boundary and a reversible setting.

## Runtime contract

Set `MERLIN_CHAT_CONTEXT_BYTES=4096` before creating the HTTP handler to try the profile. The accepted range is 256 to 1,000,000 bytes. Unset it or set it to 0 for the original behavior. An invalid setting fails startup.

For a plain text prompt, the gateway preserves contiguous leading system and developer instructions and the most recent complete user turn. It adds earlier consecutive turns until another complete turn would exceed the budget. The bound counts the exact UTF-8 JSON bytes of the message array, including delimiters and escaping. It is a transport budget. It does not predict tokenizer length, model memory, inference latency, or cost. If the required instructions and latest turn exceed the budget, the gateway returns HTTP 413 before contacting the model. Message content and roles are never rewritten.

This first profile covers simple text user and assistant histories. Tool definitions, tool calls or results, named messages, multimodal content, and interleaved instructions take the existing gateway path. Provider authorization and model selection still apply to both paths. The profile introduces neither a second model call nor a new package. Event summaries can carry byte and omission counts without exposing chat content. Persisting a complete user history remains the responsibility of the caller's existing storage path.

## Why this slice

Merlin Studio's live design Ideonomy queried a reversible context budget with a matched baseline. It examined all 28 pairs, retained 10 eligible pairs and returned five. A measured baseline comparison and a limiting case guided the selected experiment. A separate Studio tool check executed 64 tensor outcomes across 16 replays using the existing direct command path.

| Candidate | Benefit | Trade-off |
| --- | --- | --- |
| Existing full prompt | All supplied history is forwarded | More serialized context on long turns |
| Complete-turn byte budget | Predictable upper bound for supported prompts with no new inference | Older context can be omitted and multi-modal/tool requests keep their current path |
| Model-assisted summarization and scoped retrieval | Can preserve earlier details when independently qualified | Additional context construction, latency or inference, plus a need for evidence on omission and citation quality |

In a synthetic 40-turn history the message array is 51,209 bytes. Budgets of 2 KiB, 4 KiB and 8 KiB forward 1,377, 3,933 and 7,767 bytes respectively. The 4 KiB profile sends **92.3% fewer message bytes** and keeps the newest three prior turns, the leading instruction and the latest request. The paired HTTP check captures the bytes at a real loopback fixture provider, checks the exact byte receipt and rejects an oversized mandatory turn before forwarding. Preserving the latest turn does not establish that the answer will recall omitted information. A recall or long-horizon quality comparison would require an independent, held-out model evaluation.

## Context and release fit

The design uses the visible conversation, the preserved Merlin project and chat-idea ledgers, recent Studio and Parallax records, and the open GitHub runtime branch. Complete account-chat and Drive exports were not available. The test uses synthetic turns and the PR includes no private transcript text. This change leaves Studio's direct actions, Research, Draft, tensor tools, Library, LMS, voice and CAD in their existing runtime paths. The profile applies when a prompt takes the existing model gateway. The PR is stacked on the active Merlin runtime because the repository default branch does not contain that gateway.

Run `PYTHONPATH=.:python python -m pytest -q tests/research/test_chat_context.py tests/research/test_merlin_api.py`. The focused run passed 40 tests. This is a tested context-efficiency slice within P08 of the production master plan. “Optimal” refers only to keeping the longest contiguous suffix under this exact policy and byte budget.
