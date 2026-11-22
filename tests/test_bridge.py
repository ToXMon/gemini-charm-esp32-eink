import asyncio
import io
import struct
import unittest
import wave
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from bridge import app


class BridgeTests(unittest.TestCase):
    def test_detector_and_wave(self):
        detector = app.TurnDetector()
        voice = struct.pack('<512h', *([1000] * 512))
        quiet = bytes(1024)
        self.assertIsNone(detector.feed(voice))
        turn = None
        for _ in range(32):
            turn = detector.feed(quiet) or turn
        self.assertIsNotNone(turn)
        with wave.open(io.BytesIO(app.wav_bytes(turn))) as f:
            self.assertEqual((f.getnchannels(), f.getsampwidth(), f.getframerate()), (1, 2, 16000))
            self.assertEqual(f.readframes(f.getnframes()), turn)

    def test_websocket_auth_and_setup(self):
        with patch.object(app, 'TOKEN', 'a'*24), patch.object(app, 'KEY', 'key'), patch.object(app, 'CHAT', 'model'):
            with TestClient(app.app) as client:
                with self.assertRaises(Exception):
                    with client.websocket_connect('/device?key=wrong'):
                        pass
                with client.websocket_connect('/device?key='+'a'*24) as ws:
                    ws.send_json({'setup': {}})
                    self.assertEqual(ws.receive_json(), {'setupComplete': {}})

    def test_full_turn_with_mock_surplus(self):
        calls = []
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000)
            f.writeframes(bytes(2400))
        def handler(request):
            calls.append(request.url.path)
            if request.url.path.endswith('/transcriptions'):
                return httpx.Response(200, json={'text':'Tell me a story'})
            if request.url.path.endswith('/completions'):
                return httpx.Response(200, json={'choices':[{'message':{'content':'Hello duck.'}}]})
            return httpx.Response(200, content=audio.getvalue(), headers={'content-type':'audio/wav'})
        class Socket:
            def __init__(self): self.messages=[]
            async def send_json(self, value): self.messages.append(value)
        async def run():
            ws=Socket(); history=[]
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await app.respond(ws, bytes(3200), history, client)
            self.assertEqual(len(history), 2)
            self.assertTrue(ws.messages[0]['serverContent']['modelTurn']['parts'][0]['inlineData']['data'])
            self.assertEqual(ws.messages[-1], {'serverContent': {'turnComplete': True}})
        asyncio.run(run())
        self.assertEqual(len(calls), 3)

if __name__ == '__main__': unittest.main()
