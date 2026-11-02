"""Live skin-frame binding for fitted panels and sleeve attachment bands.

Keeps the visible body's mesh, garment UVs and source shape keys. Loose tails
retain their existing cloth carrier; this is not a new dynamic cloth solve.
"""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,SKIN,HAND_PREFIX
from mmd_outfit.stable_sleeve_cloth import bind_clamped_frames
from mmd_outfit.structured_cloth import _tree,_info,_sample,_field
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];arm=bpy.data.objects['达妮娅_arm'];rest=np.array([v.co[:] for v in cloth.data.vertices]);cloth.data.calc_loop_triangles();faces=np.array([t.vertices[:] for t in cloth.data.loop_triangles]);_,weld=np.unique(np.rint(rest/1e-6).astype(np.int64),axis=0,return_inverse=True);parent=np.arange(int(weld.max())+1)
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for f in weld[faces]:
    for i in f[1:]:parent[root(int(i))]=root(int(f[0]))
labels=np.array([root(int(i)) for i in weld]);converted=body.data.copy();conversion=np.linalg.inv(np.array(cloth.matrix_world))@np.array(body.matrix_world);points=np.array([v.co[:] for v in converted.vertices]);points=points@conversion[:3,:3].T+conversion[:3,3];converted.vertices.foreach_set('co',points.reshape(-1));converted.update();converted.calc_loop_triangles();triangles=list(converted.loop_triangles);allowed=[f.index for f in converted.polygons if converted.materials[f.material_index].name in SKIN];region=skin_regions(body,arm);vertex_region=np.full(len(points),'excluded',dtype='U20')
for r,ids in region['ids'].items():
    if r!='excluded':vertex_region[ids]=r
trees={};table={};allowed_set=set(allowed)
for kind in ('core','arm.L','arm.R'):
    selected=[]
    for t in triangles:
        if t.polygon_index not in allowed_set:continue
        lab=list(vertex_region[list(t.vertices)]);label=max(set(lab),key=lab.count)
        if (kind=='core' and not label.startswith('arm')) or label==kind:selected.append(t)
    table[kind]=selected;trees[kind]=BVHTree.FromPolygons(points.tolist(),[t.vertices[:] for t in selected],all_triangles=True)
arm_conversion=np.linalg.inv(np.array(cloth.matrix_world))@np.array(arm.matrix_world)
def resthead(name):
    p=np.array(arm.data.bones[name].head_local);return arm_conversion[:3,:3]@p+arm_conversion[:3,3]
