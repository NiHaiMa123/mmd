"""Repair display normals and show cached contacts. Never run new physics."""
import json,sys,shutil
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Matrix
from mathutils.geometry import intersect_ray_tri
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
base=ROOT.parent/'work/headswap_xl_codex';p=base/'standard_proxy_20261031/clumps07';out=p/'appearance_review';out.mkdir(exist_ok=True)
engine('import_export').ensure_mmd_tools()
source=base/'jiggle_physics_20261031/candidate10/完整角色_Jiggle配置_未烘焙.blend'
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False,load_ui=False);s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
actor=bpy.data.objects['东雪莲x达妮娅_素体'];ev=actor.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();normalmatrix=ev.matrix_world.inverted().transposed().to_3x3();normals={}
mesh.calc_loop_triangles();hair_tri_material={tuple(sorted(t.vertices)):mesh.materials[mesh.polygons[t.polygon_index].material_index].name for t in mesh.loop_triangles if mesh.attributes['SurfaceClass'].data[t.polygon_index].value==3}
for polygon in mesh.polygons:
    if mesh.attributes['SurfaceClass'].data[polygon.index].value!=3:continue
    face=tuple(sorted(polygon.vertices))
    for li in polygon.loop_indices:normals[(face,int(mesh.loops[li].vertex_index))]=(normalmatrix@mesh.corner_normals[li].vector).normalized().copy()
ev.to_mesh_clear()
candidate=p/'完整角色_原生分束代理_连续物理待验收.blend';bpy.ops.wm.open_mainfile(filepath=str(candidate),use_scripts=False,load_ui=False);s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
actor=bpy.data.objects['东雪莲x达妮娅_素体'];display=bpy.data.objects[s['HairDisplayObject']];proxy=bpy.data.objects['HairProxy_27束连续笼体'];cloth=next(md for md in proxy.modifiers if md.type=='CLOTH');assert cloth.point_cache.is_baked and cloth.point_cache.frame_end==2
ids=np.array([x.value for x in display.data.attributes['SourceVertexID'].data]);inverse_normal=display.matrix_world.transposed().to_3x3();localnormals=[None]*len(display.data.loops);expected=[]
for polygon in display.data.polygons:
    face=tuple(sorted(int(ids[i]) for i in polygon.vertices))
    for li in polygon.loop_indices:
        key=(face,int(ids[display.data.loops[li].vertex_index]));normal=normals[key];localnormals[li]=(inverse_normal@normal).normalized();expected.append((li,normal))
before=np.array([v.co[:] for v in display.data.vertices]);free_normals=display.data.attributes.get('custom_normal')
if free_normals is not None and free_normals.data_type=='FLOAT_VECTOR':
    values=np.empty(len(free_normals.data)*3,np.float32);free_normals.data.foreach_get('vector',values);values=values.reshape(-1,3)
    transform=np.array(inverse_normal@normalmatrix);values=values@transform.T;free_normals.data.foreach_set('vector',values.astype(np.float32).ravel())
else:display.data.normals_split_custom_set(localnormals)
display.data.update();display.data.update_tag();display.update_tag(refresh={'DATA'});s.frame_set(1);bpy.context.view_layer.update();assert np.array_equal(before,np.array([v.co[:] for v in display.data.vertices]))
raw_angles=[];rawlocal=[]
for li,target in expected:
    v=(display.matrix_world.inverted().transposed().to_3x3()@display.data.corner_normals[li].vector).normalized()
    if v.length>1e-8 and target.length>1e-8:raw_angles.append(float(v.angle(target)))
    given=Vector(localnormals[li]);got=display.data.corner_normals[li].vector
    if given.length>1e-8 and got.length>1e-8:rawlocal.append(float(given.angle(got)))
