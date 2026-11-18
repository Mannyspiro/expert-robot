# Titan private board research measurement

From the repository root, run the integrated offline check with the Python environment specified in [the Titan envelope profile](TITAN_PQ_ENVELOPE_V1.md).

```sh
PYTHONPATH=python python scripts/merlin/measure_titan_board_pq.py
PYTHONPATH=python python scripts/merlin/measure_titan_board_pq.py --compare docs/evidence/titan-board-pq-20261117.json
```

Each run generates temporary keys in memory, encrypts a message alongside three 19×19×19 boards with a mirror and compares it to a legacy three-board 7×7×7 record. The recipient decodes both full records, including their permutations, moves and Ko snapshots. Wrong-recipient and wrong-context checks exercise the refusal path. The command calls the installed HPKE backend directly without a network or a persistent key store.

The [recorded local run](../evidence/titan-board-pq-20261117.json) passed all nine checks. With a 262,144-byte padding bucket, each serialized envelope measured 351,222 bytes and had the same generic public header. A second encryption of the same record produced different ciphertext. These observations concern the two samples and the tested profile. The header, selected bucket, wire length and traffic timing remain observable.

The command outputs the software versions, public check outcomes, timing and wire lengths. Exit `0` indicates a pass, `1` indicates a failed check or comparison, and `2` indicates an unavailable or unsupported backend. The comparison checks all stable fields including the exact Python and cryptography versions. Elapsed time varies. The file's date identifies the work batch; the stored UTC timestamp records the actual run.

## Host API

The sending host obtains the trusted **recipient public key** through its own configured channel. The receiving host supplies the matching **private seed**. The example uses the same generic purpose/schema at both ends. Choose a permitted fixed bucket before sending. Payloads that exceed it are rejected.

```python
from merlin.titan_board_encoding import (
    decode_private_board_message, encode_private_board_message, public_board_context,
)
from merlin.titan_pq_envelope import decrypt, encrypt

context = public_board_context()
payload = encode_private_board_message(message_bytes, board_record)
wire_bytes = encrypt(payload, recipient_public_key, context, pad_to=262144)

recovered_payload = decrypt(wire_bytes, recipient_private_seed, public_board_context())
message_bytes, board_record = decode_private_board_message(recovered_payload)
```

The three boards and their histories are private application data in the encrypted payload. Independent sender authentication, key distribution and rotation, replay control, and deployment validation remain external responsibilities. The research runner exercises the local codec and envelope. LMS traffic and production deployment require separate integration and evidence.
