"""Import private host-only Surplus smoke results without inventing route labels."""
import argparse
import json
from pathlib import Path
from evals.analyze import validate

STAGES={'speech':'speech','transcription':'transcribe','image':'image',
        'song':'music','song60':'music','song_default':'music'}
TERMINAL_FAILURE={'http_error','failed','expired','canceled','cancelled','invalid_response','unsupported_format'}
REFERENCE='Hello from my little device.'


def convert(state, run_id, dataset_id, transcript=None):
    if not isinstance(state,dict):raise ValueError('invalid host smoke state')
    cases=[]
    for name,stage in STAGES.items():
        if name not in state:continue
        row=state[name]
        if not isinstance(row,dict):raise ValueError('invalid host smoke record')
        status=row.get('status')
        artifact_ok=stage!='music' or isinstance(row.get('artifact_bytes'),int) and row['artifact_bytes']>0
        success=status=='succeeded' and artifact_ok
        failure=status in TERMINAL_FAILURE
        stage_status='ok' if success else 'failed' if failure else 'unknown'
        result_status='completed' if success else 'failed' if failure else 'unknown'
        actual=row.get('actual_usd')
        cost={'currency':'usd','kind':'actual' if actual is not None else 'unknown','amount':actual}
        case={'case_id':name,'trial':1,'expected_route':None,'observed_route':None,
              'status':result_status,'review':'pending',
              # Music submit latency is not end-to-end generation latency.
              'latency_ms':None if stage=='music' else row.get('latency_ms'),
              'expected_stages':[stage],'stages':[{'stage':stage,'status':stage_status,'cost':cost}]}
        if name=='transcription' and success and transcript is not None:
            case['expected_transcript']=REFERENCE;case['observed_transcript']=transcript
        cases.append(case)
    run={'schema_version':1,'run_id':run_id,'variant':'surplus-host-smoke',
         'scope':'host_media','dataset_id':dataset_id,'cost_capture_complete':False,'cases':cases}
    return validate(run)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('state');p.add_argument('--run-id',required=True);p.add_argument('--dataset-id',required=True)
    p.add_argument('--output',required=True);p.add_argument('--transcript')
    a=p.parse_args()
    state=json.loads(Path(a.state).read_text(encoding='utf-8'))
    transcript=Path(a.transcript).read_text(encoding='utf-8') if a.transcript else None
    run=convert(state,a.run_id,a.dataset_id,transcript)
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(run,f,indent=2);f.write('\n')


if __name__=='__main__':main()
