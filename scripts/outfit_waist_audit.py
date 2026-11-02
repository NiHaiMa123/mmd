"""Identify the dark waist band and genuine garment boundaries before fitting."""
import argparse
from collections import Counter
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
parser=argparse.ArgumentParser(); parser.add_argument('--job',required=True); parser.add_argument('--out',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
job=Path(args.job); result=read_json(job/'result.json')
ie,qa,motion,dressing=[engine(n) for n in ('import_export','qa','motion','dressing')]
bpy.ops.wm.open_mainfile(filepath=result['blend'])
meshes=ie.model_meshes(); cloth=next(o for o in meshes if o.get('mmd_garment')); body=next(o for o in meshes if o is not cloth)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
landmarks={n:list(arm.data.bones[n].head_local) for n in ('下半身','上半身','上半身2','首')}
bpy.context.view_layer.update()
trees=[]
pixels={}
def alpha_at(obj,me,fi,point):
    face=me.polygons[fi]; material=obj.data.materials[face.material_index]
    node=material.node_tree.nodes.get('mmd_base_tex') if material.use_nodes else None
    uv=me.uv_layers.active
    if node is None or node.image is None or uv is None:
        return 1.
    image=node.image
    if image.name not in pixels:
        w,h=image.size; values=np.empty(w*h*4,dtype=np.float32); image.pixels.foreach_get(values)
        pixels[image.name]=values.reshape(h,w,4)[:,:,3]
    image_alpha=pixels[image.name]; h,w=image_alpha.shape
    coords=[Vector((*uv.data[i].uv,0)) for i in face.loop_indices]
    mapped=barycentric_transform(point,*(me.vertices[i].co for i in face.vertices),*coords)
    return float(image_alpha[int(mapped.y*h)%h,int(mapped.x*w)%w])
for obj in (body,cloth):
    me,owner=qa._evaluated_mesh_copy(obj)
    faces=list(range(len(me.polygons)))
    if obj is cloth: faces,_=engine('visibility').visible_garment_faces(obj,faces)
    trees.append((obj,me,faces,motion._bvh_from(me,faces)))
rows=[]
for z in [i/1000 for i in range(780,1051,5)]:
    samples=[]
    for x in [i/1000 for i in range(-120,121,10)]:
        origin=Vector((x,-3,z)); hits=[]
        for obj,me,faces,tree in trees:
            cursor=origin.copy()
            for attempt in range(32):
                loc,norm,fi,distance=tree.ray_cast(cursor,Vector((0,1,0)))
                if loc is None: break
                face=me.polygons[faces[fi]]
                if alpha_at(obj,me,faces[fi],loc)>.95:
                    hits.append(((loc-origin).length,obj.data.materials[face.material_index].name)); break
                cursor=loc+Vector((0,.00001,0))
        samples.append(min(hits)[1] if hits else '-')
    rows.append({'z':z,'materials':samples,'counts':dict(Counter(samples))})
dominant=dressing.dominant_bones(cloth)
boundaries={}
for material in ('服','服+jinshu','裙'):
    faces=[f for f in cloth.data.polygons if cloth.data.materials[f.material_index].name==material and
           sum(dominant[i].split('.')[0].startswith(('下半身','上半身','腰')) for i in f.vertices)>=2]
    edge_count=Counter(tuple(sorted((a,b))) for face in faces for a,b in zip(face.vertices,(*face.vertices[1:],face.vertices[0])))
    ids={i for edge,count in edge_count.items() if count==1 for i in edge}
    boundaries[material]={'faces':len(faces),'vertices':[{'vertex':i,'position':list(cloth.data.vertices[i].co),'bone':dominant[i]} for i in sorted(ids)]}
out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
write_json(out/'report.json',{'landmarks':landmarks,'rows':rows,'boundaries':boundaries,'scope':'nearest base-alpha-opaque hit; coarse grid for diagnosis'})
for obj,me,faces,tree in trees: bpy.data.meshes.remove(me)
print('WAIST_AUDIT',landmarks,[(r['z'],r['counts']) for r in rows],flush=True)