spine=[resthead(name) for name in ('下半身','上半身','上半身2','上半身3','首','頭')];up=spine[-1]-spine[0];up/=np.linalg.norm(up);paths={'core':[spine[0]-up*.3,*spine,spine[-1]+up*.1]}
for side in ('L','R'):paths['arm.'+side]=[resthead('腕.'+side),resthead('ひじ.'+side),resthead('手首.'+side)]
group_names={g.index:g.name for g in cloth.vertex_groups if g.name in arm.data.bones};dominant=[max(((g.weight,group_names[g.group]) for g in v.groups if g.group in group_names),default=(0.,''))[1] for v in cloth.data.vertices];weight=np.zeros(len(rest));fitted=rest.copy();max_move=0.;counts={}
for i,point in enumerate(rest):
    component=int(labels[i]);kind='core';fingers=dominant[i].startswith(HAND_PREFIX[1:])
    if component in (13948,5977):strength=1.
    elif component in (4311,14732,4035,15511):
        if fingers:continue
        kind='arm.L' if component in (14732,15511) else 'arm.R';q,n,j,d=trees[kind].find_nearest(Vector(point));strength=np.clip((.085-d)/.060,0.,1.);strength=strength*strength*(3-2*strength)
        if component in (4035,15511):
            begin=resthead('ひじ.'+kind[-1]);end=resthead('手首.'+kind[-1]);edge=end-begin;t=np.dot(point-begin,edge)/np.dot(edge,edge);fade=np.clip((1.-t)/.15,0.,1.);strength*=fade*fade*(3-2*fade)
        if strength<=0:continue
    else:continue
    candidates=[]
    for begin,end in zip(paths[kind][:-1],paths[kind][1:]):
        edge=end-begin
        if np.dot(edge,edge)<1e-12:continue
        t=np.clip(np.dot(point-begin,edge)/np.dot(edge,edge),0.,1.);axis=begin+edge*t;candidates.append((np.linalg.norm(point-axis),axis))
    distance,axis=min(candidates,key=lambda v:v[0]);direction=point-axis;length=np.linalg.norm(direction)
    if length<1e-6:continue
    direction/=length;origin=axis.copy();last=None;travel=0.
    for _ in range(24):
        q,n,j,d=trees[kind].ray_cast(Vector(origin),Vector(direction),.6-travel)
        if q is None:break
        travel=np.linalg.norm(np.array(q)-axis)+.00002;last=np.array(q);origin=axis+direction*travel
        if travel>.59:break
    if last is None:q,n,j,d=trees[kind].find_nearest(Vector(point));last=np.array(q);target=last+np.array(n)*.003
    else:target=axis+direction*max(length,np.linalg.norm(last-axis)+.003)
    fitted[i]=target;weight[i]=strength;max_move=max(max_move,float(np.linalg.norm(target-point)));counts[kind]=counts.get(kind,0)+1
mesh=bpy.data.meshes.new('BodyFittedGarmentCarrier');mesh.from_pydata(fitted.tolist(),[],[]);carrier=bpy.data.objects.new('BodyFittedGarmentCarrier',mesh);scene.collection.objects.link(carrier);carrier.matrix_world=cloth.matrix_world.copy();carrier.hide_render=True;carrier.hide_set(True);carrier['outfit_backup']=True;selected=np.flatnonzero(weight>0).tolist();binding=bind_clamped_frames(carrier,body,converted,allowed,selected);attribute=cloth.data.attributes.get('OutfitLiveSkinBinding') or cloth.data.attributes.new('OutfitLiveSkinBinding','FLOAT','POINT');attribute.data.foreach_set('value',weight)
tree=_tree('Outfit_LiveSkinPanelFit',True);n,l=tree.nodes,tree.links;inp=n.new('NodeGroupInput');idx=n.new('GeometryNodeInputIndex');sample=_sample(tree,_info(tree,carrier),idx.outputs[0]);pos=n.new('GeometryNodeInputPosition');subtract=n.new('ShaderNodeVectorMath');subtract.operation='SUBTRACT';l.new(sample,subtract.inputs[0]);l.new(pos.outputs[0],subtract.inputs[1]);scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';l.new(subtract.outputs[0],scale.inputs[0]);l.new(_field(tree,'OutfitLiveSkinBinding'),scale.inputs['Scale']);move=n.new('GeometryNodeSetPosition');l.new(inp.outputs['Geometry'],move.inputs['Geometry']);l.new(scale.outputs[0],move.inputs['Offset']);output=n.new('NodeGroupOutput');l.new(move.outputs['Geometry'],output.inputs['Geometry']);mod=cloth.modifiers.new('Panels follow actual posed body','NODES');mod.node_group=tree;sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=list(cloth.modifiers).index(sub));sub.levels=1;sub.render_levels=1;report={'status':'LIVE_SKIN_GARMENT_BINDING_REQUIRES_AUDIT','bound_vertices':len(selected),'by_region':counts,'maximum_rest_fit_change_m':max_move,'binding':binding,'original_body_or_garment_vertex_coordinates_changed':False,'new_cloth_simulation':False};scene.frame_set(325);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_LiveSkin325.blend'),compress=True);(out/'skin_binding.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('LIVE_SKIN_GARMENT_BINDING',json.dumps(report),flush=True)
