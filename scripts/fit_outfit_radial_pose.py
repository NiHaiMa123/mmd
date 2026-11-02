"""Anatomical outer-envelope fitting; static pose diagnostic, not dynamics."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,SKIN,HAND_PREFIX
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.show_viewport=False;sub.show_render=False
def capture(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();me.calc_loop_triangles();co=np.array([v.co[:] for v in me.vertices]);faces=np.array([t.vertices[:] for t in me.loop_triangles]);weights=[[(g.group,g.weight) for g in v.groups] for v in me.vertices];material=np.array([t.material_index for t in me.loop_triangles]);ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces,weights,material
skin,body_faces,_,body_material=capture(body);regions=skin_regions(body,arm);vertex_labels=np.full(len(skin),'excluded',dtype='U20')
for r,ids in regions['ids'].items():
    if r!='excluded':vertex_labels[ids]=r
face_labels=[]
for f in body_faces:
    labels=list(vertex_labels[f]);face_labels.append(max(set(labels),key=labels.count))
allowed=np.array([body.data.materials[int(i)].name in SKIN for i in body_material]);trees={}
for key in ('core','arm.L','arm.R','leg.L','leg.R'):
    selection=np.array([label==key if key!='core' else not label.startswith('arm') for label in face_labels])&allowed;fs=body_faces[selection];trees[key]=BVHTree.FromPolygons(skin.tolist(),fs.tolist(),all_triangles=True)
def head(n):return np.array(arm.matrix_world@arm.pose.bones[n].head)
spine=[head(n) for n in ('下半身','上半身','上半身2','上半身3','首','頭') if n in arm.pose.bones];up=spine[-1]-spine[0];up/=np.linalg.norm(up);spine=[spine[0]-up*.65,*spine,spine[-1]+up*.15];paths={'core':spine}
for s in ('L','R'):paths['arm.'+s]=[head(n+'.'+s) for n in ('腕','ひじ','手首')];paths['leg.'+s]=[head(n+'.'+s) for n in ('足','ひざ','足首')]
def closest_axis(point,path):
    candidates=[]
    for a,b in zip(path[:-1],path[1:]):
        edge=b-a;t=np.clip(np.dot(point-a,edge)/np.dot(edge,edge),0.,1.);q=a+t*edge;candidates.append((np.dot(point-q,point-q),q))
    return min(candidates,key=lambda v:v[0])[1]
def outside(point,key,margin):
    center=closest_axis(point,paths[key]);delta=point-center;length=np.linalg.norm(delta)
    if length<1e-6:return point
    direction=delta/length;origin=center.copy();last=0.;travel=0.
    for _ in range(24):
        q,n,i,d=trees[key].ray_cast(Vector(origin),Vector(direction),.85-travel)
        if q is None:break
        last=np.linalg.norm(np.array(q)-center);travel=last+.00002;origin=center+direction*travel
        if travel>.84:break
    return center+direction*max(length,last+margin) if last else point
def kind(name):
    bone=arm.pose.bones.get(name)
    while bone:
        if bone.name in ('腕.L','ひじ.L','手首.L'):return 'arm.L'
        if bone.name in ('腕.R','ひじ.R','手首.R'):return 'arm.R'
        bone=bone.parent
    return 'core'
def override(obj,points):
    m=np.linalg.inv(np.array(obj.matrix_world));points=points@m[:3,:3].T+m[:3,3];me=bpy.data.meshes.new(obj.name+'_EnvelopePositions');me.from_pydata(points.tolist(),[],[]);helper=bpy.data.objects.new(obj.name+'_EnvelopePositions',me);scene.collection.objects.link(helper);helper.matrix_world=obj.matrix_world.copy();helper.hide_render=True;helper.hide_set(True);helper['outfit_backup']=True;nt=bpy.data.node_groups.new(obj.name+'_EnvelopeFit','GeometryNodeTree');nt.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');nt.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n,l=nt.nodes,nt.links;inp=n.new('NodeGroupInput');info=n.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=helper;pos=n.new('GeometryNodeInputPosition');idx=n.new('GeometryNodeInputIndex');sample=n.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT';l.new(info.outputs['Geometry'],sample.inputs['Geometry']);l.new(pos.outputs[0],sample.inputs['Value']);l.new(idx.outputs[0],sample.inputs['Index']);move=n.new('GeometryNodeSetPosition');l.new(inp.outputs['Geometry'],move.inputs['Geometry']);l.new(sample.outputs['Value'],move.inputs['Position']);output=n.new('NodeGroupOutput');l.new(move.outputs['Geometry'],output.inputs['Geometry']);mod=obj.modifiers.new('Static anatomical envelope frame 325','NODES');mod.node_group=nt;return mod
report={'status':'STATIC_ANATOMICAL_ENVELOPE_REQUIRES_AUDIT','frame':325,'body_coordinates_changed':False,'new_physical_simulation':False,'objects':{}}
for name in ('Cloth','SleeveLining'):
    obj=bpy.data.objects[name];co,faces,weights,_=capture(obj);original=co.copy();names={g.index:g.name for g in obj.vertex_groups if g.name in arm.pose.bones};labels=[];fingers=[]
    for point,groups in zip(co,weights):
        dominant=max(((v,names[i]) for i,v in groups if i in names),default=(0.,''))[1];label=kind(dominant)
        if name=='SleeveLining':label=min(('arm.L','arm.R'),key=lambda k:np.linalg.norm(point-closest_axis(point,paths[k])))
        labels.append(label);fingers.append(dominant.startswith(HAND_PREFIX[1:]))
    for iteration in range(5):
        for i in range(len(co)):
            if fingers[i]:continue
            if labels[i]!='core':co[i]=outside(co[i],labels[i],.003)
            co[i]=outside(co[i],'core',.004)
        print('ANATOMICAL_CLOTH_ENVELOPE',name,iteration,float(np.linalg.norm(co-original,axis=1).max()),flush=True)
    mod=override(obj,co);report['objects'][name]={'vertices':len(co),'max_displacement_m':float(np.linalg.norm(co-original,axis=1).max())}
    if name=='Cloth':
        bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=list(cloth.modifiers).index(sub))
sub.show_viewport=True;sub.show_render=True;sub.levels=1;sub.render_levels=1;scene.frame_start=325;scene.frame_end=325;bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_Envelope325.blend'),compress=True);(out/'envelope_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
