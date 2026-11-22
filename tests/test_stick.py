import asyncio
import base64
import io
import json
import unittest
import wave
from unittest.mock import patch
import httpx
from PIL import Image
from fastapi.testclient import TestClient
from bridge import app, stick

class StickTests(unittest.TestCase):
    def test_price_selection_rejects_unlike_units(self):
        async def run():
            def respond(req):
                return httpx.Response(200,json={'markets':[{'model':'a','num_sellers':1,'best_media_unit_price':2,'media_unit':'image'},{'model':'b','num_sellers':1,'best_media_unit_price':1,'media_unit':'image'}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
                with patch.dict(stick.MODELS, {'image':['a','b']}): self.assertEqual(await stick.pick_model(c,'image'),'b')
        asyncio.run(run())

    def test_transcription_request(self):
        async def run():
            def respond(req):
                self.assertIn(b'speech.wav',req.content)
                return httpx.Response(200,json={'text':'draw a duck'})
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
                with patch.object(stick,'KEY','fake'): self.assertEqual(await stick.transcribe(c,bytes(3200)),'draw a duck')
        asyncio.run(run())

    def test_image_generation(self):
        img=io.BytesIO();Image.new('RGB',(40,40),'blue').save(img,format='PNG')
        async def run():
            def respond(req):
                if req.url.path.endswith('completions'):
                    return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'action':'image','prompt':'blue duck'})}}]})
                return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(img.getvalue()).decode()}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
                with patch.object(stick,'KEY','fake'),patch.dict(stick.MODELS,{'chat':['chat'],'image':['image']}):
                    action,data=await stick.create(c,'draw a duck')
            self.assertEqual(action,'image');self.assertEqual(Image.open(io.BytesIO(data)).size,(135,240))
        asyncio.run(run())

    def test_speech_generation(self):
        buf=io.BytesIO()
        with wave.open(buf,'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(bytes(3200))
        async def run():
            def respond(req):
                if req.url.path.endswith('completions'):
                    return httpx.Response(200,json={'choices':[{'message':{'content':'{"action":"speech","prompt":"hello"}'}}]})
                return httpx.Response(200,content=buf.getvalue())
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
                with patch.object(stick,'KEY','fake'),patch.dict(stick.MODELS,{'chat':['chat'],'tts':['speech']}): action,data=await stick.create(c,'hello')
            self.assertEqual(action,'speech');self.assertEqual(len(data),3200)
        asyncio.run(run())

    def test_music_succeeded_and_artifact_download(self):
        async def run():
            paths=[]
            def respond(req):
                paths.append(req.url.path)
                if req.url.path.endswith('completions'):
                    return httpx.Response(200,json={'choices':[{'message':{'content':'{"action":"song","prompt":"gentle song"}'}}]})
                if req.url.path.endswith('/music/generations'):
                    return httpx.Response(202,json={'id':'job-1'})
                if req.url.path.endswith('/music/generations/job-1'):
                    return httpx.Response(200,json={'status':'succeeded'})
                return httpx.Response(200,content=b'audio')
            async def fast_sleep(seconds): pass
            async def decode(data): self.assertEqual(data,b'audio'); return b'\x00\x00'
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
                with patch.object(stick,'KEY','fake'),patch.dict(stick.MODELS,{'chat':['chat'],'music':['song']}),patch.object(stick.asyncio,'sleep',fast_sleep),patch.object(stick,'pcm_for_device',decode):
                    action,data=await stick.create(c,'sing a song')
            self.assertEqual((action,data),('song',b'\x00\x00'))
            self.assertTrue(paths[-1].endswith('/media/artifacts/job-1/0'))
        asyncio.run(run())

    def test_job_submit_poll_and_busy(self):
        async def run():
            event=asyncio.Event()
            async def generate(client,prompt):
                await event.wait()
                return 'image',b'jpeg'
            with patch.object(stick,'TOKEN','x'*24), patch.object(stick,'KEY','fake'), patch.object(stick,'create',generate):
                stick.JOBS.clear()
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://test') as client:
                    headers={'Authorization':'Bearer '+'x'*24}
                    submit=await client.post('/stick/create',headers=headers,json={'prompt':'duck'})
                    self.assertEqual(submit.status_code,202)
                    job=submit.json()['job_id']
                    self.assertEqual((await client.post('/stick/create',headers=headers,json={'prompt':'more'})).status_code,429)
                    self.assertEqual((await client.get('/stick/jobs/'+job,headers=headers)).status_code,202)
                    event.set()
                    for _ in range(10):
                        await asyncio.sleep(0.01)
                        result=await client.get('/stick/jobs/'+job,headers=headers)
                        if result.status_code==200: break
                    self.assertEqual(result.content,b'jpeg')
                    self.assertEqual(result.headers['x-action'],'image')
                stick.JOBS.clear()
        asyncio.run(run())

    def test_auth_and_length_gate(self):
        with patch.object(stick,'TOKEN','x'*24),patch.object(stick,'KEY','fake'):
            with TestClient(app.app) as client:
                self.assertEqual(client.post('/stick/transcribe',content=b'aa').status_code,401)
                self.assertEqual(client.post('/stick/transcribe',headers={'Authorization':'Bearer '+'x'*24},content=b'a').status_code,400)

if __name__=='__main__': unittest.main()
