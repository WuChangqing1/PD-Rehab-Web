#!/usr/bin/env python3
"""Process a locally obtained, rights-cleared ballet source video.

This tool NEVER downloads media, claims licensing approval, or labels a clip as
medically reviewed. A person must supply an audited source file and a visually
reviewed full-movement in/out window.

Example (timestamps are fictional syntax examples, DO NOT copy without review):
 python process_ballet_clips.py --input licensed_source.webm \
   --start 2.5 --end 9.2 --poster-at 1.4 \
   --exercise BALLET_TENDU --mode STANDING_SUPPORTED \
   --source-id SRC-TENDU-01 --output-dir ./processed
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

KEYS = {'BALLET_PORT_DE_BRAS','BALLET_FIRST_POSITION','BALLET_TENDU','BALLET_DEMI_PLIE','BALLET_WEIGHT_SHIFT'}
MODES = {'SEATED', 'STANDING_SUPPORTED'}


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode:
        raise RuntimeError(f"Command failed: {' '.join(map(str, cmd))}\n{p.stderr[-5000:]}")
    return p.stdout


def sha256(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def probe(p):
    return json.loads(run(['ffprobe','-v','error','-show_entries',
        'format=duration,size:stream=index,codec_name,codec_type,width,height,avg_frame_rate',
        '-of','json',str(p)]))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True, help='Local, independently licensed original source file')
    ap.add_argument('--start', type=float, required=True, help='Start timestamp (seconds), chosen after visual review')
    ap.add_argument('--end', type=float, required=True, help='End timestamp (seconds), chosen after visual review')
    ap.add_argument('--poster-at', type=float, required=True, help='Timestamp within the trimmed clip')
    ap.add_argument('--exercise', choices=sorted(KEYS), required=True)
    ap.add_argument('--mode', choices=sorted(MODES), required=True)
    ap.add_argument('--source-id', required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--version', default='v1')
    args=ap.parse_args()
    if not args.input.is_file():
        ap.error(f'Source file does not exist: {args.input}')
    if not (0 <= args.start < args.end):
        ap.error('Must have 0 <= start < end')
    if not (0 <= args.poster_at <= args.end-args.start):
        ap.error('--poster-at must be inside the trimmed clip')
    if args.exercise=='BALLET_DEMI_PLIE' and args.mode=='SEATED':
        ap.error('Current training catalogue does not support SEATED Demi-Plié')
    orig=probe(args.input)
    duration=float(orig.get('format',{}).get('duration','0') or '0')
    if duration and args.end>duration+0.1:
        ap.error(f'end timestamp {args.end}s exceeds source duration {duration}s')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    name=f'ballet_{args.exercise.lower()}_{args.mode.lower()}_{args.version}'
    video=args.output_dir/(name+'.mp4')
    poster=args.output_dir/(name+'_poster.jpg')
    # Encode with broad mobile compatibility and no source audio; high fidelity
    # source review is still needed because trimming does not make content safe.
    run(['ffmpeg','-hide_banner','-loglevel','error','-y',
        '-ss',str(args.start),'-i',str(args.input),'-t',str(args.end-args.start),
        '-an','-vf','fps=25,scale=1280:-2:flags=lanczos,format=yuv420p',
        '-c:v','libx264','-preset','medium','-crf','24','-movflags','+faststart',str(video)])
    run(['ffmpeg','-hide_banner','-loglevel','error','-y',
        '-ss',str(args.poster_at),'-i',str(video),'-frames:v','1',
        '-vf','scale=960:-2',str(poster)])
    processed=probe(video)
    meta={
        'status':'TRANSCODED_AWAITING_HUMAN_APPROVAL',
        'source_id':args.source_id,
        'exercise_key':args.exercise,
        'execution_mode':args.mode,
        'source_path':str(args.input.resolve()),
        'source_sha256':sha256(args.input),
        'source_probe':orig,
        'trim_start_sec':args.start,
        'trim_end_sec':args.end,
        'poster_at_sec':args.poster_at,
        'video_path':str(video.resolve()),
        'poster_path':str(poster.resolve()),
        'sha256_processed':sha256(video),
        'processed_probe':processed,
        'license_verified':False,
        'movement_reviewed':False,
        'reviewer':None,
        'prepared_at_utc':datetime.now(timezone.utc).isoformat(),
        'notice':'Do not publish until permissions and movement suitability are verified.'
    }
    meta_path=args.output_dir/(name+'_processing.json')
    meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n', encoding='utf8')
    print(json.dumps({'video':str(video),'poster':str(poster),'metadata':str(meta_path),'status':meta['status']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
