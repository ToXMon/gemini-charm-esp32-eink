# Decision-routing experiment

This is an initial feasibility test, not a quality benchmark or a finished direct-device implementation. It asks a decision model to choose image, song, speech, or clarify for synthetic transcripts. Compare the result with the labels, latency, token usage and billing on Surplus; test ambiguous, negative and out-of-domain cases. A decision model chooses a category; a text model may still be needed to produce a response, write lyrics, or refine prompts.

```sh
pip install -r bridge/requirements.txt
export SURPLUS_API_KEY='your key'
python experiments/decision-routing/evaluate.py --model YOUR_OPENAI_FORMAT_DECISION_MODEL --output decision-results.json --run-paid
```

This sends one billable request per case. Check account access, live sellers, model dialect and price first; no automatic retries are made. No key, request content, or response bodies are written to the results file. The sample set is only a smoke test, manually authored and not independent. For an honest comparison, preregister a larger balanced held-out set, repeat, report confusion matrix, refusals, confidence calibration, latency and actual total cost versus keyword rules and a generative router; review outputs with a caregiver. Don't use private family transcripts in public test data. This script has not been run against a paid endpoint.

Surplus supports two non-interchangeable Decisions dialects; this test sends the OpenAI format. Some models and accounts may not support it. See https://www.surplusintelligence.ai/docs/api-reference/decisions.

## Venice and Surplus Jev-format tests

The Venice catalog's `type=decision` endpoint listed `clef-api` and `jev-latest` on 2026-11-23; availability, beta status, pricing and your account's access can change. Venice and Jev-only sellers on Surplus use the JEV dialect. These are separate billed runs using separate credentials; never send one provider's key to another.

```sh
export VENICE_API_KEY='your Venice key'
python experiments/decision-routing/evaluate.py --provider venice --dialect jev --model clef-api --output clef-results.json --run-paid
python experiments/decision-routing/evaluate.py --provider venice --dialect jev --model jev-latest --output venice-jev-results.json --run-paid
export SURPLUS_API_KEY='your Surplus key'
python experiments/decision-routing/evaluate.py --provider surplus --dialect jev --model jev-1.14 --output surplus-jev-results.json --run-paid
```

Each command can incur charges for each case. The JEV and OpenAI-format paths are covered by mocked tests but have not been validated with live paid calls. Compare actual bills, not just catalog rates, and report failures/refusals as well as accuracy. Venice's DIEM is an inference-credit mechanism, not a decision model or an endpoint; opportunity costs and credit utilization still matter.

To select the lowest estimated DIEM price from supported, explicitly listed online candidates in your authenticated Venice catalog snapshot, pass `--model auto --provider venice --dialect jev`. Selection uses an assumed 1,000 input and 100 output tokens; it is not an actual quote or a quality guarantee. Unknown models, missing prices and models marked offline are excluded. The chosen model is recorded in the results. This selection exists only in this experiment, **not yet in the StickS3 firmware**.
