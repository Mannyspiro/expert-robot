# PR 179 receipt retrieval comparison

On 16 preregistered questions over the existing LMS/Titan integration receipt and registry-recovery receipt, binding the answer to the requested run improved exact decisions from 10 to 13. Each pass required the correct action. Answers also required a typed value, a source-bound pointer and a byte-verified citation. A request to clarify the field counted as incorrect when an unambiguous request called for an abstention.

| Expected action | Cases | First-hit baseline correct | Run-bound candidate correct |
|---|---:|---:|---:|
| Report a supported value | 5 | 4 | 4 |
| Contradict a numeric claim | 2 | 1 | 2 |
| Abstain | 6 | 2 | 4 |
| Ask which run | 2 | 2 | 2 |
| Ask which field | 1 | 1 | 1 |

Two missing-field questions previously took answers from the other run. The bound reader abstained on both. For a third question, both readers contradicted the numeric claim, but only the candidate used the LMS receipt's count of 85 and its citation. No previously correct case regressed. Both methods sought clarification for an answerable vector-count paraphrase and for two specific unavailable quantities. Those three errors remain in the result.

The raw search check compared the baseline lexical bridge with PR 179's identifier-aware bridge. Both returned a passage covering the exact oracle span in the first two hits on 3 of 7 answerable or contradicted questions. This sample supports using run binding for the evaluated receipt reader. It supplies no measured advantage for the tokenizer change.

## Reproduce the comparison

Use a separate checkout of `Mannyspiro/expert-robot` at head `09da78d367fa50fdcca7fa0a0e0b18bf61b1487f` and the baseline bridge from commit `4811c448216e0582336ffc8c2c1468a5260a4b18`. The command verifies all ten input Git blobs and the preregistration SHA-256 before importing the retrieval code.

```sh
python -I scripts/merlin/measure_pr179_receipts.py \
  --candidate-root /path/to/pr179-checkout \
  --baseline-bridge /path/to/base-checkout/python/dot_ai_os/bridge.py
```

The frozen [protocol and questions](../../tests/fixtures/pr179-fresh-receipts-v1.json) have SHA-256 `305931db77d884f57ee4ff453a3096be96c2b5aff02728fe0df7513d731fbe3b`. The [complete observations](../evidence/pr179-fresh-receipts-v1.json) preserve each decision, checked citation and regression. The scorer keeps a completed observation even if the candidate loses the preregistered gate.

The questions and oracles were written before observing either implementation's outputs. The author could read the source code and the historical receipts. A subsequent comparison against PR 179's published cases identified one reused standalone question string (L16). Keeping the registered set gives the totals above. On the remaining 15 distinct question strings, the scores are 9/15 and 12/15. These task-specific questions cannot establish accuracy on other course corpora or production queries.
