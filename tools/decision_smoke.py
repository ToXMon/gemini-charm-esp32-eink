"""Run exactly one paid synthetic Venice decision; no automatic retry."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import time

import httpx
from private_config import ConfigError, load_keys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('routing_eval', ROOT / 'experiments/decision-routing/evaluate.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-paid', action='store_true', help='Make one chargeable provider call')
    parser.add_argument('--env', default=str(ROOT / '.env'))
    args = parser.parse_args()
    if not args.run_paid:
        raise SystemExit('Pass --run-paid to make the single synthetic decision call.')
    try:
        key = load_keys(args.env)['VENICE_API_KEY']
    except ConfigError as e:
        raise SystemExit(str(e)) from None
    private = ROOT / 'evals/private'
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(private, 0o700)
    output = private / ('venice-smoke-' + time.strftime('%Y%m%d-%H%M%S', time.gmtime()) + '.json')
    case = {'id': 'synthetic-blue-boat', 'input': 'Please draw a blue sailboat.', 'expected': 'image'}
    with httpx.Client(headers={'Authorization': 'Bearer ' + key}, timeout=30,
                      follow_redirects=False, trust_env=False) as client:
        try:
            catalog = client.get('https://api.venice.ai/api/v1/models', params={'type': 'decision'})
            catalog.raise_for_status()
            model = evaluation.cheapest_venice_model(catalog.json())
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise SystemExit('Catalog check failed; no decision was submitted.') from None
        # Persist an uncertain marker before sending. A crash or lost response
        # must not be mistaken for a free or unsubmitted request.
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump({'status': 'submission_uncertain', 'model': model}, f)
            f.flush()
            os.fsync(f.fileno())
        started = time.monotonic()
        try:
            rows = evaluation.evaluate(client, model, [case], provider='venice', dialect='jev')
        except Exception:
            rows = [{'id': case['id'], 'expected': case['expected'], 'choice': None,
                     'status': 'error', 'error_type': 'UnexpectedError',
                     'latency_ms': round((time.monotonic()-started)*1000)}]
    for row in rows:
        if row.get('choice') not in evaluation.CHOICES:
            row['choice'] = None
        confidence = row.get('confidence')
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not math.isfinite(confidence):
            row['confidence'] = None
        usage = row.get('usage')
        if isinstance(usage, dict):
            row['usage'] = {k: v for k, v in usage.items()
                            if k in ('input_tokens', 'output_tokens', 'total_tokens') and
                            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
        else:
            row['usage'] = None
    result = {'provider': 'venice', 'dialect': 'jev', 'model': model, 'cases': len(rows),
              'correct': sum(r['choice'] == r['expected'] for r in rows),
              'errors_or_refusals': sum(r['status'] != 'ok' for r in rows),
              'median_latency_ms': rows[0]['latency_ms'], 'rows': rows}
    with tempfile.NamedTemporaryFile(mode='w', dir=private, prefix='.decision-', delete=False) as f:
        tmp = f.name
        json.dump(result, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, output)
    print('Decision test:', rows[0]['status'], 'model:', model,
          'matched expected route:', rows[0]['choice'] == rows[0]['expected'],
          'latency_ms:', rows[0]['latency_ms'])
    print('Result saved privately. Actual charge remains unknown until reconciled with Venice.')


if __name__ == '__main__':
    main()
