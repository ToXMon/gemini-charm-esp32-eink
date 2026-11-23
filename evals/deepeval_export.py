"""Export route decisions in a JSON format usable to construct DeepEval LLMTestCase objects."""
import argparse
import json
from pathlib import Path
from evals.analyze import validate


def export(doc):
    validate(doc)
    return [{'input':'Route for case '+c['case_id'], 'actual_output':c['observed_route'] or 'MISSING',
             'expected_output':c['expected_route'], 'metadata':{'case_id':c['case_id'],'trial':c['trial'],'scope':doc['scope']}}
            for c in doc['cases']]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');p.add_argument('--output',required=True);a=p.parse_args()
    records=export(json.loads(Path(a.input).read_text(encoding='utf-8')))
    with Path(a.output).open('x',encoding='utf-8') as f: json.dump(records,f,indent=2);f.write('\n')

if __name__=='__main__':main()