print('RAW_NORMAL_PROBE',json.dumps(dict(raw_p50=float(np.degrees(np.median(raw_angles))),raw_p95=float(np.degrees(np.quantile(raw_angles,.95))),set_vs_get_p50=float(np.degrees(np.median(rawlocal))),matrix=[list(r) for r in display.matrix_world],first_expected=tuple(expected[0][1]),first_set=tuple(localnormals[0]),first_get=tuple(display.data.corner_normals[0].vector))),flush=True)
ev=display.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();nm=ev.matrix_world.inverted().transposed().to_3x3();angles=[]
zero_normals=0
for li,target in expected:
    current=(nm@mesh.corner_normals[li].vector).normalized()
    if current.length<1e-8 or target.length<1e-8:zero_normals+=1;continue
    angles.append(float(current.angle(target)))
ev.to_mesh_clear();report=dict(repaired_custom_corner_normals=len(localnormals),undefined_degenerate_corner_normals=zero_normals,first_frame_normal_angle_error_p50_degrees=float(np.degrees(np.median(angles))),first_frame_normal_angle_error_p95_degrees=float(np.degrees(np.quantile(angles,.95))),first_frame_normal_angle_error_max_degrees=float(np.degrees(max(angles))),geometry_unchanged=True,new_physics_run=False)
(out/'normal_fix_probe.json').write_text(json.dumps(report,indent=2),'utf8');assert np.quantile(angles,.95)<.002,report
fixed=out/'corrected';fixed.mkdir(exist_ok=True);cache_name='blendcache_'+candidate.stem;shutil.copytree(p/cache_name,fixed/cache_name,dirs_exist_ok=True)
fixed_blend=fixed/candidate.name;bpy.ops.wm.save_as_mainfile(filepath=str(fixed_blend));report['corrected_appearance_blend']=str(fixed_blend)
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.image_settings.file_format='PNG';s.render.resolution_percentage=100;s.render.resolution_x=1920;s.render.resolution_y=1080
s.frame_set(2);bpy.context.view_layer.update();assert cloth.point_cache.is_baked
def render(name):
    if (out/name).exists():return
    s.render.filepath=str(out/name);bpy.ops.render.render(write_still=True);print('CONTACT_REVIEW_RENDER',s.render.filepath,flush=True)
