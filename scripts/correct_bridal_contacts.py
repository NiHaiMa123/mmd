"""Repair the complete foot/stocking layers without projecting the hard shoe."""
import sys,argparse,json,shutil
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.shoe_contact import inward_surface,fit_layers
from mmd_outfit.jobs import write_json
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--source',default=str(ROOT/'outputs/white_bridal_shoes/final/Daniya_WhiteBridal_Clean.blend'));p.add_argument('--passes',type=int,default=32);p.add_argument('--toe-forward',type=float,default=.015)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'));cloth=bpy.data.objects['Cloth']
foot_faces=[f for f in body.data.polygons if (body.data.materials[f.material_index].mmd_material.name_j or body.data.materials[f.material_index].name) in {'Body','Nails'} and min(body.data.vertices[i].co.z for i in f.vertices)<.1953568]
ids=sorted({i for f in foot_faces for i in f.vertices});offset=len(cloth.data.vertices)-len(ids);mapping=[(bi,offset+k) for k,bi in enumerate(ids)]
assert len(foot_faces)==8928
assert all(.0014<(body.data.vertices[bi].co-cloth.data.vertices[ci].co).length<.0021 for bi,ci in mapping),'Stocking reconstruction provenance does not match'
surfaces={};rigid=[]
for side in ('L','R'):
    shell=bpy.data.objects['Bridal_high heel shoe 3d model.'+side]
    insole=bpy.data.objects['Bridal_high heel shoe 3d model.002.'+side]
    surfaces[side]=[inward_surface(shell,lambda name,n,c:'内衬' in name),inward_surface(insole,lambda name,n,c:n.z>.12)]
    # Uniform scale keeps spherical beads and their continuous chain layout.
    pearl=bpy.data.objects['Bridal_Sphere.'+side]
    points=[pearl.matrix_world@v.co for v in pearl.data.vertices]
    pivot=Vector(tuple((min(p[k] for p in points)+max(p[k] for p in points))/2 for k in range(3)))
    pearl.matrix_world=Matrix.Translation(pivot)@Matrix.Scale(1.20,4)@Matrix.Translation(-pivot)@pearl.matrix_world
    rigid.append({'object':pearl.name,'uniform_scale':1.20,'pivot':list(pivot),'bead_aspect_ratio_preserved':True})
report={'source':a.source,'rigid_pearl_adjustments':rigid,'foot_region_faces':len(foot_faces)}
report['fit']=fit_layers(body,cloth,mapping,surfaces,passes=a.passes,toe_forward=a.toe_forward)
write_json(out/'contact_correction.json',report)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'work.blend'))
shutil.copyfile(out/'work.blend',out/'Daniya_WhiteBridal_FitChecked.blend')
print('SHOE_CONTACT_CORRECTION',json.dumps(report,ensure_ascii=False),flush=True)
