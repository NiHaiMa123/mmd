"""Extend exact original body motion to 17.5 seconds; preserve hair setup."""
import argparse,json,shutil,struct,sys,time
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);assert not (out/'setup.json').exists()
base=repo.parent/'work/headswap_xl_codex';previous=base/'classic_local_surface_20261101/prepared02'
prepared=json.loads((previous/'setup.json').read_text('utf8'));oldinput=base/'fullhair_repro_20261030/input_body_aware'
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=prepared['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();assert s.render.fps==30
assert not s.camera.animation_data and not s.camera.constraints
data=out/'input_body_aware';data.mkdir(exist_ok=True)
for name in ['skin_ids.npy','body_faces.npy','real_body_faces.npy']:shutil.copy2(oldinput/name,data/name)
skin=np.load(data/'skin_ids.npy');old=np.load(oldinput/'body.npy',mmap_mode='r')
assert len(old)==3593
body=np.lib.format.open_memmap(data/'body.npy',mode='w+',dtype='<f4',shape=(4201,len(skin),3));body[:len(old)]=old
controls=[]
for f in [1,226,321,352,450]:
 s.frame_set(f);bpy.context.view_layer.update();err=float(np.abs(coords(actor)[skin]-old[(f-1)*8]).max());assert err<5e-6
 controls.append(dict(frame=f,original_body_error_m=err))
pose450=coords(actor)[skin].copy();started=time.monotonic()
for k in range(len(old),len(body)):
 f=1+k/8;s.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();body[k]=coords(actor)[skin]
 if (k-len(old))%80==0:
  row=dict(stage='EXTENDING_ORIGINAL_BODY',frame=f,samples_extended=k-len(old)+1,total_extended=len(body)-len(old),elapsed_s=time.monotonic()-started)
  (out/'status.json').write_text(json.dumps(row,indent=2),'utf8');print('BODY_EXTENSION',json.dumps(row),flush=True)
body.flush();delta=float(np.linalg.norm(body[-1]-pose450,axis=1).max());assert delta>.001,('No original body motion beyond 15 seconds',delta)
cache=out/'cache';cache.mkdir(exist_ok=True);collider=cache/'animated_body_collider.pc2'
with collider.open('wb') as f:
 f.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,len(skin),1.,.25,2101))
 for k in range(0,len(body),2):f.write(np.asarray(body[k],dtype='<f4').tobytes())
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':
   src=Path(bpy.path.abspath(md.filepath));dst=cache/src.name
   assert not src.name.startswith('ClassicHair_'),'Use unbaked preparation'
   if src.name!='animated_body_collider.pc2' and not dst.exists():shutil.copy2(src,dst)
   md.filepath=str(dst)
s.frame_set(1);s.frame_end=526;s['RequestedPreviewFPS']=24;s['RequestedSourceSeconds']='7.5-17.5';s['ShutdownForbidden']=True
blend=out/'完整角色_7.5至17.5秒预览_未模拟.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
prepared.update(blend=str(blend),source_prepared=prepared['blend'],expected_body_input=str(data),frames_planned=[1,526],preview=dict(source_fps=30,output_fps=24,source_seconds=[7.5,17.5],duration_seconds=10,output_frames=240,samples=24,resolution=[1920,1080]),body_extension_controls=controls,body_motion_after_15s_max_displacement_m=delta)
(out/'setup.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2),'utf8')
(data/'export_complete.json').write_text(json.dumps(dict(source=prepared['source_prepared'],frames=[1,526],sample_step=.125,samples=4201,body_vertices=len(skin),collider_pc2_samples=2101,original_1_to_450_reused=True,body_motion_edited=False,elapsed_s=time.monotonic()-started),indent=2),'utf8')
print('PREVIEW_PREPARED',json.dumps(dict(blend=str(blend),body_motion_after_15s_m=delta),ensure_ascii=False),flush=True)