render('corrected_full_f0002.png')
def evaluated(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();world=ev.matrix_world.copy();result={int(i.value):world@v.co for i,v in zip(mesh.attributes['SourceVertexID'].data,mesh.vertices)};ev.to_mesh_clear();return result
co=evaluated(actor);co.update(evaluated(display));witnesses=json.loads((p/'audit_stopped/surface_audit.json').read_text('utf8'))['rows'][1]['witnesses'];segments=[];depths=[];skin_normals=[]
from collections import Counter
report['intersecting_hair_materials']=dict(Counter(hair_tri_material[tuple(sorted(w['hair_vertices']))] for w in witnesses))
for witness in witnesses:
    h=[co[int(i)] for i in witness['hair_vertices']];b=[co[int(i)] for i in witness['skin_vertices']];points=[];normal=(b[1]-b[0]).cross(b[2]-b[0]).normalized();skin_normals.append(normal)
    depths.append(max(0.,-min((q-b[0]).dot(normal) for q in h)))
    for first,second in ((h,b),(b,h)):
        for j in range(3):
            start=first[j];direction=first[(j+1)%3]-start
            if direction.length_squared<1e-16:continue
            hit=intersect_ray_tri(*second,direction,start,True)
            if hit is None:continue
            t=(hit-start).dot(direction)/direction.length_squared
            if 0<=t<=1 and not any((q-hit).length<1e-6 for q in points):points.append(hit)
    if len(points)>1:
        a,b=max(((a,b) for a in points for b in points),key=lambda pair:(pair[0]-pair[1]).length);segments.append((a.copy(),b.copy()))
allpoints=np.array([list(v) for pair in segments for v in pair]);center=Vector(allpoints.mean(0));normal=sum(skin_normals,Vector()).normalized();report.update(intersecting_triangle_pairs=len(witnesses),intersection_segment_count=len(segments),intersection_bbox_mm=(np.ptp(allpoints,axis=0)*1000).tolist(),max_intersection_segment_length_mm=max((a-b).length for a,b in segments)*1000,max_depth_below_local_intersected_skin_triangle_plane_mm=max(depths)*1000,depth_metric='Signed distance of hair triangle vertices below intersected local skin triangle plane; not global nearest-surface penetration depth')
cam=bpy.data.objects.new('ReviewCamera',bpy.data.cameras.new('ReviewCamera'));s.collection.objects.link(cam);cam.data.type='ORTHO';s.camera=cam
def aim(target,offset,scale):
    cam.location=target+offset;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
head=actor.find_armature().matrix_world@actor.find_armature().pose.bones['頭'].head
aim((center+head)*.5,normal*.8+Vector((0,0,.04)),.40);s.render.resolution_x=1280;s.render.resolution_y=1280;render('corrected_head_shoulders_f0002.png')
aim(center,normal*.5+Vector((0,0,.02)),.10);render('contact_close_normal_f0002.png')
mat=bpy.data.materials.new('DiagnosticIntersectionLine');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();em=nodes.new('ShaderNodeEmission');em.inputs['Color'].default_value=(1,.015,.001,1);em.inputs['Strength'].default_value=3.;output=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(em.outputs[0],output.inputs['Surface'])
curve=bpy.data.curves.new('ExactTriangleIntersectionSegments','CURVE');curve.dimensions='3D';curve.bevel_depth=.00015;curve.bevel_resolution=2
for a,b in segments:
    spline=curve.splines.new('POLY');spline.points.add(1)
    for point,coo in zip(spline.points,[a+normal*.0002,b+normal*.0002]):point.co=(*coo,1.)
obj=bpy.data.objects.new('Diagnostic_ExactIntersections',curve);s.collection.objects.link(obj);curve.materials.append(mat);render('contact_close_marked_f0002.png')
# The normal views are occluded by the outer hair. This explicitly labelled
# diagnostic cutaway hides only that outer display and shows the real cached
# intersecting hair triangles, the original skin and exact intersection lines.
display.hide_render=True
hair_ids=sorted({int(i) for w in witnesses for i in w['hair_vertices']});lookup={i:j for j,i in enumerate(hair_ids)}
faces=sorted({tuple(lookup[int(i)] for i in w['hair_vertices']) for w in witnesses})
data=bpy.data.meshes.new('DiagnosticActualHairTriangles');data.from_pydata([co[i][:] for i in hair_ids],[],faces);data.update()
affected=bpy.data.objects.new('Diagnostic_OnlyActualIntersectingHairTriangles',data);s.collection.objects.link(affected)
red=bpy.data.materials.new('DiagnosticHairRed');red.diffuse_color=(.8,.01,.005,1);red.use_nodes=True;red.node_tree.nodes.clear();principled=red.node_tree.nodes.new('ShaderNodeBsdfPrincipled');principled.inputs['Base Color'].default_value=(.8,.01,.005,1);principled.inputs['Roughness'].default_value=.5;surface=red.node_tree.nodes.new('ShaderNodeOutputMaterial');red.node_tree.links.new(principled.outputs['BSDF'],surface.inputs['Surface']);data.materials.append(red)
aim((center+head)*.5,normal*.8+Vector((0,0,.04)),.40);render('contact_cutaway_context_f0002.png')
aim(center,normal*.5+Vector((0,0,.02)),.10);render('contact_cutaway_close_f0002.png')
report['cutaway_note']='Diagnostic only: outer render hair temporarily hidden; red is the actual cached intersecting hair triangles, orange lines are exact triangle intersections. Corrected normal full-character render and saved blend keep all hair visible.'
(out/'color_contact_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('COLOR_CONTACT_REVIEW',json.dumps(report,ensure_ascii=False),flush=True)
