import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_providers


class Response:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class Client:
    def __init__(self, **kwargs):
        assert kwargs['follow_redirects'] is False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers):
        if 'venice.ai' in url:
            assert headers['Authorization'] == 'Bearer test-venice-key'
            return Response({'data': {'accessPermitted': True, 'balances': {'DIEM': 1}}})
        assert headers['Authorization'] == 'Bearer test-surplus-key'
        return Response({'credit_balance_usdc': '3.0'})


class ProviderCheckTests(unittest.TestCase):
    def test_outputs_only_sanitized_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text('VENICE_API_KEY=test-venice-key\nSURPLUS_API_KEY=test-surplus-key\n')
            os.chmod(path, 0o600)
            output = io.StringIO()
            with patch.object(sys, 'argv', ['check_providers', '--env', str(path)]), \
                 patch.object(check_providers.httpx, 'Client', Client), contextlib.redirect_stdout(output):
                self.assertEqual(check_providers.main(), 0)
            text = output.getvalue()
            self.assertIn('Venice: account read succeeded', text)
            self.assertIn('Surplus: account read succeeded', text)
            self.assertNotIn('test-venice-key', text)
            self.assertNotIn('test-surplus-key', text)


if __name__ == '__main__':
    unittest.main()
