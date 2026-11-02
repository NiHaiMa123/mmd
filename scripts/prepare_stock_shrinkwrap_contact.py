"""Configure a stock Outside Shrinkwrap after an unmodified plugin bake.

This is an explicit native geometric contact modifier, not a physics solver.
"""
import argparse,json,shutil,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--offset',type=float,default=.008);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(exist_ok=True)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
m=bpy.data.objects['东雪莲x达妮娅_素体'];body=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部'];base=ROOT.parent/'work/headswap_xl_codex'
z=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');ids=z['ids'];hard=z['same_true_hard_root_mask'];skin_ids=np.load(base/'fullhair_repro_20261030/input_body_aware/skin_ids.npy')
assert not len(np.intersect1d(ids,skin_ids))
group=m.vertex_groups.new(name='NativeOutside_可动头发_保护真实硬根');group.add(ids[~hard].tolist(),1.,'REPLACE')
md=m.modifiers.new('原生Shrinkwrap_Outside_实际发片表面','SHRINKWRAP');md.target=body;md.wrap_method='NEAREST_SURFACEPOINT';md.wrap_mode='OUTSIDE';md.offset=a.offset;md.vertex_group=group.name
cache=out/'cache';cache.mkdir(exist_ok=True)
for obj in bpy.data.objects:
 for modifier in obj.modifiers:
  if modifier.type=='MESH_CACHE':
   old=Path(bpy.path.abspath(modifier.filepath));new=cache/old.name
   if not new.exists():shutil.copy2(old,new)
   modifier.filepath=str(new)
bpy.context.scene.frame_set(1);bpy.context.view_layer.update();path=out/'完整角色_Jiggle原版_原生表面约束_15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
config=dict(source=a.source,blend=str(path),physics='Unmodified upstream Jiggle Physics baked bone animation, Blend=1',surface_contact='Stock Blender Shrinkwrap: Nearest Surface Point / Outside',offset_m=a.offset,target=body.name,movable_hair_vertices=int((~hard).sum()),unmodified_hard_roots=int(hard.sum()),original_weights_modified=False,reference='https://docs.blender.org/manual/en/5.2/modeling/modifiers/deform/shrinkwrap.html',scope='Native geometric correction supplements physics. Requires actual surface, temporal and visual validation.')
(out/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf8');print(json.dumps(config,ensure_ascii=False),flush=True)
