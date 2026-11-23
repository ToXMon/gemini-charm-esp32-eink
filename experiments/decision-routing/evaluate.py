"""Small, paid, opt-in experiment for Surplus's OpenAI-format Decisions API."""
import argparse
import json
import os
from pathlib import Path
import statistics
from decimal import Decimal, InvalidOperation
import time
import httpx

URLS = {'surplus':'https://api.surplusintelligence.ai/v1/decisions', 'venice':'https://api.venice.ai/api/v1/decisions'}
CHOICES = ['image','song','speech','clarify']
VENICE_TESTED_DIALECT_MODELS = {'jev-latest', 'clef-api'}
INSTRUCTION = ('Choose the single output the user wants: image, song, or spoken response. '
               'Choose clarify if the output or reference is unclear. Consider instructions about what not to do.')


def cheapest_venice_model(catalog, input_tokens=1000, output_tokens=100):
    """Choose among explicitly supported JEV models by indicative DIEM cost."""
    candidates=[]
    for item in catalog.get('data',[]):
        spec=item.get('model_spec') or {}; model=item.get('id')
        if model not in VENICE_TESTED_DIALECT_MODELS or item.get('type') != 'decision' or spec.get('offline') is not False: continue
        try:
            price=spec['pricing']; inp=Decimal(str(price['input']['diem'])); out=Decimal(str(price['output']['diem']))
            if not inp.is_finite() or not out.is_finite() or inp < 0 or out < 0: continue
            candidates.append((inp*input_tokens+out*output_tokens, model))
        except (KeyError,TypeError,InvalidOperation): continue
    if not candidates: raise ValueError('No eligible priced decision models in Venice catalog')
    return min(candidates)[1]


def evaluate(client, model, cases, provider="surplus", dialect="openai"):
    if provider == "venice" and dialect != "jev": raise ValueError("Venice requires JEV format")
    rows=[]
    for case in cases:
        body={'model':model,'input':case['input'],'questions':[{'type':'choice','name':'route','instructions':INSTRUCTION,'choices':[{'value':x} for x in CHOICES]}]}
        if dialect == 'jev':
            body={'model':model,'state':case['input'],'questions':{'route':{'type':'choice','instructions':INSTRUCTION,'criteria':{x:None for x in CHOICES}}}}
        start=time.monotonic()
        try:
            response=client.post(URLS[provider],json=body)
            latency=time.monotonic()-start
            response.raise_for_status()
            payload=response.json()
            answer=payload['answers']['route'] if dialect=='jev' else payload['answers'][0]
            choice=answer.get('choice') if answer.get('type')=='choice' else None
            rows.append({'id':case['id'],'expected':case['expected'],'choice':choice,'confidence':answer.get('confidence'),'latency_ms':round(latency*1000),'usage':payload.get('usage'),'status':'ok' if choice in CHOICES else 'refusal_or_invalid'})
        except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as e:
            rows.append({'id':case['id'],'expected':case['expected'],'choice':None,'status':'error','error_type':type(e).__name__,'latency_ms':round((time.monotonic()-start)*1000)})
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True,help='Decision model ID, or auto for Venice catalog selection')
    p.add_argument('--provider',choices=['surplus','venice'],default='surplus')
    p.add_argument('--dialect',choices=['openai','jev'],default='openai')
    p.add_argument('--cases',default=str(Path(__file__).with_name('cases.json')))
    p.add_argument('--output',required=True,help='New results JSON file; never overwrites')
    p.add_argument('--run-paid',action='store_true',help='Actually issue paid Surplus requests')
    args=p.parse_args()
    if not args.run_paid: p.error('Pass --run-paid to make billable calls')
    if args.provider == 'venice' and args.dialect != 'jev': p.error('Venice requires --dialect jev')
    key_name='VENICE_API_KEY' if args.provider=='venice' else 'SURPLUS_API_KEY'
    key=os.getenv(key_name,'')
    if not key: p.error('Set '+key_name+' in your environment')
    output=Path(args.output)
    if output.exists(): p.error('Output already exists')
    cases=json.loads(Path(args.cases).read_text())
    if not cases or len(cases)>100: p.error('Supply 1–100 cases')
    if any(not isinstance(c.get('input'),str) or c.get('expected') not in CHOICES for c in cases): p.error('Invalid case')
    model=args.model
    with httpx.Client(headers={'Authorization':'Bearer '+key},timeout=30) as client:
        if model == 'auto':
            if args.provider != 'venice': p.error('--model auto is only supported for Venice')
            response=client.get('https://api.venice.ai/api/v1/models',params={'type':'decision'}); response.raise_for_status()
            model=cheapest_venice_model(response.json())
        rows=evaluate(client,model,cases,args.provider,args.dialect)
    latencies=[row['latency_ms'] for row in rows]
    result={'provider':args.provider,'dialect':args.dialect,'model':model,'cases':len(rows),'correct':sum(r['choice']==r['expected'] for r in rows),'errors_or_refusals':sum(r['status']!='ok' for r in rows),'median_latency_ms':statistics.median(latencies),'rows':rows}
    with output.open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

if __name__=='__main__': main()
