import json
from pathlib import Path
import sys
import tempfile
import unittest

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import media_smoke


class MediaSmokeTests(unittest.TestCase):
    def test_marks_submission_before_sending_and_never_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';state={};calls=[]
            class BytesStream(httpx.SyncByteStream):
                def __iter__(self):
                    yield b'example'
            def handler(request):
                self.assertEqual(json.loads(path.read_text())['speech']['status'],'submission_uncertain')
                calls.append(1)
                return httpx.Response(200,stream=BytesStream(),headers={'x-si-buyer-cost-micro':'123'})
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                result=media_smoke.paid_post(client,state,path,'speech','test-key','/v1/audio/speech',json={})
                self.assertEqual(result,(200,b'example'))
                self.assertEqual(state['speech']['actual_usd'],'0.000123')
                with self.assertRaises(ValueError):
                    media_smoke.paid_post(client,state,path,'speech','test-key','/v1/audio/speech',json={})
            self.assertEqual(len(calls),1)

    def test_timeout_is_uncertain_and_blocks_another_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json';state={};calls=[]
            def handler(request):
                calls.append(1)
                raise httpx.ReadTimeout('not displayed')
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                self.assertIsNone(media_smoke.paid_post(client,state,path,'song','test-key','/v1/music/generations',json={}))
                restored=json.loads(path.read_text())
                self.assertEqual(restored['song']['status'],'submission_uncertain')
                with self.assertRaises(ValueError):
                    media_smoke.paid_post(client,restored,path,'song','test-key','/v1/music/generations',json={})
            self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
