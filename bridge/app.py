"""Half-duplex adapter for the original device's audio envelope."""
import asyncio
import base64
import hmac
import io
import json
import logging
import os
import struct
import wave
from collections import deque

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()
BASE = os.getenv('SURPLUS_BASE_URL', 'https://api.surplusintelligence.ai/v1').rstrip('/')
TOKEN = os.getenv('BRIDGE_TOKEN', '')
KEY = os.getenv('SURPLUS_API_KEY', '')
STT = os.getenv('SURPLUS_STT_MODEL', 'venice-whisper-1')
CHAT = os.getenv('SURPLUS_CHAT_MODEL', '')
TTS = os.getenv('SURPLUS_TTS_MODEL', 'venice-tts-1')
VOICE = os.getenv('SURPLUS_VOICE', 'alloy')
THRESHOLD = int(os.getenv('VAD_THRESHOLD', '450'))
SYSTEM = os.getenv('SYSTEM_PROMPT', 'You are a warm, concise family voice assistant. Create gentle, age-appropriate, original stories and songs suitable for a 16-month-old. Use simple language, repetition, and a reassuring tone. Never claim to perform actions you cannot perform. A caregiver reviews generated content.')


def wav_bytes(pcm):
    data = io.BytesIO()
    with wave.open(data, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000); f.writeframes(pcm)
    return data.getvalue()


class TurnDetector:
    def __init__(self):
        self.prefix = deque(maxlen=10)
        self.frames = []
        self.silence = 0

    def feed(self, pcm):
        if not pcm or len(pcm) % 2:
            return None
        samples = struct.unpack('<%dh' % (len(pcm)//2), pcm)
        rms = (sum(x*x for x in samples)/len(samples))**0.5
        if not self.frames:
            self.prefix.append(pcm)
            if rms >= THRESHOLD:
                self.frames = list(self.prefix); self.prefix.clear()
            return None
        self.frames.append(pcm)
        self.silence = self.silence + len(samples) if rms < THRESHOLD else 0
        if self.silence >= 16000 or sum(map(len, self.frames)) >= 16000*2*20:
            result = b''.join(self.frames)
            self.frames = []; self.silence = 0; self.prefix.clear()
            return result
        return None


async def respond(ws, pcm, history, client):
    headers = {'Authorization': 'Bearer ' + KEY}
    r = await client.post(BASE+'/audio/transcriptions', headers=headers, data={'model': STT}, files={'file': ('turn.wav', wav_bytes(pcm), 'audio/wav')})
    r.raise_for_status(); transcript = r.json().get('text', '').strip()
    if not transcript:
        await ws.send_json({'serverContent': {'turnComplete': True}})
        return
    messages = [{'role':'system', 'content':SYSTEM}] + history[-8:] + [{'role':'user', 'content':transcript}]
    r = await client.post(BASE+'/chat/completions', headers=headers, json={'model':CHAT, 'messages':messages, 'max_tokens':250})
    r.raise_for_status(); answer = r.json()['choices'][0]['message']['content'].strip()
    if not answer:
        raise ValueError('empty answer')
    r = await client.post(BASE+'/audio/speech', headers=headers, json={'model':TTS, 'input':answer, 'voice':VOICE, 'response_format':'wav'})
    r.raise_for_status()
    # Decode whatever the upstream actually returned, and match firmware's 24 kHz PCM input.
    proc = await asyncio.create_subprocess_exec('ffmpeg', '-v', 'error', '-i', 'pipe:0', '-f', 's16le', '-ac', '1', '-ar', '24000', 'pipe:1', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        output, _ = await asyncio.wait_for(proc.communicate(r.content), timeout=30)
    except asyncio.TimeoutError:
        proc.kill(); await proc.wait(); raise
    if proc.returncode or not output or len(output) > 900000:
        raise ValueError('invalid or oversized speech audio')
    history.extend([{'role':'user','content':transcript}, {'role':'assistant','content':answer}]); del history[:-8]
    for pos in range(0, len(output), 12000):
        chunk = base64.b64encode(output[pos:pos+12000]).decode()
        await ws.send_json({'serverContent': {'modelTurn': {'parts': [{'inlineData': {'mimeType':'audio/pcm;rate=24000','data':chunk}}]}}})
    await ws.send_json({'serverContent': {'turnComplete':True}})


@app.websocket('/device')
async def device(ws: WebSocket):
    if len(TOKEN) < 20 or not KEY or not CHAT or not hmac.compare_digest(ws.query_params.get('key', ''), TOKEN):
        await ws.close(code=1008); return
    await ws.accept()
    detector = TurnDetector(); history = []
    try:
        setup = await asyncio.wait_for(ws.receive_json(), timeout=10)
        if 'setup' not in setup:
            await ws.close(code=1008); return
        await ws.send_json({'setupComplete': {}})
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
            while True:
                msg = await ws.receive_json()
                encoded = msg.get('realtimeInput', {}).get('audio', {}).get('data')
                if not isinstance(encoded, str) or len(encoded) > 4096:
                    continue
                try:
                    pcm = base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError):
                    continue
                turn = detector.feed(pcm)
                if turn:
                    try:
                        await ws.send_json({"bridgeBusy": True})
                        await respond(ws, turn, history, client)
                        # Discard frames sent before the device received bridgeBusy.
                        # The board suppresses new microphone frames during playback.
                        while True:
                            try:
                                await asyncio.wait_for(ws.receive_json(), timeout=0.05)
                            except asyncio.TimeoutError:
                                break
                        detector = TurnDetector()
                    except (httpx.HTTPError, ValueError, KeyError, IndexError, asyncio.TimeoutError):
                        logging.warning('Surplus turn failed; check configuration and provider availability')
                        await ws.send_json({'error': {'code': 502}})
                        return
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
