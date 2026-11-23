"""Read-only credential checks; never print keys or provider response bodies."""
import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys

import httpx
from private_config import ConfigError, load_keys


def positive(value):
    try:
        amount = Decimal(str(value))
        return amount.is_finite() and amount > 0
    except (InvalidOperation, ValueError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default=str(Path(__file__).resolve().parents[1] / '.env'))
    args = parser.parse_args()
    try:
        keys = load_keys(args.env)
    except ConfigError as e:
        raise SystemExit(str(e)) from None
    checks = [
        ('Venice', 'https://api.venice.ai/api/v1/api_keys/rate_limits', keys['VENICE_API_KEY']),
        ('Surplus', 'https://api.surplusintelligence.ai/v1/buyer/me', keys['SURPLUS_API_KEY']),
    ]
    failed = False
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        for name, url, key in checks:
            try:
                response = client.get(url, headers={'Authorization': 'Bearer ' + key})
                if response.status_code != 200:
                    print(f'{name}: account read returned HTTP {response.status_code}; key scope may restrict it.')
                    failed = True
                    continue
                result = response.json()
                if name == 'Venice':
                    data = result.get('data', {})
                    permitted = data.get('accessPermitted')
                    balance = positive(data.get('balances', {}).get('DIEM'))
                else:
                    permitted = True
                    balance = positive(result.get('credit_balance_usdc'))
                access = 'allowed' if permitted is True else 'not confirmed'
                funds = 'positive' if balance is True else 'zero' if balance is False else 'not reported'
                print(f'{name}: account read succeeded; access {access}; credit {funds}.')
                if permitted is not True:
                    failed = True
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                print(f'{name}: account read failed; no response details were printed.')
                failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
