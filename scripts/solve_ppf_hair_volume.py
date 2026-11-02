"""Run a clean volumetric hair clump through the existing native PPF backend."""
import sys,os,argparse,json,time,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];native=ROOT/'tools/ppf/native';sys.path.insert(0,str(native));dll=os.add_dll_directory(str(native/'bin'))
from frontend import App
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output-fps',type=int,default=120);p.add_argument('--frames',type=int);p.add_argument('--validate-only',action='store_true');p.add_argument('--soft-attachments',action='store_true');p.add_argument('--attachment-strength',type=float,default=20.);p.add_argument('--dt',type=float,default=.003);a=p.parse_args();out=Path(a.input).resolve();data=np.load(out/'trajectories.npz');manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'));cloth=data['cloth'];body=data['body'];source_fps=manifest['fps'];fps=a.output_fps;times=manifest.get('sample_times_s',[k/source_fps for k in range(len(cloth))]);frame_count=a.frames or round(times[-1]*fps)
App.get_data_dirpath=staticmethod(lambda:str(out/'runtime'));app=App.create('real_outfit',cache_dir=str(out/'cache'));app.asset.add.tet('cloth',cloth[0].astype(float),data['cloth_faces'],data['tetrahedra']);app.asset.add.tri('body',body[0].astype(float),data['body_faces']);scene=app.scene.create();garment=scene.add('cloth');garment.param.set('young-mod',1000.).set('poiss-rat',.45).set('density',100.).set('deformation-damping',.005)
fixed=np.flatnonzero(data['pins']>=.99999).tolist();anchor=garment.pin(fixed);partial=np.flatnonzero((data['pins']>0)&(data['pins']<.99999)).tolist();soft=garment.pin(partial).pull(.5).pull_per_vertex(data['pins'][partial]*.5) if partial else None
if a.soft_attachments:anchor.pull(a.attachment_strength)
# Match the official Blender decoder's animated STATIC representation. Without
# this flag a fully pinned *moving* mesh is an elastic SHELL, which is wrong for
# an animation-owned skin collider (and builds unusable skin elastic Hessians).
body_object=scene.add('body');body_object._is_static_moving=True
# The current native release rejects the decoder's zero placeholders. Keep
# ordinary positive defaults; all collider vertices remain prescribed exactly.
body_object.param.set('bend',0.)
collider=body_object.pin(allow_intersection=False)
body_keys=np.load(out/'body_key_indices.npy').tolist() if (out/'body_key_indices.npy').exists() else list(range(len(body)))
if body_keys[0]!=0 or body_keys[-1]!=len(body)-1 or any(b<=a for a,b in zip(body_keys,body_keys[1:])):raise ValueError('Ordered body time keys must include both ends')
for left,right in zip(body_keys,body_keys[1:]):collider.move_to(body[right],times[left],times[right])
for k in range(1,len(cloth)):
    anchor.move_to(cloth[k,fixed],times[k-1],times[k])
    if soft:soft.move_to(cloth[k,partial],times[k-1],times[k])
dt=a.dt
if not 0<dt<=1/60:raise ValueError('Explicit time step must be positive and at most 1/60s')
snapshot=dict(status='BUILDING',frames=frame_count,output_fps=fps,source_fps=source_fps,time_step_s=dt,hard_pins=0 if a.soft_attachments else len(fixed),soft_pins=len(partial)+(len(fixed) if a.soft_attachments else 0),allow_intersection=False,attachment_strength=a.attachment_strength)
if (out/'body_key_reduction.json').exists():snapshot['body_key_reduction']=json.loads((out/'body_key_reduction.json').read_text('utf8'))
(out/'solve_status.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
try:
    built=scene.build();assert len(built.start_links)==0,'Contact exemptions must remain empty'
    if a.validate_only:
        snapshot.update(status='INITIAL_CONTACT_VALIDATED',contact_exemptions=0)
        print('PPF_INITIAL_CONTACT_VALIDATED',flush=True)
        raise SystemExit(0)
    session=app.session.create(built);session.param.set('dt',dt).set('fps',fps).set('frames',frame_count).set('gravity',[0,0,-9.81]).set('auto-save',120).set('save-state-on-finish',True);session=session.build();snapshot.update(status='RUNNING',output=session.output.path,contact_exemptions=0);(out/'solve_status.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8');start=time.time();session.start(blocking=True);snapshot.update(status='FINISHED' if session.finished() else 'STOPPED_OR_FAILED',seconds=time.time()-start)
    latest_frame=session.get.latest_frame();complete=session.finished() and latest_frame>=frame_count
    if not complete:snapshot.update(status='CHECKPOINTED_OR_INCOMPLETE',latest_output_frame=latest_frame)
    if complete:
        ids=np.array(built._map_by_name['cloth'],dtype=int);output_frames=[];volume_frames=[]
        for f in range(frame_count+1):
            got=session.get.vertex(f)
            if got is None:raise RuntimeError(f'Missing solver output frame {f}')
            volume_frames.append(got[0][ids]);output_frames.append(got[0][ids][data['original_mapping']])
        np.save(out/'PPFVolume.npy',np.array(volume_frames,dtype='<f4'));arr=np.array(output_frames,dtype='<f4');np.save(out/'PPFCloth.npy',arr)
        with (out/'PPFCloth.pc2').open('wb') as handle:handle.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,arr.shape[1],0.,1.,len(arr)));handle.write(arr.tobytes())
        snapshot.update(cache_frames=len(arr),cache_vertices=arr.shape[1],cache='PPFCloth.pc2')
except Exception as exc:
    snapshot.update(status='FAILED',error=repr(exc),violations=getattr(exc,'violations',None));raise
finally:(out/'solve_status.json').write_text(json.dumps(snapshot,indent=2,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x)),encoding='utf-8')
print('PPF_OUTFIT_STATUS',snapshot,flush=True)
