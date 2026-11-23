"""Import the existing decision-only experiment; unknown costs stay unknown."""
import argparse
import json
from pathlib import Path
from evals.analyze import ROUTES, validate


def convert(doc, run_id, dataset_id):
    if doc.get('provider') not in {'venice','surplus'} or not isinstance(doc.get('rows'),list) or not doc['rows']:
        raise ValueError('unsupported decision report')
    currency='diem_credit' if doc['provider']=='venice' else 'usd'
    cases=[]
    for row in doc['rows']:
        choice=row.get('choice'); ok=row.get('status')=='ok' and choice in ROUTES
        cases.append({'case_id':row['id'],'trial':1,'expected_route':row['expected'],
            'observed_route':choice if ok else None,'status':'completed' if ok else 'failed',
            'review':'pending','latency_ms':row.get('latency_ms'), 'expected_stages':['decision'],
            'stages':[{'stage':'decision','status':'ok' if ok else 'failed',
                'cost':{'currency':currency,'kind':'unknown','amount':None}}]})
    result={'schema_version':1,'run_id':run_id,'variant':doc['provider']+':'+str(doc.get('model','unknown')),
            'scope':'decision_only','dataset_id':dataset_id,'cost_capture_complete':False,'cases':cases}
    return validate(result)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');p.add_argument('--run-id',required=True);p.add_argument('--dataset-id',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();doc=json.loads(Path(a.input).read_text(encoding='utf-8'));converted=convert(doc,a.run_id,a.dataset_id)
    with Path(a.output).open('x',encoding='utf-8') as f: json.dump(converted,f,indent=2);f.write('\n')

if __name__=='__main__': main()
