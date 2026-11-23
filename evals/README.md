# Device evaluation and cost analysis

This is an **offline-first analysis harness**, inspired by the DataTalksClub media course, DeepEval, and ATTEST. No API calls or model judges run when using these commands. The fixtures are **invented synthetic examples**, not measurements or a comparison claim. The direct Venice/Surplus device firmware does not yet exist and no automatic device trace capture is implemented. Until instrumentation is added, record real observations manually and retain original bills privately.

## Try it now without credentials

```sh
python -m evals.analyze evals/fixtures/sample-venice-surplus.json --compare evals/fixtures/sample-gemini.json
python -m unittest discover -s tests -v
```

For asset checks, install `bridge/requirements.txt` for Pillow:

```sh
python -m evals.check_media image PATH_TO_JPEG_OR_PNG --width 135 --height 240
python -m evals.check_media audio PATH_TO_WAV --max-seconds 55
```

These checks inspect file structure and format, not whether content is accurate, appropriate, pleasant, or safe. The audio checker handles uncompressed WAV, not MP3 or device playback. A full-size generated image may intentionally differ from the resized device display image.

## Record a real run

1. Create a versioned, synthetic golden set with case IDs, expected routes, and (only for consented test audio) reference transcripts. Test easy, ambiguous, mixed, negated, noisy, and out-of-scope requests. Use the same input recordings, settings, and case IDs for Gemini and Venice/Surplus. Record the **same** `dataset_id`, scope and trial IDs; version the dataset if it changes. The harness trusts those labels—it cannot verify recordings are identical.
2. Copy `fixtures/sample-venice-surplus.json` to `evals/private/your-run.json` after creating `evals/private/`. Replace every example with actual observations. Name the run and variant; set `scope` to `device_end_to_end` or `decision_only`. A case contains its expected and observed route (or `null` for failure), status, caregiver review, end-to-end latency in milliseconds or `null`, and ordered stages. `expected_stages` is optional and checked for **exact ordered stages and successful statuses**, not detailed arguments or content.
3. Add one cost entry per chargeable stage or attempt, including failed and retried calls. Use `actual` only for provider-reported settled amounts, `estimate` for rate-card calculations, and `unknown` with `amount: null` when unavailable. `currency` is `usd` for monetary charges or `diem_credit` for consumed Venice credits, both in dollar-denominated units. Zero is valid only when actually known. Never convert DIEM credits into cash or add them to USD spending without an explicitly justified economic model.
4. Set `cost_capture_complete: true` only after reconciling **all** chargeable calls in the scoped run, including review/judge calls, failures, retries and any known platform fees. It is a user attestation, not automatic billing verification. Incomplete captures must be `false`. Cost per accepted result is omitted when costs are unknown/estimated, reviews are pending, or capture is incomplete. Even a complete inference run does not automatically include device purchase, hotspot, hosting, power or DIEM acquisition/opportunity costs.
5. Mark each completed artifact `accepted`, `rejected` or `pending` only after caregiver review using the [versioned rubric](rubric.md). A failed run cannot be accepted. Save test artifacts, transcript pairs, provider bills and notes in `evals/private/` (Git-ignored); do not publish child recordings, names, keys, provider response bodies or private prompts. This directory is ignored, **not encrypted**.
6. Analyze each run and compare paired `case_id` + `trial` values:

```sh
python -m evals.analyze evals/private/surplus-run.json --compare evals/private/gemini-run.json --output evals/private/report.json
```

The analyzer refuses mismatched scope/dataset or conflicting route labels, reports unmatched cases and never silently treats them as paired. Reports include route confusion and accuracy (missing routes count as wrong), exact stage sequence, human review counts, p50/p95 nearest-rank latency, whitespace/case-normalized word error rate (WER; punctuation still matters), and separate actual, estimated and unknown costs. Failed attempts count toward cost. P95 is unstable for small samples; do not present tiny synthetic runs as a benchmark.

## Existing decision experiment

`experiments/decision-routing/evaluate.py` makes paid Venice or Surplus calls only with `--run-paid`. Its output contains route decisions and usage, not a device trajectory or verified bill. To analyze one completed result, supply the dataset ID used for that run:

```sh
python -m evals.import_decision evals/private/decision-results.json --run-id decision-1 --dataset-id routing-v1 --output evals/private/decision-run.json
python -m evals.analyze evals/private/decision-run.json
```

Imported runs are marked `decision_only`, reviews are pending, and costs are unknown. They cannot be compared to `device_end_to_end` runs. The importer deliberately does not derive costs from token usage.

## Estimate a cost from a dated price snapshot

These examples use arbitrary rates, **not live prices**. Provide the exact provider rate, unit, timestamp and applicable usage; different media have different billing units and minimums. Estimates exclude unentered fees and do not become actual charges.

```sh
python -m evals.cost --currency usd --price-source 'example rate card' --price-as-of 2026-11-23 tokens --input-tokens 1000 --output-tokens 200 --input-per-million 1.20 --output-per-million 4.00
python -m evals.cost --currency usd --price-source 'example per image' --price-as-of 2026-11-23 units --units 1 --price-per-unit 0.02 --unit-name image
```

Copy the resulting amount into a stage with `kind: estimate`, preserving the source/date in your private evidence. If Gemini charges by audio tokens or minute, use its actual documented unit and bill for that model; do not assume its Live audio is equivalent to separate transcription and TTS. Make an apples-to-apples quality/latency comparison first.

## DeepEval interoperability

Export sanitized route-only test cases:

```sh
python -m evals.deepeval_export evals/private/surplus-run.json --output evals/private/deepeval-cases.json
```

Each JSON object has `input`, `actual_output`, `expected_output`, and `metadata` and can be passed to `deepeval.test_case.LLMTestCase(**row)` after installing DeepEval separately. This export contains case IDs and route labels, not the underlying prompts, audio or images. It is useful for an exact-route metric, **not sufficient for evaluating image/audio quality or a model-based content judge**. DeepEval is an optional external tool, is not installed by this project, and its integration has not been run against the DeepEval package. G-Eval/JevEval and other model judges may send content to a provider and incur additional costs; configure one deliberately, evaluate it against human labels, and include its charges as review stages. See [DeepEval](https://github.com/confident-ai/deepeval) and [JevEval](https://deepeval.com/docs/metrics-jev-eval).

ATTEST-inspired reporting here separates route, step sequence and outcome; it **does not implement ATTEST's sandbox, prompt-injection tests, containment score or evidence ledger**. The course's golden-set and cost-per-accepted concepts inform the workflow; several later course lessons are outlines, and no MLflow integration is claimed. Promote a verified synthetic failure into a new, versioned regression case; don't publish private device traces.
