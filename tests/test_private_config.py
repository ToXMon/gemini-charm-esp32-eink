import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from private_config import ConfigError, load_keys


class PrivateConfigTests(unittest.TestCase):
    def test_valid_owner_only_file_and_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text("# test\nVENICE_API_KEY='test-venice-key'\nSURPLUS_API_KEY=test-surplus-key\n")
            os.chmod(path, 0o600)
            keys = load_keys(path)
            self.assertEqual(keys['VENICE_API_KEY'], 'test-venice-key')
            self.assertEqual(keys['SURPLUS_API_KEY'], 'test-surplus-key')
            os.chmod(path, 0o644)
            with self.assertRaises(ConfigError):
                load_keys(path)

    def test_missing_duplicate_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text('VENICE_API_KEY=\nSURPLUS_API_KEY=test-surplus-key\n')
            os.chmod(path, 0o600)
            with self.assertRaises(ConfigError):
                load_keys(path)
            path.write_text('VENICE_API_KEY=test-venice-key\nVENICE_API_KEY=another-test-key\nSURPLUS_API_KEY=test-surplus-key\n')
            with self.assertRaises(ConfigError):
                load_keys(path)
            link = Path(tmp) / 'link'
            link.symlink_to(path)
            with self.assertRaises(ConfigError):
                load_keys(link)


if __name__ == '__main__':
    unittest.main()
