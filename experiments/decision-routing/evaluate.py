"""Small, paid, opt-in experiment for Surplus's OpenAI-format Decisions API."""
import argparse
import json
import os
from pathlib import Path
import statistics
import time
import httpx

URL = 'https://api.surplusintelligence.ai/v1/decisions'
CHOICES = ['image','song','speech','clarify']
INSTRUCTION = ('Choose the single output the user wants: image, song, or spoken response. '
               'Choose clarify if the output or reference is unclear. Consider instructions about what not to do.')


def evaluate(client, model, cases):
    rows=[]
    for case in cases:
        body={'model':model,'input':case['input'],'questions':[{'type':'choice','name':'route','instructions':INSTRUCTION,'choices':[{'value':x} for x in CHOICES]}]}
        start=time.monotonic()
        try:
            response=client.post(URL,json=body)
            latency=time.monotonic()-start
            response.raise_for_status()
            payload=response.json()
            answer=payload['answers'][0]
            choice=answer.get('choice') if answer.get('type')=='choice' else None
            rows.append({'id':case['id'],'expected':case['expected'],'choice':choice,'confidence':answer.get('confidence'),'latency_ms':round(latency*1000),'usage':payload.get('usage'),'status':'ok' if choice in CHOICES else 'refusal_or_invalid'})
        except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as e:
            rows.append({'id':case['id'],'expected':case['expected'],'choice':None,'status':'error','error_type':type(e).__name__,'latency_ms':round((time.monotonic()-start)*1000)})
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True,help='Decision model supporting the OpenAI Decisions dialect')
    p.add_argument('--cases',default=str(Path(__file__).with_name('cases.json')))
    p.add_argument('--output',required=True,help='New results JSON file; never overwrites')
    p.add_argument('--run-paid',action='store_true',help='Actually issue paid Surplus requests')
    args=p.parse_args()
    if not args.run_paid: p.error('Pass --run-paid to make billable calls')
    key=os.getenv('SURPLUS_API_KEY','')
    if not key: p.error('Set SURPLUS_API_KEY in your environment')
    output=Path(args.output)
    if output.exists(): p.error('Output already exists')
    cases=json.loads(Path(args.cases).read_text())
    if not cases or len(cases)>100: p.error('Supply 1–100 cases')
    if any(not isinstance(c.get('input'),str) or c.get('expected') not in CHOICES for c in cases): p.error('Invalid case')
    with httpx.Client(headers={'Authorization':'Bearer '+key},timeout=30) as client: rows=evaluate(client,args.model,cases)
    latencies=[row['latency_ms'] for row in rows]
    result={'model':args.model,'cases':len(rows),'correct':sum(r['choice']==r['expected'] for r in rows),'errors_or_refusals':sum(r['status']!='ok' for r in rows),'median_latency_ms':statistics.median(latencies),'rows':rows}
    with output.open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

if __name__=='__main__': main()
