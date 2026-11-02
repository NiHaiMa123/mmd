"""Read-only inspection of the actual animated rig before building contact corrections."""
import json, sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
arm=bpy.data.objects['达妮娅_arm']; body=bpy.data.objects['达妮娅_mesh']
out=ROOT/'outputs/cynical_cloth15/contact_motion';out.mkdir(parents=True,exist_ok=True)
for obj in bpy.data.objects:
    if obj.type=='MESH' and obj!=body:obj.hide_viewport=True
scene=bpy.context.scene;scene.frame_set(437)
rows=[]
for b in arm.pose.bones:
    if any(t in b.name for t in ('腕','ひじ','手首','肩','上半身','下半身','首','頭','足','ひざ')):
        rows.append(dict(name=b.name,parent=b.parent.name if b.parent else None,head=list(arm.matrix_world@b.head),tail=list(arm.matrix_world@b.tail),rotation_mode=b.rotation_mode,constraints=[dict(name=c.name,type=c.type,mute=c.mute,influence=c.influence) for c in b.constraints],deform=b.bone.use_deform))
report=dict(bones=rows,scale=list(arm.scale),matrix=[list(r) for r in arm.matrix_world],materials=[dict(index=i,name=m.name,polygons=sum(f.material_index==i for f in body.data.polygons)) for i,m in enumerate(body.data.materials)],modifiers=[dict(name=m.name,type=m.type,visible=m.show_viewport) for m in body.modifiers],action=arm.animation_data.action.name if arm.animation_data else None)
from collections import Counter
report['dominant_groups']=dict(Counter(body.vertex_groups[max((g for g in v.groups if not body.vertex_groups[g.group].name.startswith('mmd_')),key=lambda g:g.weight).group].name for v in body.data.vertices if any(not body.vertex_groups[g.group].name.startswith('mmd_') for g in v.groups)))
report['all_bones']=[dict(name=b.name,parent=b.parent.name if b.parent else None,rest=[list(r) for r in b.bone.matrix_local],basis=[list(r) for r in b.matrix_basis],posed=[list(r) for r in b.matrix],constraints=[c.type for c in b.constraints]) for b in arm.pose.bones]
report['garments']={}
for name in ('Cloth','Stockings','SleeveLining'):
    o=bpy.data.objects.get(name)
    if o:
        vg={g.index:g.name for g in o.vertex_groups if not g.name.startswith(('mmd_','Outfit','Sleeve','Cloth'))}
        report['garments'][name]=dict(materials=[m.name for m in o.data.materials],dominant=dict(Counter(max(((g.weight,vg[g.group]) for g in v.groups if g.group in vg),default=(0,''))[1] for v in o.data.vertices)))
(out/'rig_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('RIG_INSPECTION_READY',str(out),flush=True)
