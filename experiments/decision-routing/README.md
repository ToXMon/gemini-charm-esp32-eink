# Decision-routing experiment

This is an initial feasibility test, not a quality benchmark or a finished direct-device implementation. It asks a decision model to choose image, song, speech, or clarify for synthetic transcripts. Compare the result with the labels, latency, token usage and billing on Surplus; test ambiguous, negative and out-of-domain cases. A decision model chooses a category; a text model may still be needed to produce a response, write lyrics, or refine prompts.

```sh
pip install -r bridge/requirements.txt
export SURPLUS_API_KEY='your key'
python experiments/decision-routing/evaluate.py --model YOUR_OPENAI_FORMAT_DECISION_MODEL --output decision-results.json --run-paid
```

This sends one billable request per case. Check account access, live sellers, model dialect and price first; no automatic retries are made. No key, request content, or response bodies are written to the results file. The sample set is only a smoke test, manually authored and not independent. For an honest comparison, preregister a larger balanced held-out set, repeat, report confusion matrix, refusals, confidence calibration, latency and actual total cost versus keyword rules and a generative router; review outputs with a caregiver. Don't use private family transcripts in public test data. This script has not been run against a paid endpoint.

Surplus supports two non-interchangeable Decisions dialects; this test sends the OpenAI format. Some models and accounts may not support it. See https://www.surplusintelligence.ai/docs/api-reference/decisions.
