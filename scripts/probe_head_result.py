import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/keqing_head/fit02/work.blend'),load_ui=False,use_scripts=False)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'))
keys=body.data.shape_keys
print('KEYS',keys.key_blocks[0].name,[(k.name,k.value,k.relative_key.name) for k in keys.key_blocks if k.value or k==keys.key_blocks[0]],'DRIVERS',len(keys.animation_data.drivers) if keys.animation_data else 0,flush=True)
print('BASIS_RAW',max((v.co-k.co).length for v,k in zip(body.data.vertices,keys.key_blocks[0].data)),flush=True)
deps=bpy.context.evaluated_depsgraph_get();eval_obj=body.evaluated_get(deps);me=eval_obj.to_mesh()
for mi,mat in enumerate(body.data.materials):
 if mat.mmd_material.name_j not in ('面','口舌','目','肌','Body'):continue
 ids={i for f in body.data.polygons if f.material_index==mi for i in f.vertices}
 error=max((me.vertices[i].co-body.data.vertices[i].co).length for i in ids)
 print('MATERIAL_DELTA',mat.mmd_material.name_j,error,flush=True)
 print('VERTEX',[(i,list(body.data.vertices[i].co),list(me.vertices[i].co),[(body.vertex_groups[g.group].name,g.weight) for g in body.data.vertices[i].groups]) for i in sorted(ids)[:2]],flush=True)
for name in ('頭','首','目.L','目.R','両目','舌１','舌２'):
 b=arm.pose.bones[name];print('BONE',name,'rest',list(b.bone.head_local),'pose',list(b.matrix.translation),'basis',[list(row) for row in b.matrix_basis],'constraints',[(c.name,c.type) for c in b.constraints],'id',b.mmd_bone.bone_id,'add',b.mmd_bone.additional_transform_bone,flush=True)
