"""Check facial transfer, connected neck, eye follow and protected footwear."""
import sys,json,argparse,math,hashlib
from pathlib import Path
from collections import Counter,defaultdict
import bpy,bmesh,numpy as np
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine,_static_validation
from mmd_outfit.jobs import read_json,write_json
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.fit).resolve()
ie,render=engine('import_export'),engine('extraction');ie.ensure_mmd_tools();report=read_json(out/'head_swap_report.json');provenance=read_json(out/'neck_vertex_provenance.json')
bpy.ops.wm.open_mainfile(filepath=report['target'],load_ui=False,use_scripts=False)
def morph_digest(obj):
    digest=hashlib.sha256()
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            values=np.empty(len(key.data)*3,dtype=np.float32);key.data.foreach_get('co',values);digest.update(key.name.encode());digest.update(values.tobytes())
    return digest.hexdigest()
def weights(obj):return [[(obj.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in obj.data.vertices]
protected={o.name:{'co':[tuple(v.co) for v in o.data.vertices],'faces':[tuple(f.vertices) for f in o.data.polygons],'uv':{u.name:[tuple(p.uv) for p in u.data] for u in o.data.uv_layers},'matrix':o.matrix_world.copy(),'weights':weights(o),'morph_digest':morph_digest(o)} for o in ie.model_meshes() if o.get('mmd_garment')}
original_body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'))
body_prov=provenance['body'];i0=np.array([row[0][0] for row in body_prov]);w0=np.array([row[0][1] for row in body_prov])[:,None]
i1=np.array([row[1][0] if len(row)>1 else row[0][0] for row in body_prov]);w1=np.array([row[1][1] if len(row)>1 else 0. for row in body_prov])[:,None]
old_body_morphs={};relative_keys={}
for key in original_body.data.shape_keys.key_blocks:
    values=np.empty(len(key.data)*3,dtype=np.float32);key.data.foreach_get('co',values);values=values.reshape(-1,3)
    old_body_morphs[key.name]=values[i0]*w0+values[i1]*w1;relative_keys[key.name]=key.relative_key.name
bpy.ops.wm.open_mainfile(filepath=str(out/'work.blend'),load_ui=False,use_scripts=False)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'));root=ie.mmd_root(arm);original=list(bpy.data.objects)
result={'native':str(out/'work.blend'),'accepted':False,'scope':'head geometry, source expressions, neck connection and rigid head/eye follow; migrated hair physics not dynamically accepted','static_validation':_static_validation(original)}
assert not result['static_validation']['failures'],result['static_validation']['failures']
for name,old in protected.items():
    obj=bpy.data.objects[name]
    assert old['co']==[tuple(v.co) for v in obj.data.vertices],name+' changed'
    assert old['faces']==[tuple(f.vertices) for f in obj.data.polygons],name+' topology changed'
    assert old['uv']=={u.name:[tuple(p.uv) for p in u.data] for u in obj.data.uv_layers},name+' UV changed'
    assert old['matrix']==obj.matrix_world,name+' transform changed'
    assert old['weights']==weights(obj),name+' weights changed'
    assert old['morph_digest']==morph_digest(obj),name+' morph data changed'
result['protected_outfit_shoe_meshes']=len(protected)
body_error=0.
for name,expected in old_body_morphs.items():
    key=body.data.shape_keys.key_blocks[name];values=np.empty(len(key.data)*3,dtype=np.float32);key.data.foreach_get('co',values)
    body_error=max(body_error,float(np.abs(values.reshape(-1,3)[:len(body_prov)]-expected).max()))
    assert key.relative_key.name==relative_keys[name],name+' body morph basis changed'
assert body_error<5e-7,'Body morph interpolation changed'
result['preserved_body_morphs']={'keys':len(old_body_morphs),'max_coordinate_error_m':body_error}
assert not [(k.name,k.value) for k in body.data.shape_keys.key_blocks if k.name!='Basis' and abs(k.value)>1e-7],'Unexpected active expression'
assert list(body.data.uv_layers.keys())==['UVMap','UV1','UV2','UV3']
for side in ('L','R'):assert arm.pose.bones['目.'+side].mmd_bone.additional_transform_bone=='両目'
source_objects=ie.import_pmx(report['source']);source=ie.model_meshes(source_objects)[0];start=report['neck_bridge']['body_vertices'];prov=provenance['head'];basis=source.data.shape_keys.key_blocks[0]
scale=report['scale'];maximum=0.;checked=0
for key in source.data.shape_keys.key_blocks[1:]:
    transferred=body.data.shape_keys.key_blocks.get(key.name);assert transferred is not None,key.name
    for k,weights in enumerate(prov):
        expected=sum(((key.data[i].co-basis.data[i].co)*(scale*w) for i,w in weights),Vector())
        actual=transferred.data[start+k].co-body.data.shape_keys.key_blocks[0].data[start+k].co
        maximum=max(maximum,(actual-expected).length)
    checked+=1
assert maximum<6e-7,'Source facial morph deltas changed: '+str(maximum)
result['source_expressions']={'checked':checked,'max_transfer_error_m':maximum}
for obj in source_objects:bpy.data.objects.remove(obj,do_unlink=True)
bridge_count=report['neck_bridge']['bridge_faces'];bridge_faces=list(body.data.polygons)[-bridge_count:]
geometric_edges=Counter()
for f in body.data.polygons:
    for j,i in enumerate(f.vertices):
        k=f.vertices[(j+1)%len(f.vertices)]
        edge=tuple(sorted((tuple(round(c,6) for c in body.data.vertices[i].co),tuple(round(c,6) for c in body.data.vertices[k].co))))
        geometric_edges[edge]+=1
bridge_edges={tuple(sorted((tuple(round(c,6) for c in body.data.vertices[i].co),tuple(round(c,6) for c in body.data.vertices[f.vertices[(j+1)%len(f.vertices)]].co)))) for f in bridge_faces for j,i in enumerate(f.vertices)}
bad=[(e,geometric_edges[e]) for e in bridge_edges if geometric_edges[e]!=2]
assert not bad,'Open or non-manifold neck bridge edges: '+repr(bad[:4])
result['neck_bridge']={'faces':bridge_count,'edges':len(bridge_edges),'all_edge_valences_two':True}
groups=defaultdict(list)
for v in body.data.vertices:
    if 1.315<v.co.z<1.365:groups[tuple(round(c,6) for c in v.co)].append(v.index)
seams=[ids for ids in groups.values() if len(ids)>1]
face_ids={i for f in body.data.polygons if body.data.materials[f.material_index].mmd_material.name_j=='面' for i in f.vertices}
eye_ids={i for f in body.data.polygons if body.data.materials[f.material_index].mmd_material.name_j=='目' for i in f.vertices}
scene=bpy.context.scene;render._setup_render(scene,1000,1000);render._setup_lights(scene)
data=bpy.data.cameras.new('HeadMotionReview');data.type='ORTHO';data.ortho_scale=.44
camera=bpy.data.objects.new('HeadMotionReview',data);scene.collection.objects.link(camera);scene.camera=camera;center=Vector((0,.015,1.41))
camera.location=center+Vector((.9,-3,.01));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
def rotate(name,axis,degrees):
    bone=arm.pose.bones[name];rotation=bone.bone.matrix_local.to_3x3();bone.rotation_mode='QUATERNION'
    bone.rotation_quaternion=(rotation.inverted()@Matrix.Rotation(math.radians(degrees),3,axis)@rotation).to_quaternion()
shots=[]
for label,head_axis,head_angle,neck_angle in [('neutral','Z',0,0),('head_left','Z',30,0),('head_right','Z',-30,0),('look_down','X',20,0),('neck_tilt','Z',15,15)]:
    for name in ('頭','首','両目'):arm.pose.bones[name].matrix_basis=Matrix.Identity(4)
    rotate('頭',head_axis,head_angle);rotate('首','X',neck_angle);bpy.context.view_layer.update()
    evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh()
    motion=arm.pose.bones['頭'].matrix@arm.data.bones['頭'].matrix_local.inverted()
    face_error=max((me.vertices[i].co-motion@body.data.vertices[i].co).length for i in face_ids)
    eye_error=max((me.vertices[i].co-motion@body.data.vertices[i].co).length for i in eye_ids)
    gap=max((max((me.vertices[i].co-me.vertices[j].co).length for i in ids for j in ids) for ids in seams),default=0.)
    assert face_error<3e-6 and eye_error<3e-6,(label,face_error,eye_error)
    assert gap<2e-5,(label,'neck seam split',gap)
    shots.append({'pose':label,'rigid_face_error_m':face_error,'eye_follow_error_m':eye_error,'max_neck_coincident_gap_m':gap})
    evaluated.to_mesh_clear();scene.render.filepath=str(out/f'pose_{label}.png');bpy.ops.render.render(write_still=True)
for name in ('頭','首','両目'):arm.pose.bones[name].matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update();result['poses']=shots
for key in body.data.shape_keys.key_blocks:key.value=0.
# Isolate the face/neck to inspect the actual seam that the collar covers.
allowed={'Body','肌','Keqing_NeckBlend','面','面1','白目','目','睫','二重','眉','口舌','目星','照れ'}
mesh=bpy.data.meshes.new_from_object(body.evaluated_get(bpy.context.evaluated_depsgraph_get()),preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
bm=bmesh.new();bm.from_mesh(mesh)
bmesh.ops.delete(bm,geom=[f for f in bm.faces if mesh.materials[f.material_index].mmd_material.name_j not in allowed or min(v.co.z for v in f.verts)<1.285],context='FACES')
bm.to_mesh(mesh);bm.free();copy=bpy.data.objects.new('NeckSeamDiagnostic',mesh);scene.collection.objects.link(copy)
for obj in bpy.data.objects:
    if obj.type=='MESH':obj.hide_render=obj!=copy
data.ortho_scale=.29;center=Vector((0,.025,1.39))
for name,direction in [('front',(0,-1,0)),('side',(1,0,0)),('back',(0,1,0))]:
    camera.location=center+Vector(direction)*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/f'neck_{name}.png');bpy.ops.render.render(write_still=True)
    solid=bpy.data.materials.get('NeckSolidDiagnostic') or bpy.data.materials.new('NeckSolidDiagnostic')
    solid.diffuse_color=(.6,.6,.6,1)
    bpy.context.view_layer.material_override=solid
    scene.render.filepath=str(out/f'neck_{name}_solid.png');bpy.ops.render.render(write_still=True)
    bpy.context.view_layer.material_override=None
write_json(out/'head_verification.json',result)
print('HEAD_SWAP_VERIFIED',json.dumps({k:v for k,v in result.items() if k!='static_validation'},ensure_ascii=False),flush=True)
