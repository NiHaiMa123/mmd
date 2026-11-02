"""Read-only diagnosis and explicitly labelled cutaway from frozen native cache.

No physics advance, coordinate correction or project-file save is performed.
The normal complete-character image is created by the stopped native runner.
"""
import argparse,json,sys,collections
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.geometry import intersect_ray_tri,closest_point_on_tri
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,crosses
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);candidate=Path(a.candidate)
config=json.loads((candidate/'configuration.json').read_text('utf8'))
result=json.loads((candidate/'simulation_result.json').read_text('utf8'))
frame=result['frames_simulated'][1];out=candidate/'contact_diagnosis';out.mkdir(exist_ok=True)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=result['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];display=bpy.data.objects[s['HairDisplayObject']]
proxy=bpy.data.objects['HairProxy_全头共享几何体积'];cloth=next(md for md in proxy.modifiers if md.type=='CLOTH')
assert cloth.point_cache.is_baked and frame<=cloth.point_cache.frame_end
s.frame_set(frame);bpy.context.view_layer.update()
audit=json.loads((candidate/'reopened_frozen_audit/surface_audit.json').read_text('utf8'))
row=next(r for r in audit['rows'] if r['frame']==frame);witnesses=row['witnesses'];assert len(witnesses)==row['crossings']
def evaluated(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    try:
        co=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',co);co=co.reshape(-1,3)
        matrix=np.array(ev.matrix_world);co=co@matrix[:3,:3].T+matrix[:3,3]
        ids=np.array([x.value for x in me.attributes['SourceVertexID'].data],np.int32)
        me.calc_loop_triangles();tri=np.array([ids[list(t.vertices)] for t in me.loop_triangles])
        classes=np.array([me.attributes['SurfaceClass'].data[t.polygon_index].value for t in me.loop_triangles])
        mats={tuple(sorted(map(int,f))):me.materials[me.polygons[t.polygon_index].material_index].name for f,t in zip(tri,me.loop_triangles)}
        return dict(zip(map(int,ids),map(Vector,co))),tri,classes,mats
    finally:ev.to_mesh_clear()
co,btri,bclasses,_=evaluated(actor);hc,htri,hclasses,hmats=evaluated(display);co.update(hc)
skin=btri[np.isin(bclasses,[1,2])];hair=htri[hclasses==3]
allco=np.array([co.get(i,Vector((0,0,0)))[:] for i in range(len(actor.data.vertices))])
def hit_count(x,faces):
    ht=BVHTree.FromPolygons(x.tolist(),faces.tolist(),all_triangles=True)
    bt=BVHTree.FromPolygons(allco.tolist(),skin.tolist(),all_triangles=True)
    return sum(crosses([Vector(x[k]) for k in faces[i]],[Vector(allco[k]) for k in skin[j]]) for i,j in ht.overlap(bt))
base=ROOT.parent/'work/headswap_xl_codex';inp=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
h0=inp['head_matrix'];inv=np.linalg.inv(h0);local=inp['world']@inv[:3,:3].T+inv[:3,3]
head=np.array(actor.find_armature().matrix_world@actor.find_armature().pose.bones['頭'].matrix)
control=allco.copy();control[inp['ids']]=local@head[:3,:3].T+head[:3,3]
control_hits=hit_count(control,hair)
rest=np.load(candidate/'clump_proxy_rest.npz');physical=coords(proxy)/config.get('simulation_scale',1.)
pt=BVHTree.FromPolygons(physical.tolist(),rest['triangles'].tolist(),all_triangles=True)
bt=BVHTree.FromPolygons(allco.tolist(),skin.tolist(),all_triangles=True)
proxy_hits=sum(crosses([Vector(physical[k]) for k in rest['triangles'][i]],[Vector(allco[k]) for k in skin[j]]) for i,j in pt.overlap(bt))
vertex_gap=min(bt.find_nearest(Vector(v))[3] for v in physical)
def segment_distance_squared(a,b,c,d):
    u=b-a;v=d-c;w=a-c;aa=u.dot(u);bb=u.dot(v);cc=v.dot(v);dd=u.dot(w);ee=v.dot(w)
    denominator=aa*cc-bb*bb
    q=float(np.clip((bb*ee-cc*dd)/denominator,0,1)) if abs(denominator)>1e-30 else 0.
    r=(bb*q+ee)/cc
    if r<0:r=0.;q=float(np.clip(-dd/aa,0,1))
    elif r>1:r=1.;q=float(np.clip((bb-dd)/aa,0,1))
    delta=w+q*u-r*v;return float(delta.dot(delta))
def triangle_distance(a,b):
    av=list(map(Vector,a));bv=list(map(Vector,b))
    minimum=min((v-closest_point_on_tri(v,*bv)).length_squared for v in av)
    minimum=min(minimum,min((v-closest_point_on_tri(v,*av)).length_squared for v in bv))
    for i in range(3):
        for j in range(3):minimum=min(minimum,segment_distance_squared(a[i],a[(i+1)%3],b[j],b[(j+1)%3]))
    return float(np.sqrt(max(minimum,0.)))
proxy_triangles=physical[rest['triangles']];centers=proxy_triangles.mean(1)
radii=np.linalg.norm(proxy_triangles-centers[:,None,:],axis=2).max(1);largest=float(radii.max())
center_tree=KDTree(len(centers))
for i,v in enumerate(centers):center_tree.insert(v,i)
center_tree.balance();exact_contact_gaps=[]
for skin_ids in {tuple(map(int,w['skin_vertices'])) for w in witnesses}:
    b=np.array([co[i][:] for i in skin_ids]);center_b=b.mean(0);radius_b=np.linalg.norm(b-center_b,axis=1).max()
    best=min(pt.find_nearest(Vector(v))[3] for v in b)
    for _,j,center_distance in center_tree.find_range(center_b,radius_b+largest+best+1e-6):
        if center_distance<=radius_b+radii[j]+best+1e-6:best=min(best,triangle_distance(b,proxy_triangles[j]))
    exact_contact_gaps.append(best)
segments=[];normals=[]
for witness in witnesses:
    h=[co[int(i)] for i in witness['hair_vertices']];b=[co[int(i)] for i in witness['skin_vertices']]
    normals.append((b[1]-b[0]).cross(b[2]-b[0]).normalized());points=[]
    for first,second in [(h,b),(b,h)]:
        for i in range(3):
            start=first[i];direction=first[(i+1)%3]-start
            if direction.length_squared<1e-16:continue
            hit=intersect_ray_tri(*second,direction,start,True)
            if hit is None:continue
            t=(hit-start).dot(direction)/direction.length_squared
            if 0<=t<=1 and not any((q-hit).length<1e-6 for q in points):points.append(hit)
    if len(points)>=2:segments.append(max([(u.copy(),v.copy()) for u in points for v in points],key=lambda uv:(uv[0]-uv[1]).length))
assert segments,'No exact intersection segments found'
points=np.array([v[:] for uv in segments for v in uv]);center=Vector(points.mean(0));normal=sum(normals,Vector()).normalized()
body_contact_vertices=sorted({int(i) for w in witnesses for i in w['skin_vertices']})
report=dict(frame=frame,actual_hair_skin_crossing_pairs=row['crossings'],proxy_skin_crossing_pairs=proxy_hits,
    rigid_head_follow_control_crossing_pairs=control_hits,
    crossing_hair_materials=dict(collections.Counter(hmats[tuple(sorted(w['hair_vertices']))] for w in witnesses)),
    skin_regions=row['skin_collision_bones'],hair_bones=row['dominant_collision_bones'],
    proxy_vertex_skin_unsigned_distance_min_m=vertex_gap,
    involved_skin_vertex_to_proxy_distance_min_m=min(pt.find_nearest(co[i])[3] for i in body_contact_vertices),
    involved_skin_triangle_to_proxy_exact_distance_min_m=min(exact_contact_gaps),
    configured_proxy_body_combined_margin_real_m=config['cloth_collision_distance_m']+config['body_collision_outer_m'],
    exact_intersection_bbox_mm=(np.ptp(points,axis=0)*1000).tolist(),
    maximum_exact_intersection_segment_length_mm=max((u-v).length for u,v in segments)*1000,
    normal_full_character_image=result['normal_image'],physics_advanced=False,
    note='Triangle pairs are not separate visible holes. Exact segment extent is not penetration depth. Proxy contact and actual display contact are reported separately.')
(out/'contact_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.use_persistent_data=True
s.render.resolution_x=s.render.resolution_y=1280;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
camera=bpy.data.objects.new('DiagnosticContactCamera',bpy.data.cameras.new('DiagnosticContactCamera'));s.collection.objects.link(camera)
camera.data.type='ORTHO';s.camera=camera
def aim(point,scale):
    camera.location=point+normal*.6+Vector((0,0,.015));camera.rotation_euler=(point-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=scale
def render(name):
    if (out/name).exists():return
    s.render.filepath=str(out/name);bpy.ops.render.render(write_still=True)
mat=bpy.data.materials.new('Diagnostic_ExactIntersection');mat.use_nodes=True;mat.node_tree.nodes.clear()
em=mat.node_tree.nodes.new('ShaderNodeEmission');em.inputs['Color'].default_value=(1,.08,0,1);em.inputs['Strength'].default_value=3
shader=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(em.outputs[0],shader.inputs['Surface'])
curve=bpy.data.curves.new('ExactIntersectionLines','CURVE');curve.dimensions='3D';curve.bevel_depth=.00012;curve.bevel_resolution=2;curve.materials.append(mat)
for u,v in segments:
    spline=curve.splines.new('POLY');spline.points.add(1)
    for point,position in zip(spline.points,[u+normal*.00015,v+normal*.00015]):point.co=(*position,1.)
lines=bpy.data.objects.new('Diagnostic_ExactIntersectionLines',curve);s.collection.objects.link(lines)
# Diagnostic only: hide outer hair and show the cached intersecting triangles.
# Never save this cutaway to the project file.
display.hide_render=True
ids=sorted({int(i) for w in witnesses for i in w['hair_vertices']});lookup={i:j for j,i in enumerate(ids)}
faces=sorted({tuple(lookup[int(i)] for i in w['hair_vertices']) for w in witnesses})
mesh=bpy.data.meshes.new('Diagnostic_ActualCachedHairTriangles');mesh.from_pydata([co[i][:] for i in ids],[],faces);mesh.update()
affected=bpy.data.objects.new('Diagnostic_IntersectingHairOnly',mesh);s.collection.objects.link(affected)
red=bpy.data.materials.new('Diagnostic_RedHair');red.use_nodes=True
bsdf=red.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.8,.005,.002,1);bsdf.inputs['Roughness'].default_value=.5;mesh.materials.append(red)
headpoint=Vector(head[:3,3]);aim((center+headpoint)*.5,.4);render('diagnostic_cutaway_context.png')
aim(center,.08);render('diagnostic_cutaway_close.png')
report.update(cutaway_context=str(out/'diagnostic_cutaway_context.png'),cutaway_close=str(out/'diagnostic_cutaway_close.png'),
    cutaway_note='Diagnostic only: outer hair temporarily hidden, red triangles are the actual cached intersecting hair, orange lines mark exact intersections with a 0.15mm visibility offset. Saved native project and normal full-character image retain all hair.')
(out/'contact_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
