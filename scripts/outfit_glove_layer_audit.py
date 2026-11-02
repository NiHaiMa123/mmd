"""Audit glove overlay faces before choosing which surfaces need rebuilding."""
import sys
from pathlib import Path
from collections import defaultdict, Counter
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
profile=read_json(sys.argv[sys.argv.index('--')+1])
out=ROOT/'outputs/glove_layer_audit'
out.mkdir(exist_ok=True)
ie,dressing,render=[engine(n) for n in ('import_export','dressing','extraction')]
ie.clear_scene()
objects=ie.import_pmx(profile['source']['path'])
mesh=ie.model_meshes(objects)[0]
arm=next(o for o in objects if o.type=='ARMATURE')
dominant=dressing.dominant_bones(mesh)
side='L'
wrist=arm.data.bones['手首.'+side].head_local
axis=(arm.data.bones['中指１.'+side].head_local-wrist).normalized()
selected=[]
for f in mesh.data.polygons:
    if sum(dominant[i].endswith('.L') and dominant[i][:-2].startswith(('手首','親指','人指','中指','薬指','小指','ひじ','腕','手捩')) for i in f.vertices)<len(f.vertices)*.5:
        continue
    if (f.center-wrist).dot(axis)<-.018:
        continue
    selected.append(f)
by_material=defaultdict(list)
for f in selected:
    by_material[mesh.data.materials[f.material_index].name].append(f)
def position_faces(faces):
    return {tuple(sorted(tuple(round(c,6) for c in mesh.data.vertices[i].co) for i in f.vertices)) for f in faces}
base=position_faces(by_material['服'])
report={}
for name,faces in by_material.items():
    material=bpy.data.materials.get(name)
    nodes=[]
    for node in material.node_tree.nodes:
        record={'name':node.name,'type':node.type}
        if node.type=='TEX_IMAGE' and node.image:
            record.update(image=node.image.filepath,size=list(node.image.size),channels=node.image.channels)
            uvs=[mesh.data.uv_layers.active.data[i].uv for f in faces for i in f.loop_indices]
            sample=[]
            w,h=node.image.size
            for uv in uvs[::max(1,len(uvs)//100)]:
                sample.append(node.image.pixels[(int((uv.y%1)*h)*w+int((uv.x%1)*w))*4+3])
            record['sample_alpha_min']=min(sample)
            record['sample_alpha_max']=max(sample)
        nodes.append(record)
    report[name]={'faces':len(faces),'vertices':len({i for f in faces for i in f.vertices}),
                  'exact_base_face_duplicates':len(position_faces(faces)&base),
                  'diffuse_alpha':material.diffuse_color[3],
                  'mmd_alpha':getattr(material.mmd_material,'alpha',None),'nodes':nodes}
write_json(out/'report.json',report)
render._setup_render(bpy.context.scene,1000,1000)
render._setup_lights(bpy.context.scene)
data=bpy.data.cameras.new('GloveLayerAudit')
data.type='ORTHO'
data.ortho_scale=.20
camera=bpy.data.objects.new('GloveLayerAudit',data)
bpy.context.scene.collection.objects.link(camera)
bpy.context.scene.camera=camera
center=wrist+axis*.045
camera.location=center+Vector((0,-3,.3))
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
for name,faces in by_material.items():
    part,_=engine('garment')._copy_mesh_subset(mesh,[f.index for f in faces],'GloveLayer')
    mesh.hide_render=True
    bpy.context.scene.render.filepath=str(out/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(part,do_unlink=True)
mesh.hide_render=False
print('GLOVE_LAYERS',report,flush=True)
