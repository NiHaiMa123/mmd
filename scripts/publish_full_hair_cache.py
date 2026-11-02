"""Publish only checkpointed, validated simulation samples to a streamed PC2."""
import sys,argparse,json,struct,os
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--run',required=True);p.add_argument('--out',required=True);a=p.parse_args();src=Path(a.input);run=Path(a.run);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);cache=out/'cache/full_head.pc2';cache.parent.mkdir(exist_ok=True);manifest=json.loads((src/'export_complete.json').read_text('utf8'));state=json.loads((run/'latest_state.json').read_text('utf8'));fingerprint=json.loads((run/'input_fingerprint.json').read_text('utf8'))['fingerprint'];assert fingerprint==state['fingerprint'];n=manifest['samples'];count=manifest['hair_vertices'];positions=np.load(run/'positions.npy',mmap_mode='r');heads=np.load(src/'anchors.npy',mmap_mode='r')[:,manifest['anchor_bones'].index('頭')];record=out/'cache_publication.json';old=json.loads(record.read_text('utf8')) if record.exists() else None
if old and old['fingerprint']!=fingerprint:
 proof=json.loads((run/'prefix_fork_proof.json').read_text('utf8'))
 assert proof['status']=='TRUE_STATE_PREFIX_FORK_VERIFIED' and proof['new_fingerprint']==fingerprint,'Cannot mix different physical trajectories'
 if proof['old_fingerprint']!=old['fingerprint']:
  sibling=json.loads((Path(old['run'])/'prefix_fork_proof.json').read_text('utf8'));assert sibling['new_fingerprint']==old['fingerprint'] and sibling['old_fingerprint']==proof['old_fingerprint'] and old['published_through_sample']<=min(sibling['checkpoint_sample'],proof['checkpoint_sample']),'Cannot mix different physical trajectories'
 if old['published_through_sample']>proof['checkpoint_sample']:
  assert proof.get('invalidate_after_checkpoint',False),'Cannot overwrite a published trajectory without an explicit invalidation proof'
  old['published_through_sample']=proof['checkpoint_sample']
 old['fingerprint']=fingerprint
first=old['published_through_sample']+1 if old else 0;last=state['sample'];assert last>=first-1
if not cache.exists():
 with cache.open('xb') as f:f.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,count,0.,manifest['sample_step'],n));f.truncate(32+n*count*12)
assert cache.stat().st_size==32+n*count*12
with cache.open('r+b') as f:
 for k in range(first,last+1,32):
  end=min(last+1,k+32);x=np.asarray(positions[k:end],dtype=np.float64);inv=np.linalg.inv(heads[k:end]);local=(np.einsum('fij,fvj->fvi',inv[:,:3,:3],x)+inv[:,None,:3,3]).astype('<f4');assert np.isfinite(local).all();f.seek(32+k*count*12);f.write(local.tobytes())
 f.flush();os.fsync(f.fileno())
complete=last==n-1 and json.loads((run/'result.json').read_text('utf8'))['stage']=='COMPLETE' if (run/'result.json').exists() else False
r=dict(status='COMPLETE_PHYSICAL_TRAJECTORY' if complete else 'LIVE_CANDIDATE_RENDER_ONLY_PUBLISHED_PREFIX',fingerprint=fingerprint,input=str(src),run=str(run),cache=str(cache),published_through_sample=last,published_through_frame=manifest['frames'][0]+last*manifest['sample_step'],total_samples=n,step=manifest['sample_step'],hard_roots=int(np.load(src/'hard_roots.npy').sum()),all_head_parts_present=True,body_contact_verified_per_sample=True,self_collision_solved=False);temp=record.with_suffix('.tmp.json');temp.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(record);print('PUBLISHED',json.dumps(r,ensure_ascii=False),flush=True)
