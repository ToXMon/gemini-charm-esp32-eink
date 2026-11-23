"""Estimate a single provider charge from a caller-supplied dated rate, never an invoice."""
import argparse
import json
from evals.analyze import amount


def token_estimate(input_tokens, output_tokens, input_per_million, output_per_million):
    if any(isinstance(x,bool) or not isinstance(x,int) or x<0 for x in (input_tokens,output_tokens)):
        raise ValueError('token counts must be nonnegative integers')
    in_rate=amount(input_per_million);out_rate=amount(output_per_million)
    if in_rate is None or out_rate is None: raise ValueError('both rates required')
    return (in_rate*input_tokens+out_rate*output_tokens)/1000000


def unit_estimate(units, price_per_unit):
    u=amount(units);p=amount(price_per_unit)
    if u is None or p is None: raise ValueError('units and rate required')
    return u*p


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--currency',required=True,choices=['usd','diem_credit']);p.add_argument('--price-source',required=True);p.add_argument('--price-as-of',required=True,help='Date of pricing snapshot, YYYY-MM-DD')
    sub=p.add_subparsers(dest='method',required=True)
    t=sub.add_parser('tokens');t.add_argument('--input-tokens',required=True,type=int);t.add_argument('--output-tokens',required=True,type=int);t.add_argument('--input-per-million',required=True);t.add_argument('--output-per-million',required=True)
    u=sub.add_parser('units');u.add_argument('--units',required=True);u.add_argument('--price-per-unit',required=True);u.add_argument('--unit-name',required=True)
    a=p.parse_args()
    from datetime import date
    try:
        date.fromisoformat(a.price_as_of)
        if a.method=='tokens': value=token_estimate(a.input_tokens,a.output_tokens,a.input_per_million,a.output_per_million)
        else: value=unit_estimate(a.units,a.price_per_unit)
    except ValueError as e: p.error(str(e))
    print(json.dumps({'kind':'estimate','currency':a.currency,'amount':str(value),'price_source':a.price_source,'price_as_of':a.price_as_of,'method':a.method,'unit_name':getattr(a,'unit_name',None)},indent=2))

if __name__=='__main__':main()
