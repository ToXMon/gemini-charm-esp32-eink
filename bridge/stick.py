"""StickS3 HTTP adapter: bounded audio in; transcription, image or audio out."""
import asyncio
import base64
import hmac
import io
import json
import logging
import os
import re
import secrets
import time
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, ImageOps
from bridge.app import BASE, KEY, TOKEN, wav_bytes

router = APIRouter()
# In-memory, bounded job state; do not deploy multiple workers without shared storage.
JOBS = {}
JOB_TTL = 600
MARKET_CACHE = {"until": 0.0, "markets": None}
MARKETS = os.getenv('SURPLUS_MARKETS_URL', 'https://api.surplusintelligence.ai/api/markets')
MODELS = {
    'chat': os.getenv('SURPLUS_CHAT_MODELS', os.getenv('SURPLUS_CHAT_MODEL', '')).split(','),
    'stt': os.getenv('SURPLUS_STT_MODELS', 'venice-whisper-1').split(','),
    'tts': os.getenv('SURPLUS_TTS_MODELS', 'venice-tts-1').split(','),
    'image': os.getenv('SURPLUS_IMAGE_MODELS', 'venice-z-image-turbo').split(','),
    'music': os.getenv('SURPLUS_MUSIC_MODELS', 'venice-ace-step-15').split(','),
}
VOICE = os.getenv('SURPLUS_VOICE', 'alloy')
PROMPT = ('You route a caregiver\'s request to image, song, or speech. Return only JSON '
          'with action and prompt. For an image or song, prompt describes the requested asset. '
          'Otherwise action is speech and prompt is a short helpful spoken response. '
          'For toddler content be gentle, original, reassuring, simple and age-appropriate.')
MAX_AUDIO = 16000 * 2 * 30


def authorize(request):
    expected = 'Bearer ' + TOKEN
    if len(TOKEN) < 20 or not KEY or not hmac.compare_digest(request.headers.get('authorization',''), expected):
        raise HTTPException(401, 'Unauthorized')


async def pick_model(client, kind):
    """Choose from user-approved model IDs; compare only compatible price units."""
    allowed = [m.strip() for m in MODELS[kind] if m.strip()]
    if not allowed: raise ValueError('No configured model for '+kind)
    if len(allowed) == 1: return allowed[0]
    if MARKET_CACHE['markets'] is None or time.monotonic() >= MARKET_CACHE['until']:
        r = await client.get(MARKETS); r.raise_for_status()
        MARKET_CACHE['markets'] = {m['model']: m for m in r.json()['markets']}
        MARKET_CACHE['until'] = time.monotonic() + 30
    markets = MARKET_CACHE['markets']
    choices = []
    for model in allowed:
        item = markets.get(model, {})
        if not item.get('num_sellers'): continue
        if kind == 'chat':
            inp, out = item.get('best_input_per_1m'), item.get('best_output_per_1m')
            if inp is None or out is None or inp <= 0 or out <= 0: continue
            price, unit = inp * 1000 + out * 250, 'token mix'
        else:
            price, unit = item.get('best_media_unit_price'), item.get('media_unit')
            if price is None or price <= 0 or not unit: continue
        choices.append((price, unit, model))
    if not choices: raise ValueError('No live priced offers for '+kind)
    if len({v[1] for v in choices}) != 1: raise ValueError('Cannot compare unlike billing units for '+kind)
    return min(choices)[2]


