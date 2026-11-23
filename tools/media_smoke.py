"""Single-attempt, synthetic Surplus media checks. Never retry a paid POST."""
import argparse
import base64
from decimal import Decimal, InvalidOperation
import fcntl
import io
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlsplit
import wave

import httpx
from PIL import Image
from private_config import ConfigError, load_keys

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://api.surplusintelligence.ai'
TEXT = 'Hello from my little device.'
LIMIT = 8 * 1024 * 1024


def save_json(path, value):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.state-', delete=False) as f:
        name = f.name
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(name, path)


def bounded_response(client, method, url, **kwargs):
    started = time.monotonic()
    with client.stream(method, url, **kwargs) as response:
        status = response.status_code
        headers = dict(response.headers)
        body = bytearray()
        if status == 200 or status == 202 or 400 <= status < 600:
            if headers.get('content-encoding', 'identity').lower() != 'identity':
                raise ValueError('compressed response')
            length=headers.get('content-length')
            if length and (not length.isdigit() or int(length)>LIMIT):
                raise ValueError('response too large')
            for chunk in response.iter_raw():
                if len(body) + len(chunk) > LIMIT:
                    raise ValueError('response too large')
                body.extend(chunk)
        return status, headers, bytes(body), round((time.monotonic()-started)*1000)


def paid_post(client, state, state_path, kind, key, path, **kwargs):
    if kind in state:
        raise ValueError('already attempted')
    state[kind] = {'status': 'submission_uncertain'}
    save_json(state_path, state)
    try:
        status, headers, body, latency = bounded_response(
            client, 'POST', BASE+path, headers={'Authorization': 'Bearer '+key, 'Accept-Encoding': 'identity'}, **kwargs)
    except (httpx.HTTPError, ValueError):
        return None
    state[kind].update(status='received' if status in (200,202) else 'http_error', http_status=status, latency_ms=latency)
    if status >= 400:
        try:
            error=json.loads(body)
            error=error.get('error',error)
            code=error.get('code') if isinstance(error,dict) else None
            if code in {'invalid_request','model_not_found','no_sellers_for_model',
                        'insufficient_credit','insufficient_balance','no_healthy_sellers'}:
                state[kind]['error_code']=code
        except (ValueError,TypeError,AttributeError):pass
    # On these endpoints only accept a numeric provider cost header as actual.
    amount = headers.get('x-si-buyer-cost-micro')
    if amount and amount.isdigit() and status in (200, 202):
        state[kind]['actual_usd'] = str(Decimal(amount) / Decimal(1000000))
    save_json(state_path, state)
    return status, body


