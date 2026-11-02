"""Read-only native normal/x-ray stills locating the reported frame-211 contact.

Normal material geometry stays unchanged. Diagnostic skin transparency and
small point markers are applied only to a temporary render duplicate.
"""
import argparse,json,sys,numpy as np
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run);out=run/'contact_locations';out.mkdir(exist_ok=True)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(run/'完整角色_失败现场_仅1至7秒.blend'),load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(211);bpy.context.view_layer.update();actor=bpy.data.objects['东雪莲x达妮娅_素体'];co=coords(actor);originalcam=s.camera
base=repo.parent/'work/headswap_xl_codex';d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));measured=np.load(run/'full_measure/frame_211_signed_distances.npz');assert np.array_equal(d['ids'],measured['hair_ids'])
distance=measured['vertex_signed_distance_m'];exp=base/'fullhair_repro_20261030/input_body_aware';skinids=np.load(exp/'skin_ids.npy');bf=np.load(exp/'body_faces.npy');real=np.load(exp/'real_body_faces.npy').astype(bool);real_indices=np.flatnonzero(real)
bodytree=BVHTree.FromPolygons(co[skinids].tolist(),bf[real].tolist(),all_triangles=True)
rows=[]
for label in [23,24]:
 candidates=np.flatnonzero((d['chain_labels']==label)&(distance<-.0001));ii=int(candidates[np.argmin(distance[candidates])]);vi=int(d['ids'][ii]);point=co[vi]
 nearest,normal,fi,dd=bodytree.find_nearest(Vector(point));uv=world_to_camera_view(s,originalcam,Vector(point));pixel=[float(uv.x*1920),float((1-uv.y)*1080)]
 delta=Vector(point)-originalcam.matrix_world.translation;hit,_,_,hitdist=bodytree.ray_cast(originalcam.matrix_world.translation,delta.normalized(),delta.length)
 occluded=hit is not None and hitdist<delta.length-.0001
 triangle=skinids[bf[real_indices[fi]]];weights={}
 for v in triangle:
  for g in actor.data.vertices[int(v)].groups:weights[actor.vertex_groups[g.group].name]=weights.get(actor.vertex_groups[g.group].name,0)+g.weight
 rows.append(dict(chain=meta['chains'][label]['name'],deepest_source_vertex=vi,inside_source_vertices=d['ids'][candidates].tolist(),depth_to_closed_body_m=float(-distance[ii]),distance_to_actual_visible_skin_m=float(dd),nearest_actual_skin_triangle=triangle.tolist(),nearest_skin_dominant_bones=sorted(weights.items(),key=lambda q:-q[1])[:4],world=point.tolist(),surface=list(nearest),normal=list(normal),full_frame_pixel=pixel,occluded_by_skin_from_original_camera=bool(occluded),buried_points=co[d['ids'][candidates]].tolist()))
(out/'locations.json').write_text(json.dumps(dict(frame=211,original_seconds=7,rows=rows,normal_geometry_unchanged=True,new_simulation=False),ensure_ascii=False,indent=2),'utf8')
print('CONTACT_LOCATIONS',json.dumps(rows,ensure_ascii=False),flush=True)
# Freeze an evaluated copy for x-ray material display, with identical shape.
ev=actor.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());xray=bpy.data.objects.new('DiagnosticOnly_TransparentSkin',mesh);s.collection.objects.link(xray);xray.matrix_world=actor.matrix_world.copy();xray.hide_render=True
assert np.max(np.abs(coords(xray)-co))<5e-6
classes=mesh.attributes['SurfaceClass'];transparent={}
for poly in mesh.polygons:
 if classes.data[poly.index].value not in [1,2]:continue
 index=poly.material_index
 if index not in transparent:
  mat=mesh.materials[index].copy();mat.name+='__DiagnosticSkinTransparency';mat.use_nodes=True;nodes=mat.node_tree.nodes;links=mat.node_tree.links;output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output);old=output.inputs['Surface'].links[0].from_socket
  trans=nodes.new('ShaderNodeBsdfTransparent');mix=nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.78;links.new(old,mix.inputs[1]);links.new(trans.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],output.inputs['Surface']);transparent[index]=len(mesh.materials);mesh.materials.append(mat)
 poly.material_index=transparent[index]
markmat=bpy.data.materials.new('Diagnostic_InsidePoints');markmat.use_nodes=True;n=markmat.node_tree.nodes;n.clear();em=n.new('ShaderNodeEmission');em.inputs[0].default_value=(1,.005,.01,1);em.inputs[1].default_value=2;output=n.new('ShaderNodeOutputMaterial');markmat.node_tree.links.new(em.outputs[0],output.inputs['Surface'])
markers=[]
for row in rows:
 for point in row['buried_points']:
  bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=.00065,location=point);ob=bpy.context.object;ob.name='DiagnosticOnly_BuriedVertex';ob.data.materials.append(markmat);ob.hide_render=True;markers.append(ob)
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=48;s.cycles.use_denoising=True;s.cycles.transparent_max_bounces=16;s.render.use_persistent_data=True;s.render.resolution_x=1400;s.render.resolution_y=1000;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.use_sequencer=False
for i,row in enumerate(rows,1):
 point=Vector(row['world']);surface=Vector(row['surface']);normal=Vector(row['normal']).normalized();up=Vector((0,0,1));centre=(point+surface)*.5+up*.015
 # Look slightly along the skin so the relation to neck/upper chest is clear.
 toward=originalcam.matrix_world.translation-centre;tangent=normal.cross(up).normalized()
 if tangent.dot(toward)<0:tangent=-tangent
 direction=(normal*.8+tangent*.6+up*.18).normalized()
 camdata=bpy.data.cameras.new('ContactCloseup');cam=bpy.data.objects.new('ContactCloseup',camdata);s.collection.objects.link(cam);cam.location=centre+direction*.65;cam.rotation_euler=(centre-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=.19;camdata.clip_start=.001;s.camera=cam;bpy.context.view_layer.update()
 row['closeup_pixels']={}
 for key in ['world','surface']:
  uv=world_to_camera_view(s,cam,Vector(row[key]));row['closeup_pixels'][key]=[float(uv.x*1400),float((1-uv.y)*1000)]
 actor.hide_render=False;xray.hide_render=True
 for ob in markers:ob.hide_render=True
 s.render.filepath=str(out/f'{i}_normal.png');bpy.ops.render.render(write_still=True)
 actor.hide_render=True;xray.hide_render=False
 for ob in markers:ob.hide_render=False
 s.render.filepath=str(out/f'{i}_xray.png');bpy.ops.render.render(write_still=True)
 actor.hide_render=False;xray.hide_render=True
 for ob in markers:ob.hide_render=True
(out/'locations.json').write_text(json.dumps(dict(frame=211,original_seconds=7,rows=rows,normal_geometry_unchanged=True,new_simulation=False,diagnostic_skin_transparency=.78,red_markers='Inside hair vertices; markers do not move hair'),ensure_ascii=False,indent=2),'utf8')
print('CONTACT_LOCATION_RENDERS_COMPLETE',flush=True)
