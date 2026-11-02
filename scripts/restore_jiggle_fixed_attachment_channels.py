"""Preserve static FK channels when the upstream bake selects simulated bones only."""
import bpy,json,sys
from pathlib import Path
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/jiggle_physics_20261031';source=base/'candidate13';out=base/'candidate14';out.mkdir(exist_ok=True)
config=json.loads((source/'configuration.json').read_text('utf8'));report=json.loads((source/'bake_report.json').read_text('utf8'));fixed=[r['name'] for r in config['hair_bones'] if not r['enabled']]
bpy.ops.wm.open_mainfile(filepath=str(source/'完整角色_Jiggle配置_未烘焙.blend'),load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update();arm=bpy.data.objects['东雪莲x达妮娅_骨架']
values={name:dict(location=tuple(arm.pose.bones[name].location),rotation_quaternion=tuple(arm.pose.bones[name].rotation_quaternion),scale=tuple(arm.pose.bones[name].scale)) for name in fixed}
bpy.ops.wm.open_mainfile(filepath=report['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;arm=bpy.data.objects['东雪莲x达妮娅_骨架'];s.frame_set(1);bpy.context.view_layer.update();differences=[]
for name,props in values.items():
 b=arm.pose.bones[name]
 differences.append(dict(bone=name,before={prop:list(getattr(b,prop)) for prop in props},fixed=props))
 for prop,value in props.items():
  setattr(b,prop,value)
  for frame in [1,450]:b.keyframe_insert(data_path=prop,frame=frame,group=name)
for obj in bpy.data.objects:
 for md in obj.modifiers:
  if md.type=='MESH_CACHE':md.filepath=bpy.path.abspath(md.filepath)
arm.animation_data.action.name='JigglePhysics_原版烘焙_保留固定附着FK'
s.frame_set(1);bpy.context.view_layer.update();path=out/'完整角色_JigglePhysics原版_15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
report.update(blend=str(path),fixed_attachment_channels_retained=fixed,source_bake=str(source),dynamic_hair_contact_audit_pending=True)
(out/'bake_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');(out/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf8')
(out/'fixed_attachment_channels.json').write_text(json.dumps(differences,ensure_ascii=False,indent=2),'utf8');print(json.dumps(dict(blend=str(path),fixed_bones=len(fixed),differences=differences[:3]),ensure_ascii=False),flush=True)
