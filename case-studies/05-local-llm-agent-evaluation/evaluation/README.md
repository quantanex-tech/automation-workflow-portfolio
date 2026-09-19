# Published evaluation evidence

This directory contains compact, sanitised outputs from the local-model reliability baseline described in the parent case study.

## Included

- [`api-summary.json`](api-summary.json): aggregate results for six scenarios run five times each.
- [`chain-summary.json`](chain-summary.json): aggregate results for 30 fifteen-call chains.
- [`coding-task-summary.json`](coding-task-summary.json): externally verified outcomes for three disposable Hermes tasks.
- [`coding-task-evidence.json`](coding-task-evidence.json): sanitised first-attempt hashes, changed-file lists and external test results.
- [`run-manifest.json`](run-manifest.json): model, runtime, request settings and original runner hashes for the reported baseline.
- [`fixtures/identifier-corruption.json`](fixtures/identifier-corruption.json): the failed exact-identifier check.
- [`fixtures/chain-argument-drift.json`](fixtures/chain-argument-drift.json): the three failed long-chain argument checks.

## Deliberately excluded

The complete raw archive is not included because it contains hundreds of repetitive request/response files and environment-specific metadata. It was retained locally for diagnosis when the evaluation ran.

The published files remove:

- private network addresses;
- absolute user and workspace paths;
- credentials and authentication state;
- Hermes profile and session identifiers;
- server-specific cache paths.

## Reading the metrics

`pass_rate` is a scenario- or run-level result. A chain passes only when all 15 calls and the final stop response are correct.

`strict_correct_calls` counts calls whose parsed tool name, arguments and finish reason all matched. A failed run stops immediately, so the public summary distinguishes correct, incorrect and unattempted calls instead of treating unattempted steps as model failures.

The original retained chain summary called the correct-call value `completed_tool_calls_before_failures`. The public names are more explicit about what was measured.

## Reproduction

The scripts in [`../scripts`](../scripts) use only the Python standard library and an OpenAI-compatible `/v1/chat/completions` endpoint.

Example (write generated run data outside the repository):

```bash
python3 ../scripts/tool_call_evaluator.py \
  --base-url http://localhost:8080 \
  --model your-model-alias \
  --out-dir /tmp/local-llm-run-api

python3 ../scripts/chain_evaluator.py \
  --base-url http://localhost:8080 \
  --model your-model-alias \
  --out-dir /tmp/local-llm-run-chain \
  --runs 30 \
  --chain-length 15

python3 ../scripts/hermes_coding_evaluator.py \
  --base-url http://localhost:8080/v1 \
  --model your-model-alias \
  /tmp/local-llm-run-coding
```

The API scripts save request parameters, individual JSONL records and raw requests/responses in the chosen output directory. Pass `--capture-server-metadata` only when saving `/props` and `/slots` is safe; those endpoints can reveal local model paths or launch details. Generated tool actions remain mocked and are not executed.

The public runners are sanitised versions of the retained baseline harnesses. Publication review added type-sensitive JSON comparison, stricter final-response checks and safer metadata defaults. The reported baseline is tied to the original runner hashes in `run-manifest.json`; reruns with the strengthened public scripts are new evaluations rather than byte-for-byte reproductions of the historical run.
