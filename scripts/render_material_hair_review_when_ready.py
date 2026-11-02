"""Wait for a real saved 12-second state, then render the normal 11s review.

Runs no simulation and starts only one Blender GPU process at a time.
"""
import argparse,json,subprocess,time
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--delivery',required=True)
p.add_argument('--blender',required=True)
a=p.parse_args()
out=Path(a.delivery)
root=Path(__file__).resolve().parents[1]
while True:
    pub=json.loads((out/'cache_publication.json').read_text('utf8'))
    run=Path(pub['run'])
    status=json.loads((run/'status.json').read_text('utf8'))
    if status['stage']=='FAILED':
        raise RuntimeError(status)
    if pub['published_through_frame']>=360 and status['stage'] in ['TEST_PREFIX_RECORDED','COMPLETE'] and not (run/'worker.lock.json').exists():
        break
    time.sleep(5)
blend=out/'完整角色_整头连续物理_15秒.blend'
base=[a.blender,'-b','--threads','4','--python',str(root/'scripts/render_full_hair_showcase.py'),'--','--source',str(blend)]
with (out/'review_keyframes_render.log').open('w',encoding='utf8') as log:
    subprocess.run(base+['--out',str(out/'keyframes_11s'),'--frames','326,331,336'],stdout=log,stderr=subprocess.STDOUT,check=True)
with (out/'review_continuous_render.log').open('w',encoding='utf8') as log:
    subprocess.run(base+['--out',str(out/'preview11s'),'--first','301','--last','360','--percentage','50','--samples','16'],stdout=log,stderr=subprocess.STDOUT,check=True)
(out/'review_ready.json').write_text(json.dumps(dict(status='NORMAL_FULL_CHARACTER_11S_REVIEW_READY',fingerprint=pub['fingerprint'],frames=[301,360],native_keyframes=[326,331,336]),indent=2),'utf8')
print('NORMAL_11S_REVIEW_READY',flush=True)
