"""Preserve an existing upstream-plugin bake in an isolated review project."""
import argparse,hashlib,json,shutil,struct,sys
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);assert not (out/'setup.json').exists()
candidate=repo.parent/'work/headswap_xl_codex/jiggle_physics_20261031/candidate13';original=json.loads((candidate/'bake_report.json').read_text('utf8'));source=Path(original['blend']);digest=hashlib.sha256(source.read_bytes()).hexdigest()
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();assert s.render.fps==30 and s.render.fps_base==1
assert arm.animation_data.action.name==original['action'];assert not s.rigidbody_world or not s.rigidbody_world.enabled
assert not any('jiggle' in getattr(f,'__module__','').lower() for f in list(bpy.app.handlers.frame_change_pre)+list(bpy.app.handlers.frame_change_post)),'Read existing baked keys only'
assert s.camera and not s.camera.animation_data and not s.camera.constraints
active_cloth=[(ob.name,md.name) for ob in bpy.data.objects for md in ob.modifiers if md.type=='CLOTH' and (md.show_viewport or md.show_render)]
assert not active_cloth,('Unexpected live Cloth',active_cloth)
reference={}
for frame in [1,256,321,331,376,450]:
 s.frame_set(frame);bpy.context.view_layer.update();reference[frame]=coords(actor)
cache=out/'cache';cache.mkdir(exist_ok=True);caches=[]
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':
   src=Path(bpy.path.abspath(md.filepath));assert src.is_file(),src;dst=cache/src.name
   if not dst.exists():shutil.copy2(src,dst)
   md.filepath=str(dst)
   with dst.open('rb') as f:magic,version,points,start,step,samples=struct.unpack('<12siiffi',f.read(32))
   assert magic==b'POINTCACHE2\0' and dst.stat().st_size==32+points*samples*12
   caches.append(dict(object=ob.name,path=str(dst),points=points,start=start,step=step,samples=samples))
s['ReviewExistingJiggleBakeOnly']=True;s['ReviewHairDepthLimitCM']=5.;s['ShutdownForbidden']=True;s['ReviewAllHairAccepted']=False
s.frame_start=1;s.frame_end=450;s.frame_set(1);s.render.use_sequencer=False
blend=out/'完整角色_原版Jiggle_5cm复核.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
assert all(Path(bpy.path.abspath(md.filepath)).is_file() for ob in bpy.data.objects for md in ob.modifiers if md.type=='MESH_CACHE')
bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False);s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];checks=[]
for frame,expected in reference.items():
 s.frame_set(frame);bpy.context.view_layer.update();error=float(np.abs(coords(actor)-expected).max());assert error<5e-6,(frame,error);checks.append(dict(frame=frame,maximum_actor_error_m=error))
assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
setup=dict(status='EXISTING_JIGGLE_BAKE_REOPEN_VERIFIED',source=str(source),source_sha256=digest,blend=str(blend),frames=[1,450],source_fps=30,physics_plugin=original['plugin'],baked_hair_bones=144,active_physics_bones_at_bake=90,head_motion='Original production dance, no control motion added',original_materials_and_full_character=True,original_action_preserved=True,source_file_changed=False,new_simulation=False,new_keyframes=False,reopened_mesh_checks=checks,caches=caches,acceptance='Maximum actual hair intrusion depth >5cm is over limit; extent is reference only. Naturalness assessed separately.',shutdown_forbidden=True)
(out/'setup.json').write_text(json.dumps(setup,ensure_ascii=False,indent=2),'utf8');print('JIGGLE_RECHECK_PREPARED',json.dumps(setup,ensure_ascii=False),flush=True)
