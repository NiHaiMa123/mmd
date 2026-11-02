import sys,json
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/stockings_sleeves/v4/work.blend'),load_ui=False,use_scripts=False)
arm=bpy.data.objects['达妮娅_arm'];arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.mmd_tools.import_vmd(filepath=str(ROOT/'outputs/keqing_head/proportions_v2/mmd/grounded.vmd'),scale=.08,rename_bones=True,margin=0,log_level='ERROR');bpy.context.scene.frame_set(256);bpy.context.view_layer.update()
proxy=bpy.data.objects['Outfit_SkinCollider'];body=bpy.data.objects['达妮娅_mesh'];stock=bpy.data.objects['Stockings'];deps=bpy.context.evaluated_depsgraph_get()
for obj in (body,proxy,stock):
    ev=obj.evaluated_get(deps);me=ev.to_mesh();pts=[v.co for v in me.vertices];print('OBJECT',obj.name,'verts',len(pts),'range',[[min(p[k] for p in pts),max(p[k] for p in pts)] for k in range(3)],'mods',[(m.name,m.type) for m in obj.modifiers],flush=True);ev.to_mesh_clear()
mod=stock.modifiers[-1];print('WRAP',mod.wrap_method,mod.wrap_mode,mod.vertex_group,mod.offset,flush=True)
after=[v.co.copy() for v in stock.evaluated_get(deps).data.vertices];mod.show_viewport=False;bpy.context.view_layer.update();before=[v.co.copy() for v in stock.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices];print('MAX_CORRECTION',max((a-b).length for a,b in zip(after,before)),flush=True)
names={g.index:g.name for g in body.vertex_groups};counts={}
for v in body.data.vertices:
    if .75<v.co.z<1.1 and abs(v.co.x)<.2:
        n=sum(g.weight>1e-7 and names[g.group] in arm.data.bones for g in v.groups);counts[n]=counts.get(n,0)+1
print('BONE_COUNTS',counts,'EXAMPLE',[(names[g.group],g.weight) for g in body.data.vertices[12000].groups],flush=True)
for m in stock.modifiers:
    if m.type!='ARMATURE':m.show_viewport=False
bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();sv=stock.evaluated_get(deps).data.vertices;bv=body.evaluated_get(deps).data.vertices
provenance=json.loads((ROOT/'outputs/stockings_sleeves/v4/stocking_provenance.json').read_text())['target_vertices'];rows=[]
for k,binding in enumerate(provenance):
    if len(binding)!=1:continue
    i=binding[0][0]
    if .78<body.data.vertices[i].co.z<1.05:
        rows.append(((sv[k].co-bv[i].co).length,k,i,list(body.data.vertices[i].co)))
rows.sort(reverse=True);print('LARGEST_CORRESPONDENCE_ERRORS',rows[:10],flush=True)
_,k,i,_=rows[0];print('WEIGHTS',[(body.vertex_groups[g.group].name,g.weight) for g in body.data.vertices[i].groups],[(stock.vertex_groups[g.group].name,g.weight) for g in stock.data.vertices[k].groups],flush=True)
print('BODY_MOD',[(m.name,m.use_deform_preserve_volume,m.vertex_group,m.invert_vertex_group) for m in body.modifiers if m.type=='ARMATURE'],'STOCK_MOD',[(m.name,m.use_deform_preserve_volume,m.vertex_group) for m in stock.modifiers if m.type=='ARMATURE'],flush=True)