def jpeg_for_screen(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 25_000_000: raise ValueError('Image too large')
        result = ImageOps.fit(image.convert('RGB'), (135,240), method=Image.Resampling.LANCZOS)
        buf = io.BytesIO(); result.save(buf, format='JPEG', quality=85)
        return buf.getvalue()


async def pcm_for_device(data):
    proc = await asyncio.create_subprocess_exec('ffmpeg','-v','error','-i','pipe:0','-t','55','-f','s16le','-ac','1','-ar','16000','pipe:1',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try: output, _ = await asyncio.wait_for(proc.communicate(data), timeout=45)
    except asyncio.TimeoutError:
        proc.kill(); await proc.wait(); raise
    if proc.returncode or not output or len(output)>2*1024*1024: raise ValueError('Audio decode failed')
    return output


async def transcribe(client, pcm):
    model = await pick_model(client, 'stt')
    r = await client.post(BASE+'/audio/transcriptions', headers={'Authorization':'Bearer '+KEY},data={'model':model},files={'file':('speech.wav',wav_bytes(pcm),'audio/wav')})
    r.raise_for_status(); return r.json().get('text','').strip()[:4000]


async def create(client, prompt):
    headers={'Authorization':'Bearer '+KEY}
    model=await pick_model(client,'chat')
    r=await client.post(BASE+'/chat/completions',headers=headers,json={'model':model,'messages':[{'role':'system','content':PROMPT},{'role':'user','content':prompt}],'max_tokens':350})
    r.raise_for_status(); text=r.json()['choices'][0]['message']['content'].strip()
    # Some providers wrap JSON in code fences. Refuse ambiguous output rather than spend on a wrong action.
    if text.startswith('```'): text=re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.I)
    plan=json.loads(text); action=plan.get('action'); brief=plan.get('prompt')
    if action not in ('speech','image','song') or not isinstance(brief,str) or not brief.strip() or len(brief)>4000:
        raise ValueError('Invalid routing result')
    if action=='speech':
        model=await pick_model(client,'tts')
        r=await client.post(BASE+'/audio/speech',headers=headers,json={'model':model,'input':brief,'voice':VOICE,'response_format':'wav'})
        r.raise_for_status(); return action,await pcm_for_device(r.content)
    if action=='image':
        model=await pick_model(client,'image')
        r=await client.post(BASE+'/images/generations',headers=headers,json={'model':model,'prompt':brief+', colorful, simple centered portrait composition, age-appropriate','n':1,'response_format':'b64_json'})
        r.raise_for_status(); item=r.json()['data'][0]
        return action,jpeg_for_screen(base64.b64decode(item['b64_json'],validate=True))
    model=await pick_model(client,'music')
    r=await client.post(BASE+'/music/generations',headers=headers,json={'model':model,'prompt':brief[:2000],'duration_seconds':15})
    r.raise_for_status(); job=r.json(); job_id=job['id']
    if not re.fullmatch(r'[A-Za-z0-9-]{1,128}',job_id): raise ValueError('Invalid job ID')
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        await asyncio.sleep(3)
        r=await client.get(BASE+'/music/generations/'+job_id,headers=headers);r.raise_for_status();job=r.json()
        if job['status'] in ('succeeded','completed'): break
        if job['status'] in ('failed','expired','cancelled','canceled'): raise ValueError('Music job failed')
    else: raise TimeoutError('Music job timed out')
    r=await client.get(BASE+'/media/artifacts/'+job_id+'/0',headers=headers)
    if r.is_redirect:
        url=r.headers['location']; parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password: raise ValueError('Invalid artifact URL')
        # No credential headers are forwarded to the signed artifact location.
        r=await client.get(url)
    r.raise_for_status(); return action,await pcm_for_device(r.content)


@router.post('/stick/transcribe')
async def endpoint_transcribe(request: Request):
    authorize(request)
    declared=request.headers.get('content-length')
    if not declared or not declared.isdigit() or int(declared)>MAX_AUDIO: raise HTTPException(413,'Audio too large')
    pcm=await request.body()
    if not pcm or len(pcm)>MAX_AUDIO or len(pcm)%2: raise HTTPException(400,'Invalid PCM')
    try:
        async with httpx.AsyncClient(timeout=110,follow_redirects=False) as client: text=await transcribe(client,pcm)
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        logging.warning('Transcription failed');raise HTTPException(502,'Transcription failed')
    return {'text':text}


async def _run_job(job_id, prompt):
    job=JOBS[job_id]
    try:
        async with httpx.AsyncClient(timeout=110,follow_redirects=False) as client:
            action,content=await create(client,prompt)
        job.update(status='done',action=action,content=content,finished=time.monotonic())
    except Exception:
        logging.warning('Generation failed')
        job.update(status='failed',finished=time.monotonic())


@router.post('/stick/create', status_code=202)
async def endpoint_create(request: Request):
    authorize(request)
    declared=request.headers.get('content-length')
    if not declared or not declared.isdigit() or int(declared)>12000: raise HTTPException(413,'Request too large')
    try:
        data=await request.json(); prompt=data['prompt']
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>4000: raise ValueError('Invalid prompt')
    except (ValueError,KeyError,TypeError): raise HTTPException(400,'Invalid prompt')
    now=time.monotonic()
    for key,job in list(JOBS.items()):
        if job.get('finished') and now-job['finished']>JOB_TTL: del JOBS[key]
    if sum(job['status']=='running' for job in JOBS.values())>=1 or len(JOBS)>=10:
        raise HTTPException(429,'Bridge busy')
    job_id=secrets.token_urlsafe(18)
    JOBS[job_id]={'status':'running'}
    asyncio.create_task(_run_job(job_id,prompt))
    return {'job_id':job_id}


@router.get('/stick/jobs/{job_id}')
async def endpoint_job(job_id: str, request: Request):
    authorize(request)
    job=JOBS.get(job_id)
    if not job: raise HTTPException(404,'Job not found')
    if job['status']=='running': return Response(status_code=202)
    if job['status']=='failed': raise HTTPException(502,'Generation failed')
    return Response(job['content'],media_type='image/jpeg' if job['action']=='image' else 'application/octet-stream',headers={'X-Action':job['action']})
