"""Generate caregiver-reviewed story, speech, image or music assets via Surplus."""
import argparse
import base64
import json
import os
from pathlib import Path
import time
import httpx

BASE = os.getenv('SURPLUS_BASE_URL', 'https://api.surplusintelligence.ai/v1').rstrip('/')
KEY = os.environ.get('SURPLUS_API_KEY', '')
SYSTEM = ('Create original, gentle, age-appropriate content for a 16-month-old. '
          'Use simple language, repetition, warmth and a reassuring ending. '
          'Avoid frightening situations and unsafe activities. Output only the requested content.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind', choices=['story', 'speech', 'image', 'music'])
    p.add_argument('--model', required=True, help='Live Surplus model ID for this modality')
    p.add_argument('--prompt', help='Generation brief (story, image, music)')
    p.add_argument('--text-file', help='Reviewed UTF-8 text to narrate (speech)')
    p.add_argument('--voice', default='alloy', help='Speech voice supported by the selected model')
    p.add_argument('--output', required=True, help='New output file (never overwrites)')
    p.add_argument('--duration', type=int, default=15, help='Music duration in seconds')
    a = p.parse_args()
    if not KEY: p.error('Set SURPLUS_API_KEY in your environment')
    if a.kind == 'speech':
        if not a.text_file or a.prompt: p.error('Speech requires --text-file and no --prompt')
        speech_text = Path(a.text_file).read_text(encoding='utf-8').strip()
        if not speech_text or len(speech_text) > 4000: p.error('Text must contain 1–4000 characters')
    elif not a.prompt or a.text_file:
        p.error('This kind requires --prompt and no --text-file')
    dest = Path(a.output)
    if dest.exists(): p.error('Output already exists')
    headers = {'Authorization': 'Bearer '+KEY}
    with httpx.Client(timeout=120, follow_redirects=False) as c:
        if a.kind == 'story':
            r = c.post(BASE+'/chat/completions', headers=headers, json={'model':a.model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':a.prompt}],'max_tokens':500})
            r.raise_for_status(); data = r.json()['choices'][0]['message']['content'].encode()
        elif a.kind == 'speech':
            r = c.post(BASE+'/audio/speech', headers=headers, json={'model':a.model,'input':speech_text,'voice':a.voice,'response_format':'wav'})
            r.raise_for_status(); data = r.content
            if not data: raise ValueError('Provider returned empty audio')
        elif a.kind == 'image':
            r = c.post(BASE+'/images/generations', headers=headers, json={'model':a.model,'prompt':a.prompt+', gentle toddler-friendly illustration, simple shapes, no text','n':1,'response_format':'b64_json'})
            r.raise_for_status(); item = r.json()['data'][0]
            if 'b64_json' not in item: raise ValueError('Provider did not return b64_json; choose a compatible model')
            data = base64.b64decode(item['b64_json'], validate=True)
        else:
            if not 1 <= a.duration <= 60: p.error('Duration must be 1–60 seconds')
            r = c.post(BASE+'/music/generations', headers=headers, json={'model':a.model,'prompt':a.prompt,'duration_seconds':a.duration,'force_instrumental':True})
            r.raise_for_status(); job = r.json(); job_id = job['id']
            # Construct paths ourselves; never forward the API key to a returned URL.
            if not all(ch.isalnum() or ch == '-' for ch in job_id): raise ValueError('Invalid job ID')
            deadline = time.monotonic()+900
            while time.monotonic() < deadline:
                time.sleep(5)
                r = c.get(BASE+'/music/generations/'+job_id, headers=headers); r.raise_for_status(); job = r.json()
                if job['status'] == 'completed': break
                if job['status'] in ('failed','expired','canceled','cancelled'): raise RuntimeError('Music generation failed: '+job['status'])
            else: raise TimeoutError('Music job timed out')
            # Artifact endpoint redirects to a signed URL; follow without sending credentials cross-origin.
            r = c.get(BASE+'/media/artifacts/'+job_id+'/0', headers=headers)
            if r.is_redirect:
                url = r.headers['location']
                if not url.startswith('https://'): raise ValueError('Unsafe artifact redirect')
                r = c.get(url)
            r.raise_for_status(); data = r.content
    with dest.open('xb') as f: f.write(data)
    print('Saved', dest, '— review before sharing with your child.')


if __name__ == '__main__': main()
