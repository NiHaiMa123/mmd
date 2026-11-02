"""Attach a verified full-head trajectory to a complete normal MMD scene."""
import sys,json,argparse,shutil,hashlib
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.streamed_position_cache import bind_streamed_cache
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);pub=json.loads((out/'cache_publication.json').read_text('utf8'));src=Path(pub['input']);manifest=json.loads((src/'export_complete.json').read_text('utf8'));profile=json.loads(Path(manifest['rig_profile']).read_text('utf8'));ids=np.load(src/'hair_ids.npy');engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=manifest['source_blend'],load_ui=False,use_scripts=False);m=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];s=bpy.context.scene;removed=[]
for mod in list(m.modifiers):
 if mod.type!='NODES' or not mod.node_group:continue
 attrs=[n.inputs['Name'].default_value for n in mod.node_group.nodes if n.bl_idname=='GeometryNodeInputNamedAttribute'];superseded=[]
 for name in attrs:
  attr=m.data.attributes.get(name)
  if attr and name.startswith('HairContact_MeasuredIndex'):
   values=np.empty(len(m.data.vertices),dtype=np.int32);attr.data.foreach_get('value',values)
   if np.any(values[ids]>=0):superseded.append(name)
 if superseded:
  removed.append(dict(modifier=mod.name,attributes=superseded));m.modifiers.remove(mod)
  for name in superseded:
   if name in m.data.attributes:m.data.attributes.remove(m.data.attributes[name])
binding=bind_streamed_cache(m,ids,out/'cache/full_head.pc2',first=manifest['frames'][0],anchor_armature=arm,anchor_bone='頭',namespace='WholeHeadPhysics')
caches=[]
for obj in s.objects:
 for mod in obj.modifiers:
  if mod.type=='MESH_CACHE':
   old=Path(bpy.path.abspath(mod.filepath)).resolve();assert old.exists(),str(old)
   if old==Path(binding['cache']):new=old
   else:
    digest=hashlib.sha256()
    with old.open('rb') as stream:
     for block in iter(lambda:stream.read(8*1024*1024),b''):digest.update(block)
    new=out/'cache'/(obj.name.replace('.','_')+'_'+digest.hexdigest()[:12]+'_'+old.name)
    if old!=new and not new.exists():shutil.copy2(old,new)
   mod.filepath='//cache/'+new.name;caches.append(dict(object=obj.name,path=mod.filepath,bytes=new.stat().st_size))
s.frame_start=int(manifest['frames'][0]);s.frame_end=int(manifest['frames'][1]);s.frame_set(s.frame_start);s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.fps=30;s['FullHairCachePublication']='//cache_publication.json';s['FullHairAlgorithmFingerprint']=pub['fingerprint'];candidate=out/'完整角色_整头连续物理_15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True,relative_remap=False)
(out/'assembly.json').write_text(json.dumps(dict(blend=str(candidate),source=manifest['source_blend'],binding=binding,removed_superseded_hair_bindings=removed,cache_files=caches,source_geometry_weights_actions_edited=False,all_head_parts_visible=True,publication=pub),ensure_ascii=False,indent=2),encoding='utf8');print('COMPLETE_CHARACTER_ASSEMBLED',str(candidate),flush=True)
