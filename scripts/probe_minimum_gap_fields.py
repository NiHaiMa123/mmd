import sys,json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from review_tights_sleeves import evaluate
engine('import_export').ensure_mmd_tools();fit=ROOT/'outputs/stockings_sleeves/v18';bpy.ops.wm.open_mainfile(filepath=str(fit/'work.blend'),load_ui=False,use_scripts=False);arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];proxy=bpy.data.objects['Outfit_SkinCollider'];arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.mmd_tools.import_vmd(filepath=str(ROOT/'outputs/keqing_head/proportions_v2/mmd/grounded.vmd'),scale=.08,rename_bones=True,margin=0,log_level='ERROR');bpy.context.scene.frame_set(1)
nt=next(m.node_group for m in cloth.modifiers if m.type=='NODES' and m.node_group.name.startswith('Outfit_MinimumSkinGap'));n=nt.nodes;l=nt.links;input_=next(x for x in n if x.type=='GROUP_INPUT');out=next(x for x in n if x.type=='GROUP_OUTPUT');geometry=input_.outputs['Geometry']
for name,operation,kind in [('DebugNormal','NORMALIZE','FLOAT_VECTOR'),('DebugDistance','LENGTH','FLOAT'),('DebugSigned','DOT_PRODUCT','FLOAT')]:
    node=next(x for x in n if x.bl_idname=='ShaderNodeVectorMath' and x.operation==operation);store=n.new('GeometryNodeStoreNamedAttribute');store.domain='POINT';store.data_type=kind;store.inputs['Name'].default_value=name;l.new(geometry,store.inputs['Geometry']);l.new(node.outputs['Vector' if kind=='FLOAT_VECTOR' else 'Value'],store.inputs['Value']);geometry=store.outputs['Geometry']
l.new(geometry,out.inputs['Geometry']);bpy.context.view_layer.update();cm,cp=evaluate(cloth);bm,bp=evaluate(body);bodytri=[tuple(t.vertices) for t in bm.loop_triangles if bm.materials[t.material_index].mmd_material.name_j=='Body'];inv=cloth.matrix_world.inverted();bvh=BVHTree.FromPolygons([inv@p for p in bp],bodytri,all_triangles=True)
rows=json.loads((fit/'review/contacts.json').read_text(encoding='utf-8'))['vmd_1']['sleeves_crossings'];ids=sorted({i for row in rows[:10] for i in cm.loop_triangles[row['cloth_triangle']].vertices})[:10]
for label,obj in [('body',body),('cloth',cloth),('proxy',proxy),('arm',arm)]:print('MATRIX',label,[list(row) for row in obj.matrix_world],flush=True)
for i in ids:
    hit,norm,ti,distance=bvh.find_nearest(cm.vertices[i].co)
    print('GAP_VERTEX',i,'region',cm.attributes['OutfitAudit_SleeveRegion'].data[i].value,'node_normal',list(cm.attributes['DebugNormal'].data[i].vector),'node_distance',cm.attributes['DebugDistance'].data[i].value,'node_signed',cm.attributes['DebugSigned'].data[i].value,'real_distance',distance,'real_signed',(cm.vertices[i].co-hit).dot(norm),flush=True)
