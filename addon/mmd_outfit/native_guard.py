"""Small automation entry point for native Blender clothing pose guards."""
import json,math
import bpy
from .skin_collision import collider,install
from .forearm_clearance import install as forearm_clearance
from .minimum_skin_gap import install as minimum_gap


def add_skin_guard(body,garment,vertex_group,*,offset=.0035,forearms=False):
    """Use an explicit existing region group; never save or clear the scene."""
    body=bpy.data.objects[body] if isinstance(body,str) else body
    garment=bpy.data.objects[garment] if isinstance(garment,str) else garment
    if body==garment or body.type!='MESH' or garment.type!='MESH':raise ValueError('Choose separate skin and garment meshes')
    if not math.isfinite(offset) or not .0001<=offset<=.02:raise ValueError('Clearance must be between 0.1 and 20 mm')
    if garment.get('native_pose_guard') or any(m.name.startswith('Keep clothing outside posed skin') for m in garment.modifiers):raise ValueError('This garment already has a native pose guard; inspect its modifiers instead of stacking another')
    group=garment.vertex_groups.get(vertex_group)
    if group is None:raise ValueError('Missing garment region group: '+vertex_group)
    ids={v.index for v in garment.data.vertices if any(g.group==group.index and g.weight>.5 for g in v.groups)}
    if not ids:raise ValueError('The selected clothing region is empty')
    if not any(getattr(getattr(m,'mmd_material',None),'name_j',None)=='Body' for m in body.data.materials):raise ValueError('This MMD helper requires the exact skin material role Body')
    arm=next((m.object for m in body.modifiers if m.type=='ARMATURE'),None)
    if forearms and (arm is None or any(n not in arm.data.bones for n in ('ひじ.L','ひじ.R','手首.L','手首.R'))):raise ValueError('Forearm guard requires MMD elbow and wrist landmarks')
    proxy=next((o for o in bpy.context.scene.objects if o.get('outfit_skin_source')==body.name),None) or collider(body)
    result=install(garment,proxy,ids,group_name='NativeGuardRegion',offset=offset,subdivision=2)
    if forearms:result['forearms']=forearm_clearance(garment,body,arm,region='OutfitAudit_NativeGuardRegion',margin=offset)
    result['minimum_gap']=minimum_gap(garment,proxy,'OutfitAudit_NativeGuardRegion',gap=offset)
    result.update(body=body.name,garment=garment.name,source_vertex_group=vertex_group)
    garment['native_pose_guard']=json.dumps(result,ensure_ascii=False);bpy.context.view_layer.update();return result