def write_private(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.artifact-', delete=False) as f:
        name=f.name
        f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(name,path)


def audio_info(body):
    with wave.open(io.BytesIO(body), 'rb') as wav:
        info={'channels': wav.getnchannels(), 'sample_rate': wav.getframerate(),
              'bits': wav.getsampwidth()*8, 'frames': wav.getnframes(), 'compression': wav.getcomptype()}
        if not info['frames'] or len(wav.readframes(info['frames'])) != info['frames']*info['channels']*wav.getsampwidth():
            raise wave.Error('truncated audio')
        return info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind', choices=['speech', 'transcription', 'image', 'song', 'song60', 'song_default'])
    p.add_argument('--run-paid', action='store_true')
    p.add_argument('--env', default=str(ROOT/'.env'))
    args = p.parse_args()
    if not args.run_paid:
        raise SystemExit('Pass --run-paid to submit one synthetic request.')
    try:
        key=load_keys(args.env)['SURPLUS_API_KEY']
    except ConfigError as e:
        raise SystemExit(str(e)) from None
    folder=ROOT/'evals/private/surplus-host-smoke'
    folder.mkdir(parents=True,mode=0o700,exist_ok=True);os.chmod(folder,0o700)
    state_path=folder/'state.json'
    lock_fd=os.open(folder/'lock',os.O_CREAT|os.O_RDWR,0o600)
    try:
        fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd);raise SystemExit('Another media smoke test is running.') from None
    try:
        state=json.loads(state_path.read_text()) if state_path.exists() else {}
        with httpx.Client(timeout=60,follow_redirects=False,trust_env=False) as client:
            kind=args.kind
            if kind=='speech':
                result=paid_post(client,state,state_path,kind,key,'/v1/audio/speech',
                                 json={'model':'venice-kokoro-tts','input':TEXT,'voice':'af_heart','response_format':'wav'})
                if result and result[0]==200:
                    try:
                        info=audio_info(result[1]);write_private(folder/'speech.wav',result[1])
                        state[kind].update(status='succeeded',audio=info)
                    except (wave.Error,EOFError):state[kind]['status']='unsupported_format'
            elif kind=='transcription':
                path=folder/'speech.wav'
                if not path.exists():raise SystemExit('Run a successful speech test first.')
                with path.open('rb') as f:
                    result=paid_post(client,state,state_path,kind,key,'/v1/audio/transcriptions',
                                     data={'model':'venice-whisper-large-v3'},files={'file':('speech.wav',f,'audio/wav')})
                if result and result[0]==200:
                    try:
                        text=json.loads(result[1]).get('text','')
                        if not isinstance(text,str) or len(text)>4000:raise ValueError('invalid transcript')
                        state[kind].update(status='succeeded',matches_reference=text.strip().lower().rstrip('.')==TEXT.lower().rstrip('.'))
                        write_private(folder/'transcript.txt',text.encode())
                    except (ValueError,TypeError,AttributeError):state[kind]['status']='invalid_response'
            elif kind=='image':
                result=paid_post(client,state,state_path,kind,key,'/v1/images/generations',
                                 json={'model':'venice-z-image-turbo','prompt':'A small blue sailboat, simple colorful illustration.',
                                       'n':1,'response_format':'b64_json'})
                if result and result[0]==200:
                    try:
                        encoded=json.loads(result[1])['data'][0]['b64_json']
                        data=base64.b64decode(encoded,validate=True)
                        if not data or len(data)>LIMIT:raise ValueError('invalid image size')
                        with Image.open(io.BytesIO(data)) as image:
                            if image.width*image.height>4000000:raise ValueError('large dimensions')
                            info={'format':image.format,'width':image.width,'height':image.height};image.verify()
                        write_private(folder/'image.bin',data);state[kind].update(status='succeeded',image=info)
                    except (ValueError,KeyError,IndexError,TypeError,OSError):state[kind]['status']='invalid_response'
            else:
                if kind not in state:
                    duration=60 if kind=='song60' else 15
                    request={'model':'venice-ace-step-15',
                             'prompt':'A short cheerful instrumental tune with a gentle piano.'}
                    if kind!='song_default':request.update(duration_seconds=duration,force_instrumental=True)
                    result=paid_post(client,state,state_path,kind,key,'/v1/music/generations',
                                     json=request)
                    if result and result[0] in (200,202):
                        try:
                            job=json.loads(result[1]);job_id=job['id']
                            if not isinstance(job_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',job_id):raise ValueError('invalid id')
                            state[kind].update(status='queued',job_id=job_id);save_json(state_path,state)
                        except (ValueError,TypeError,KeyError):state[kind]['status']='submission_uncertain'
                job_id=state.get(kind,{}).get('job_id')
                if job_id and state[kind].get('status') in ('queued','succeeded'):
                    deadline=time.monotonic()+180
                    while time.monotonic()<deadline:
                        time.sleep(4)
                        try:
                            code,_,body,_=bounded_response(client,'GET',BASE+'/v1/music/generations/'+job_id,
                                                           headers={'Authorization':'Bearer '+key,'Accept-Encoding':'identity'})
                            if code!=200:break
                            job=json.loads(body);status=job.get('status')
                            if status in ('failed','expired','canceled','cancelled'):
                                state[kind]['status']=status;break
                            if status in ('succeeded','completed'):
                                state[kind]['status']='succeeded'
                                usage=job.get('usage') or {}
                                try:
                                    settlement=usage.get('settlement_status')
                                    micro=Decimal(str(usage['buyer_cost_usdc']))
                                    if settlement in ('captured','confirmed') and micro.is_finite() and micro>=0:
                                        amount=str(micro/Decimal(1000000))
                                        state[kind]['provider_reported_usd']=amount
                                        state[kind]['settlement_status']=settlement
                                        if settlement=='confirmed':state[kind]['actual_usd']=amount
                                except (InvalidOperation,KeyError,TypeError):pass
                                # Artifact retrieval is a separate safe GET; never forward auth to redirects.
                                if not state[kind].get('artifact_bytes'):
                                    code,headers,body,_=bounded_response(client,'GET',BASE+'/v1/media/artifacts/'+job_id+'/0',
                                                                        headers={'Authorization':'Bearer '+key,'Accept-Encoding':'identity'})
                                    if code in (301,302,303,307,308):
                                        target=headers.get('location','');parsed=urlsplit(target)
                                        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:raise ValueError('invalid redirect')
                                        code,headers,body,_=bounded_response(client,'GET',target,headers={'Accept-Encoding':'identity'})
                                    if code==200 and 0<len(body)<=LIMIT:
                                        write_private(folder/'song.bin',body);state[kind]['artifact_bytes']=len(body)
                                break
                        except (httpx.HTTPError,ValueError,TypeError,KeyError):break
                    save_json(state_path,state)
            save_json(state_path,state)
            print(kind+':', state.get(kind,{}).get('status','not started'),
                  'HTTP',state.get(kind,{}).get('http_status','unknown'),
                  'actual USD',state.get(kind,{}).get('actual_usd','unknown'),
                  'error code',state.get(kind,{}).get('error_code','not reported'))
    except ValueError as e:
        if str(e)=='already attempted':raise SystemExit('This test was already attempted; inspect its private state before any new submission.') from None
        raise SystemExit('Media test failed; inspect its private state before any retry.') from None
    finally:
        os.close(lock_fd)


if __name__=='__main__':main()
