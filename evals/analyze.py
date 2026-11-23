"""Analyze versioned, manually captured device evaluations without API calls."""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import statistics
import sys

ROUTES={'speech','image','song','clarify'}
STAGES={'transcribe','decision','rewrite','speech','image','music','review','other'}
CURRENCIES={'usd','diem_credit'}


def amount(value):
    if value is None: return None
    if isinstance(value,bool) or not isinstance(value,(int,float,str)): raise ValueError('invalid amount')
    try: result=Decimal(str(value))
    except InvalidOperation as e: raise ValueError('invalid amount') from e
    if not result.is_finite() or result<0: raise ValueError('invalid amount')
    return result


def validate(doc):
    if not isinstance(doc,dict) or doc.get('schema_version')!=1: raise ValueError('unsupported schema_version')
    if not isinstance(doc.get('run_id'),str) or not doc['run_id'] or not isinstance(doc.get('variant'),str) or not doc['variant']: raise ValueError('run_id and variant required')
    if not isinstance(doc.get('dataset_id'),str) or not doc['dataset_id'] or doc.get('scope') not in {'device_end_to_end','decision_only','host_media'}: raise ValueError('dataset_id and scope required')
    if not isinstance(doc.get('cost_capture_complete'), bool): raise ValueError('cost_capture_complete must be boolean')
    cases=doc.get('cases')
    if not isinstance(cases,list) or not cases: raise ValueError('cases must be a nonempty array')
    seen=set()
    for c in cases:
        if not isinstance(c,dict) or not {'observed_route','latency_ms','stages'}.issubset(c) or not isinstance(c.get('case_id'),str) or not c['case_id']: raise ValueError('case_id required')
        trial=c.get('trial'); key=(c['case_id'],trial)
        if not isinstance(trial,int) or isinstance(trial,bool) or trial<1 or key in seen: raise ValueError('invalid or duplicate case_id/trial')
        seen.add(key)
        if doc['scope']=='host_media':
            if 'expected_route' not in c or c['expected_route'] is not None or c.get('observed_route') is not None: raise ValueError('host media has no routing result')
        elif c.get('expected_route') not in ROUTES or c.get('observed_route') not in ROUTES|{None}: raise ValueError('invalid route')
        if c.get('status') not in {'completed','failed','cancelled','unknown'}: raise ValueError('invalid status')
        review=c.get('review')
        if review not in {'accepted','rejected','pending'}: raise ValueError('invalid review')
        if c['status']!='completed' and review=='accepted': raise ValueError('failed case cannot be accepted')
        latency=c.get('latency_ms')
        if latency is not None and (isinstance(latency,bool) or not isinstance(latency,(int,float)) or not math.isfinite(latency) or latency<0): raise ValueError('invalid latency')
        stages=c.get('stages')
        if not isinstance(stages,list): raise ValueError('stages must be array')
        for stage in stages:
            if not isinstance(stage,dict) or stage.get('stage') not in STAGES or stage.get('status') not in {'ok','failed','unknown'}: raise ValueError('invalid stage')
            cost=stage.get('cost')
            if not isinstance(cost,dict) or cost.get('currency') not in CURRENCIES or cost.get('kind') not in {'actual','estimate','unknown'}: raise ValueError('invalid cost')
            value=amount(cost.get('amount'))
            if (cost['kind']=='unknown') != (value is None): raise ValueError('unknown costs must have null amount and known costs require amount')
        if 'expected_stages' in c and (not isinstance(c['expected_stages'],list) or any(x not in STAGES for x in c['expected_stages'])): raise ValueError('invalid expected_stages')
        if 'expected_transcript' in c or 'observed_transcript' in c:
            if not all(isinstance(c.get(k),str) for k in ('expected_transcript','observed_transcript')): raise ValueError('transcripts must be paired strings')
    return doc


def word_error_rate(reference,hypothesis):
    ref=reference.casefold().split(); hyp=hypothesis.casefold().split()
    if not ref: return None
    prev=list(range(len(hyp)+1))
    for i,a in enumerate(ref,1):
        curr=[i]
        for j,b in enumerate(hyp,1): curr.append(min(curr[-1]+1,prev[j]+1,prev[j-1]+(a!=b)))
        prev=curr
    return {'errors':prev[-1], 'reference_words':len(ref), 'wer':prev[-1]/len(ref)}


def percentile(values,p):
    if not values: return None
    ordered=sorted(values);return ordered[max(0,math.ceil(p*len(ordered))-1)]


