"""Separate rigid shoe-foot motion from accessories tied around the calf."""
import argparse,sys,json,shutil
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
report={'source':a.source,'weights':{},'accessories':[]}
for obj in ie.model_meshes():
    if obj.get('external_shoe'):continue
    names={g.index:g.name for g in obj.vertex_groups};count=0
    for v in obj.data.vertices:
        if v.co.z>=.19 or abs(v.co.x)>.17:continue
        side='L' if v.co.x>0 else 'R';target='足首D.'+side
        entries=[(names[e.group],e.weight) for e in v.groups if not names[e.group].startswith('mmd_')]
        old=sum(w for n,w in entries if n==target)
        t=min(1.,max(0.,(.16-v.co.z)/.035));desired=t*t*(3-2*t)
        if desired<=old+1e-6:continue
        other=sum(w for n,w in entries if n!=target)
        for name,w in entries:
            if name==target:continue
            value=w*(1-desired)/max(other,1e-9)
            if value<1e-7:obj.vertex_groups[name].remove([v.index])
            else:obj.vertex_groups[name].add([v.index],value,'REPLACE')
        (obj.vertex_groups.get(target) or obj.vertex_groups.new(name=target)).add([v.index],desired,'REPLACE');count+=1
    report['weights'][obj.name]=count
body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'));cloth=bpy.data.objects['Cloth']
faces=[f for f in body.data.polygons if (body.data.materials[f.material_index].mmd_material.name_j or body.data.materials[f.material_index].name) in {'Body','Nails'} and min(body.data.vertices[i].co.z for i in f.vertices)<.1953568]
ids=sorted({i for f in faces for i in f.vertices});offset=len(cloth.data.vertices)-len(ids)
assert len(faces)==8928
for k,bi in enumerate(ids):
    ci=offset+k;v=cloth.data.vertices[ci]
    for entry in list(v.groups):
        group=cloth.vertex_groups[entry.group]
        if not group.name.startswith('mmd_'):group.remove([ci])
    for entry in body.data.vertices[bi].groups:
        name=body.vertex_groups[entry.group].name
        if not name.startswith('mmd_'):(cloth.vertex_groups.get(name) or cloth.vertex_groups.new(name=name)).add([ci],entry.weight,'REPLACE')
report['matched_stocking_weights']=len(ids)
# Nylon at the moving Achilles crease needs less standoff than the loose calf.
# Fade to the original 1.5-mm offset at the reconstructed stocking boundary.
def smooth(v):
    v=min(1.,max(0.,v));return v*v*(3-2*v)
thinned=0;max_thinning=0.
for k,bi in enumerate(ids):
    ci=offset+k;p=body.data.vertices[bi].co
    mask=smooth((p.y-.055)/.015)*smooth((p.z-.12)/.025)*smooth((.195-p.z)/.02)
    move=(body.data.vertices[bi].co-cloth.data.vertices[ci].co)*(.65*mask)
    if move.length<1e-9:continue
    cloth.data.vertices[ci].co+=move
    if cloth.data.shape_keys:
        for key in cloth.data.shape_keys.key_blocks:key.data[ci].co+=move
    thinned+=1;max_thinning=max(max_thinning,move.length)
report['achilles_stocking_standoff']={'vertices':thinned,'max_reduction_m':max_thinning,'minimum_fraction_of_original':.35,'deleted_faces':0}
for obj in [o for o in bpy.data.objects if o.get('external_shoe')]:
    short=obj.name.removeprefix('Bridal_')[:-2]
    if short not in {'Cube','Cylinder','Plane','Sphere','BézierCircle','大蝴蝶结.fbx'}:continue
    side=obj.name[-1];bone='ひざD.'+side
    obj.vertex_groups.clear();obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))),1.,'REPLACE')
    if short in {'Cube','Cylinder','Plane','BézierCircle'}:
        pivot=Vector(((1 if side=='L' else -1)*.08046,.05114,.1594))
        obj.matrix_world=Matrix.Translation(pivot)@Matrix.Scale(1.04,4)@Matrix.Translation(-pivot)@obj.matrix_world
    if short=='Sphere':
        # Raise the loose lower pearl strand above the deforming ankle crease.
        obj.matrix_world=Matrix.Translation((0,0,.030))@obj.matrix_world
    if short=='大蝴蝶结.fbx':
        obj.matrix_world=Matrix.Translation((0,.014,0))@obj.matrix_world
    report['accessories'].append({'object':obj.name,'bone':bone,'cuff_uniform_scale':1.04 if short in {'Cube','Cylinder','Plane','BézierCircle'} else 1.,
                                  'translation_m':[0,0,.030] if short=='Sphere' else [0,.014,0] if short=='大蝴蝶结.fbx' else [0,0,0]})
write_json(out/'binding_correction.json',report)
contact=Path(a.source).parent/'contact_correction.json'
if contact.exists():
    shutil.copyfile(contact,out/contact.name)
    original=Path(json.loads(contact.read_text(encoding='utf8'))['source']).parent/'fit_report.json'
    base=json.loads(original.read_text(encoding='utf8'))
    base['contact_followup']={'surface_fit':str(out/contact.name),'binding':str(out/'binding_correction.json')}
    write_json(out/'fit_report.json',base)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'work.blend'))
shutil.copyfile(out/'work.blend',out/'Daniya_WhiteBridal_FitChecked.blend')
print('SHOE_BINDING_CORRECTION',json.dumps(report,ensure_ascii=False),flush=True)
