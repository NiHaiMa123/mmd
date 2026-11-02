"""Ray audit of the glove closeup: separate missing alpha from shell crossing."""
import argparse
from collections import Counter
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform
from mathutils.kdtree import KDTree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json

parser=argparse.ArgumentParser()
parser.add_argument('--job',required=True)
parser.add_argument('--out',required=True)
parser.add_argument('--frame',type=int,default=61)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
job=Path(args.job)
result,request=read_json(job/'result.json'),read_json(job/'request.json')
ie,qa,motion,dressing=[engine(n) for n in ('import_export','qa','motion','dressing')]
ie.clear_scene()
objects=ie.import_pmx(result['pmx'])
mesh=ie.model_meshes(objects)[0]
arm=next(o for o in objects if o.type=='ARMATURE')
dominant=dressing.dominant_bones(mesh)
cloth_ids={i for face in mesh.data.polygons if mesh.data.materials[face.material_index].name=='服' for i in face.vertices}
tree=KDTree(len(cloth_ids))
for i in cloth_ids:
    tree.insert(mesh.data.vertices[i].co,i)
tree.balance()
def weights(i):
    return {mesh.vertex_groups[g.group].name:round(g.weight,5) for g in mesh.data.vertices[i].groups
            if g.weight>1e-6 and not mesh.vertex_groups[g.group].name.startswith('mmd_')}
pair_data={}
skin_ids={i for face in mesh.data.polygons if mesh.data.materials[face.material_index].name=='Body' for i in face.vertices}
for i in skin_ids:
    if not dominant[i][:-2].startswith(('手首','親指','人指','中指','薬指','小指')):
        continue
    v=mesh.data.vertices[i]
    candidates=sorted(tree.find_range(v.co,.005),key=lambda x:x[2])
    same=[(p,j,d) for p,j,d in candidates if weights(j)==weights(i)]
    if same:
        p,j,d=same[0]
        delta=p-v.co
        pair_data[i]={'cloth_vertex':j,'rest_delta':list(delta),'rest_dot':delta.dot(v.normal),'weights':weights(i)}
arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.mmd_tools.import_vmd(filepath=result.get('effective_motion') or request['motion'],scale=.08,rename_bones=True,log_level='ERROR')
bpy.context.scene.frame_set(args.frame)
bpy.context.view_layer.update()
me,owner=qa._evaluated_mesh(mesh)
uv=next(layer for layer in me.uv_layers if layer.active_render)
image_cache={}
def opacity(fi,point):
    face=me.polygons[fi]; material=me.materials[face.material_index]
    base=material.node_tree.nodes.get('mmd_base_tex') if material.use_nodes else None
    if base is None or base.image is None:
        return 1.,None
    img=base.image
    if img.name not in image_cache:
        w,h=img.size; data=np.empty(w*h*4,dtype=np.float32); img.pixels.foreach_get(data)
        image_cache[img.name]=data.reshape(h,w,4)[:,:,3]
    alpha=image_cache[img.name]; h,w=alpha.shape
    coords=[Vector((*uv.data[i].uv,0)) for i in face.loop_indices]
    mapped=barycentric_transform(point,*(me.vertices[i].co for i in face.vertices),*coords)
    x,y=mapped.x*w-.5,mapped.y*h-.5
    ix,iy=int(np.floor(x)),int(np.floor(y)); fx,fy=x-ix,y-iy
    value=sum(alpha[(iy+dy)%h,(ix+dx)%w]*(fx if dx else 1-fx)*(fy if dy else 1-fy)
              for dx in (0,1) for dy in (0,1))
    return float(value),list(mapped.xy)

reports=[]
for i,row in pair_data.items():
    row['posed_delta']=list(me.vertices[row['cloth_vertex']].co-me.vertices[i].co)
    row['posed_dot']=(me.vertices[row['cloth_vertex']].co-me.vertices[i].co).dot(me.vertices[i].normal)
