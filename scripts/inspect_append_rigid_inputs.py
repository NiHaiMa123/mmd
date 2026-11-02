import bpy,json,sys
from pathlib import Path
root=Path(r'E:\project\mmd\mmd_repo');sys.path.insert(0,str(root/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools()
p=root.parent/'work/headswap_xl_codex/jiggle_physics_20261031'
bpy.ops.wm.open_mainfile(filepath=str(p/'candidate10/完整角色_Jiggle配置_未烘焙.blend'),use_scripts=False,load_ui=False)
rigids=[]
for o in bpy.data.objects:
 if getattr(o,'mmd_type','')=='RIGID_BODY':
  r=o.mmd_rigid;rigids.append(dict(name=o.name,bone=r.bone,parent=o.parent.name if o.parent else None,position=list(o.location),world=list(o.matrix_world.translation),type=r.type,shape=r.shape,size=list(r.size)))
roots=[dict(name=o.name,parent=o.parent.name if o.parent else None) for o in bpy.data.objects if getattr(o,'mmd_type','')=='ROOT']
joints=[dict(name=o.name,a=o.rigid_body_constraint.object1.name if o.rigid_body_constraint and o.rigid_body_constraint.object1 else None,b=o.rigid_body_constraint.object2.name if o.rigid_body_constraint and o.rigid_body_constraint.object2 else None) for o in bpy.data.objects if getattr(o,'mmd_type','')=='JOINT']
(p/'append_inputs.json').write_text(json.dumps(dict(roots=roots,rigids=rigids,joints=joints),ensure_ascii=False,indent=2),'utf8')
print('INPUTS',len(roots),len(rigids),len(joints),flush=True);print(json.dumps(rigids[:4],ensure_ascii=False),flush=True)
