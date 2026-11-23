"""Check basic local image/WAV integrity; this does not assess content quality."""
import argparse
import json
from pathlib import Path
import sys
import wave
from PIL import Image, UnidentifiedImageError


def inspect(path, kind):
    path=Path(path)
    if not path.is_file() or path.stat().st_size==0: raise ValueError('asset missing or empty')
    if kind=='image':
        with Image.open(path) as image:
            if image.format not in {'JPEG','PNG'}: raise ValueError('expected JPEG or PNG')
            image.verify()
        with Image.open(path) as image:
            return {'kind':'image','format':image.format,'width':image.width,'height':image.height,'bytes':path.stat().st_size}
    with wave.open(str(path),'rb') as wav:
        if wav.getcomptype()!='NONE' or wav.getframerate()<=0 or wav.getnchannels() not in (1,2): raise ValueError('unsupported WAV')
        frames=wav.getnframes();size=frames*wav.getnchannels()*wav.getsampwidth()
        if frames<=0 or size>path.stat().st_size: raise ValueError('invalid or truncated WAV')
        remaining=frames
        while remaining:
            chunk=min(remaining,4096); data=wav.readframes(chunk)
            if len(data)!=chunk*wav.getnchannels()*wav.getsampwidth(): raise ValueError('truncated WAV')
            remaining-=chunk
        return {'kind':'audio','format':'WAV','channels':wav.getnchannels(),'sample_rate':wav.getframerate(),'duration_seconds':frames/wav.getframerate(),'bytes':path.stat().st_size}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kind',choices=['image','audio']);p.add_argument('path');p.add_argument('--max-seconds',type=float);p.add_argument('--width',type=int);p.add_argument('--height',type=int);a=p.parse_args()
    try:
        result=inspect(a.path,a.kind)
        if a.kind=='audio' and a.max_seconds is not None and result['duration_seconds']>a.max_seconds: raise ValueError('duration exceeds limit')
        if a.kind=='image' and ((a.width is not None and result['width']!=a.width) or (a.height is not None and result['height']!=a.height)): raise ValueError('dimensions do not match')
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,EOFError,wave.Error,UnidentifiedImageError) as e:
        print('Asset check failed:',e,file=sys.stderr);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