def analyze(doc):
    validate(doc); cases=doc['cases']; n=len(cases)
    confusion={r:{o:0 for o in sorted(ROUTES|{'missing'})} for r in sorted(ROUTES)}
    totals={currency:{'actual':Decimal(0),'estimate':Decimal(0),'unknown':0} for currency in sorted(CURRENCIES)}
    per_stage={}; wers=[]
    for c in cases:
        if c['expected_route'] is not None: confusion[c['expected_route']][c['observed_route'] or 'missing']+=1
        if 'expected_transcript' in c:
            w=word_error_rate(c['expected_transcript'],c['observed_transcript'])
            if w is not None: wers.append(w)
        for stage in c['stages']:
            cost=stage['cost']; bucket=totals[cost['currency']]
            if cost['kind']=='unknown': bucket['unknown']+=1
            else: bucket[cost['kind']]+=amount(cost['amount'])
            key=stage['stage'];per_stage[key]=per_stage.get(key,0)+1
    accepted=sum(c['review']=='accepted' for c in cases)
    prices={}
    for currency,t in totals.items():
        # Never blend actual and estimated charges; exclude unknown totals from unit-cost claims.
        complete=doc['cost_capture_complete'] and t['unknown']==0 and t['estimate']==0
        reviewed=all(c['review']!='pending' for c in cases)
        prices[currency]={'known_actual':str(t['actual']),'known_estimate':str(t['estimate']),'unknown_stage_count':t['unknown'],
                          'actual_cost_per_accepted':str(t['actual']/accepted) if accepted and complete and reviewed else None,
                          'complete_actual':complete,'all_cases_reviewed':reviewed}
    measured=[c for c in cases if 'expected_stages' in c]
    trajectories=sum([s['stage'] for s in c['stages']]==c['expected_stages'] and all(s['status']=='ok' for s in c['stages']) for c in measured)
    lat=[c['latency_ms'] for c in cases if c['latency_ms'] is not None]
    routed=[c for c in cases if c['expected_route'] is not None]
    return {'schema_version':1,'run_id':doc['run_id'],'variant':doc['variant'],'dataset_id':doc['dataset_id'],'scope':doc['scope'],'case_trials':n,
            'route_correct':sum(c['expected_route']==c['observed_route'] for c in routed),
            'route_accuracy':sum(c['expected_route']==c['observed_route'] for c in routed)/len(routed) if routed else None,
            'route_confusion':confusion,'trajectory':{'measured':len(measured),'passed':trajectories},'statuses':dict(Counter(c['status'] for c in cases)),
            'review':dict(Counter(c['review'] for c in cases)), 'accepted_fraction_of_all':accepted/n,
            'acceptance_among_reviewed':accepted/sum(c['review']!='pending' for c in cases) if any(c['review']!='pending' for c in cases) else None,
            'latency_ms':{'samples':len(lat),'p50':statistics.median(lat) if lat else None,'p95_nearest_rank':percentile(lat,.95)},
            'word_error_rate':{'cases':len(wers),'errors':sum(w['errors'] for w in wers),'reference_words':sum(w['reference_words'] for w in wers),'aggregate':sum(w['errors'] for w in wers)/sum(w['reference_words'] for w in wers) if wers else None},
            'costs':prices,'stage_counts':per_stage}


def compare(a,b):
    validate(a);validate(b)
    if a['dataset_id']!=b['dataset_id'] or a['scope']!=b['scope']: raise ValueError('runs must share dataset_id and scope')
    left={(c['case_id'],c['trial']):c for c in a['cases']};right={(c['case_id'],c['trial']):c for c in b['cases']}
    common=sorted(left.keys()&right.keys()); disagree=[k for k in common if left[k]['expected_route']!=right[k]['expected_route']]
    if disagree: raise ValueError('paired cases disagree on expected route')
    routed=[k for k in common if left[k]['expected_route'] is not None]
    return {'left':a['run_id'],'right':b['run_id'],'matched':len(common),'left_only':len(left.keys()-right.keys()),'right_only':len(right.keys()-left.keys()),
            'route_left_only_correct':sum(left[k]['observed_route']==left[k]['expected_route'] and right[k]['observed_route']!=right[k]['expected_route'] for k in routed) if routed else None,
            'route_right_only_correct':sum(right[k]['observed_route']==right[k]['expected_route'] and left[k]['observed_route']!=left[k]['expected_route'] for k in routed) if routed else None,
            'both_correct':sum(left[k]['observed_route']==left[k]['expected_route'] and right[k]['observed_route']==right[k]['expected_route'] for k in routed) if routed else None}


def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run');p.add_argument('--compare',help='Optional second run; pairs case_id and trial');p.add_argument('--output',help='New report file, never overwritten')
    args=p.parse_args()
    try:
        run=load(args.run); result={'report':analyze(run)}
        if args.compare:
            other=load(args.compare);result['comparison_run']=analyze(other);result['paired_comparison']=compare(run,other)
        text=json.dumps(result,indent=2,allow_nan=False)+'\n'
        if args.output:
            with Path(args.output).open('x',encoding='utf-8') as f: f.write(text)
        else: print(text,end='')
    except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as e:
        print('Evaluation error:',str(e),file=sys.stderr);return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