for side in ('L','R'):
    allowed={i for i,n in enumerate(dominant) if n.endswith('.'+side) and n[:-2].startswith(('手首','親指','人指','中指','薬指','小指'))}
    faces=[f.index for f in me.polygons if all(i in allowed for i in f.vertices)]
    skin=[i for i in faces if me.materials[me.polygons[i].material_index].name in {'Body','Nails'}]
    cloth=[i for i in faces if me.materials[me.polygons[i].material_index].name=='服']
    bvh=motion._bvh_from(me,skin); cvh=motion._bvh_from(me,cloth)
    points=[me.vertices[i].co for i in allowed]
    center=Vector(tuple((min(p[a] for p in points)+max(p[a] for p in points))*.5 for a in range(3)))
    direction=Vector((0,-1,.1)).normalized()
    quat=(-direction).to_track_quat('-Z','Y')
    right,up=quat@Vector((1,0,0)),quat@Vector((0,1,0))
    hits=[]
    # A 0.5 mm grid over the hand; exclude the intentionally open wrist.
    for y in range(400):
        for x in range(400):
            origin=center+direction*3+right*((x+.5)/400-.5)*.20+up*(.5-(y+.5)/400)*.20
            bp,bn,bi,bd=bvh.ray_cast(origin,-direction)
            if bp is None:
                continue
            wrist=arm.pose.bones['手首.'+side].head
            axis=(arm.pose.bones['中指１.'+side].head-wrist).normalized()
            if (bp-wrist).dot(axis)<.012:
                continue
            cp,cn,ci,cd=cvh.ray_cast(origin,-direction)
            if cp is None:
                reason='no cloth along ray'; a=None; coords=None
            else:
                a,coords=opacity(cloth[ci],cp)
                if cd<bd-1e-5 and a>.95:
                    continue
                reason='alpha hole' if cd<bd-1e-5 else 'skin in front'
            nearest=cvh.find_nearest(bp)
            face=me.polygons[skin[bi]]
            hits.append({'pixel':[x,y],'skin_face':skin[bi],'vertices':list(face.vertices),
                         'face_toward_camera':bn.dot(direction),
                         'reason':reason,'cloth_alpha':a,'cloth_uv':coords,
                         'ray_depth_delta_m':cd-bd if cp is not None else None,
                         'nearest_cloth_m':nearest[3],'position':list(bp)})
    face_offsets=[]
    cloth_face_sets={tuple(sorted(me.polygons[fi].vertices)):fi for fi in cloth}
    for fi in sorted({h['skin_face'] for h in hits}):
        face=me.polygons[fi]
        if all(i in pair_data for i in face.vertices):
            deltas=[Vector(pair_data[i]['posed_delta']) for i in face.vertices]
            rests=[Vector(pair_data[i]['rest_delta']) for i in face.vertices]
            face_offsets.append({'face':fi,'posed_normal_dot':min(d.dot(face.normal) for d in deltas),
                                 'matching_cloth_face':cloth_face_sets.get(tuple(sorted(pair_data[i]['cloth_vertex'] for i in face.vertices))),
                                 'face_toward_camera':face.normal.dot(direction),
                                 'rest_normal_dot':min(d.dot(mesh.data.polygons[fi].normal) for d in rests),
                                 'posed_center_dot':sum(deltas,Vector()).dot(face.normal)/3})
    reports.append({'side':side,'counts':dict(Counter(h['reason'] for h in hits)),
                    'face_offsets':face_offsets,
                    'faces':dict(Counter(str(h['skin_face']) for h in hits)), 'hits':hits})
owner.to_mesh_clear()
out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
write_json(out/'report.json',{'frame':args.frame,'pixel_size_m':.0005,'hands':reports,'vertex_pairs':pair_data})
print('HAND_AUDIT',[(r['side'],r['counts']) for r in reports],flush=True)
