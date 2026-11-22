import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from bridge import media

class SpeechTests(unittest.TestCase):
    def test_narrates_reviewed_file(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, content=b'RIFFtestWAVE')
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'reviewed.txt'
            output = Path(directory) / 'story.wav'
            source.write_text('Hello, little duck.', encoding='utf-8')
            argv = ['media.py','speech','--model','speech-model','--text-file',str(source),'--output',str(output)]
            with patch.object(media, 'KEY', 'fake'), patch.object(media.httpx, 'Client', return_value=client), patch.object(sys, 'argv', argv):
                media.main()
            self.assertEqual(output.read_bytes(), b'RIFFtestWAVE')
            self.assertEqual(json.loads(requests[0].content)['input'], 'Hello, little duck.')
            self.assertTrue(requests[0].url.path.endswith('/audio/speech'))

if __name__ == '__main__': unittest.main()
