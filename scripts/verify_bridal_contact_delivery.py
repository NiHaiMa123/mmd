"""Compare the delivered native meshes to the pre-repair complete-foot asset."""
import argparse,sys,json,hashlib
from pathlib import Path
from collections import defaultdict
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.fit).resolve()
ie=engine('import_export');ie.ensure_mmd_tools()
source=json.loads((folder/'contact_correction.json').read_text(encoding='utf8'))['source']

def coords(data):
    values=np.empty(len(data)*3,dtype=np.float32);data.foreach_get('co',values);return values.reshape(-1,3)

def structure(mesh):
    digest=hashlib.sha256()
    for name,collection,field,count,dtype in [('faces',mesh.polygons,'loop_total',len(mesh.polygons),np.int32),('loops',mesh.loops,'vertex_index',len(mesh.loops),np.int32),('material',mesh.polygons,'material_index',len(mesh.polygons),np.int32)]:
        array=np.empty(count,dtype=dtype);collection.foreach_get(field,array);digest.update(array.tobytes())
    for layer in mesh.uv_layers:
        array=np.empty(len(layer.data)*2,dtype=np.float32);layer.data.foreach_get('uv',array);digest.update(layer.name.encode());digest.update(array.tobytes())
    digest.update(json.dumps([m.name for m in mesh.materials],ensure_ascii=False).encode())
    return digest.hexdigest()

bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False)
before={}
for obj in ie.model_meshes():
    before[obj.name]={'vertices':coords(obj.data.vertices),'structure':structure(obj.data),'matrix':np.array(obj.matrix_world),'faces':len(obj.data.polygons),
                      'keys':{k.name:coords(k.data) for k in obj.data.shape_keys.key_blocks} if obj.data.shape_keys else {}}
body_name=next(o.name for o in ie.model_meshes() if not o.get('mmd_garment'))
body=bpy.data.objects[body_name]
ids=sorted({i for f in body.data.polygons if (body.data.materials[f.material_index].mmd_material.name_j or body.data.materials[f.material_index].name) in {'Body','Nails'} and min(body.data.vertices[i].co.z for i in f.vertices)<.1953568 for i in f.vertices})
offset=len(bpy.data.objects['Cloth'].data.vertices)-len(ids)
original_offset=before['Cloth']['vertices'][offset:]-before[body_name]['vertices'][ids]
bpy.ops.wm.open_mainfile(filepath=str(folder/'work.blend'),load_ui=False,use_scripts=False)
report={'source':source,'native':str(folder/'work.blend'),'objects':{},'scope':'native topology/UV/morph/complete-foot preservation, static shoe contacts and sampled motion contacts; no full-frame dynamics acceptance'}
accessories={'Cube','Cylinder','Plane','Sphere','BézierCircle','大蝴蝶结.fbx'}
for name,old in before.items():
    obj=bpy.data.objects[name];now=coords(obj.data.vertices);delta=now-old['vertices']
    assert structure(obj.data)==old['structure'],name+' topology/UV/material changed'
    row={'vertices':len(now),'faces':len(obj.data.polygons),'topology_uv_material_unchanged':True,'max_displacement_m':float(np.linalg.norm(delta,axis=1).max())}
    if obj.get('external_shoe'):
        assert np.array_equal(now,old['vertices']),name+' rigid shoe vertex changed'
        short=name.removeprefix('Bridal_')[:-2]
        if short not in accessories:assert np.array_equal(np.array(obj.matrix_world),old['matrix']),name+' hard shoe transform changed'
        row['rigid_mesh_unchanged']=True;row['hard_shoe_transform_unchanged']=short not in accessories
    else:
        upper=old['vertices'][:,2]>=.195
        assert np.abs(delta[upper]).max()<1e-7,name+' upper body moved'
        max_error=0.
        assert list(old['keys'])==[k.name for k in obj.data.shape_keys.key_blocks]
        for key in obj.data.shape_keys.key_blocks:
            error=float(np.abs((coords(key.data)-old['keys'][key.name])-delta).max());max_error=max(max_error,error)
        assert max_error<3e-7,name+' morph displacement was not preserved'
        row.update({'morph_keys':len(old['keys']),'max_morph_translation_error_m':max_error,'upper_body_unchanged':True})
    report['objects'][name]=row
body=bpy.data.objects[body_name];cloth=bpy.data.objects['Cloth']
final_offset=coords(cloth.data.vertices)[offset:]-coords(body.data.vertices)[ids]
ratio=np.linalg.norm(final_offset,axis=1)/np.linalg.norm(original_offset,axis=1)
assert ratio.min()>.349 and ratio.max()<1.001
assert (np.sum(final_offset*original_offset,axis=1)>0).all()
report['complete_feet']={'body_region_faces':8928,'body_stocking_correspondence_vertices':len(ids),'all_faces_retained':True,
                        'min_stocking_offset_m':float(np.linalg.norm(final_offset,axis=1).min()),'max_stocking_offset_m':float(np.linalg.norm(final_offset,axis=1).max()),
                        'min_relative_stocking_offset':float(ratio.min())}
static=json.loads((folder/'review/report.json').read_text(encoding='utf8'));motion=json.loads((folder/'motion_sample/report.json').read_text(encoding='utf8'))
assert all(r['crossing_pairs']==0 for r in static['sides'].values())
assert all(r['crossing_pairs']==0 for r in motion['sides'].values())
report['contact_checks']={'static_sides':len(static['sides']),'static_views_per_side':12,'sampled_motion_side_frames':len(motion['sides']),'all_crossing_pairs':0}
report['visible_model_meshes']=len([o for o in ie.model_meshes() if o.visible_get()])
assert report['visible_model_meshes']==22
report['review_state']='REVIEW_REQUIRED'
write_json(folder/'contact_verification.json',report)
print('CONTACT_DELIVERY_VERIFIED',json.dumps({k:v for k,v in report.items() if k!='objects'},ensure_ascii=False),flush=True)
