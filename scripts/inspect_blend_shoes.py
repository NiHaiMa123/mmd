"""Inspect an external shoe Blend without editing its source file."""
import argparse,json,sys
from pathlib import Path
from collections import Counter,defaultdict
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json
p=argparse.ArgumentParser();p.add_argument('--asset',required=True);p.add_argument('--out',required=True)
p.add_argument('--shoe-only',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=a.asset,load_ui=False,use_scripts=False)
report={'asset':a.asset,'units':bpy.context.scene.unit_settings.system,'scale_length':bpy.context.scene.unit_settings.scale_length,'objects':[],'images':[]}
meshes=[]
for obj in bpy.data.objects:
    row={'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,'hidden':obj.hide_get(),'hide_render':obj.hide_render}
    row['matrix']=[list(v) for v in obj.matrix_world]
    if obj.type=='MESH':
        meshes.append(obj);points=[obj.matrix_world@v.co for v in obj.data.vertices]
        row.update(vertices=len(points),faces=len(obj.data.polygons),materials=[m.name if m else None for m in obj.data.materials],
            bounds=[[min(v[i] for v in points) for i in range(3)],[max(v[i] for v in points) for i in range(3)]],
            groups=[g.name for g in obj.vertex_groups],modifiers=[{'name':m.name,'type':m.type,'object':getattr(getattr(m,'object',None),'name',None)} for m in obj.modifiers])
        row['material_faces']=dict(Counter(obj.data.materials[f.material_index].name if obj.data.materials[f.material_index] else None for f in obj.data.polygons))
        parent=list(range(len(points)))
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for f in obj.data.polygons:
            for i in f.vertices[1:]:parent[find(i)]=find(f.vertices[0])
        parts=defaultdict(list)
        for i in range(len(points)):parts[find(i)].append(i)
        row['components']=[{'vertices':len(ids),'min':[min(points[j][i] for j in ids) for i in range(3)],'max':[max(points[j][i] for j in ids) for i in range(3)]} for ids in sorted(parts.values(),key=lambda ids:-len(ids))[:40]]
    if obj.type=='ARMATURE':row['bones']=[{'name':b.name,'head':list(obj.matrix_world@b.head_local),'tail':list(obj.matrix_world@b.tail_local),'parent':b.parent.name if b.parent else None} for b in obj.data.bones]
    report['objects'].append(row)
for image in bpy.data.images:report['images'].append({'name':image.name,'path':image.filepath,'packed':bool(image.packed_file),'size':list(image.size)})
write_json(out/'inventory.json',report)
render=engine('extraction');scene=bpy.context.scene
render._setup_render(scene,1000,1000);render._setup_lights(scene)
for obj in bpy.data.objects:
    if obj.type in {'MESH','CURVE'}:
        allowed=not a.shoe_only or (obj.name not in {'Plane.001','Cylinder.002'} and not obj.name.startswith('Stitch Type'))
        obj.hide_render=not allowed;obj.hide_set(not allowed)
meshes=[obj for obj in meshes if not obj.hide_render]
points=[obj.matrix_world@v.co for obj in meshes for v in obj.data.vertices]
minimum=Vector([min(v[i] for v in points) for i in range(3)]);maximum=Vector([max(v[i] for v in points) for i in range(3)])
center=(minimum+maximum)*.5;extent=max(maximum-minimum)
data=bpy.data.cameras.new('ShoeAssetCamera');data.type='ORTHO';data.ortho_scale=extent*1.25
camera=bpy.data.objects.new('ShoeAssetCamera',data);scene.collection.objects.link(camera);scene.camera=camera
for name,direction in [('front',(0,-1,.12)),('side',(1,0,.1)),('oblique',(1,-1,.4))]:
    camera.location=center+Vector(direction).normalized()*extent*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
print('SHOE_ASSET_INVENTORY',str(out/'inventory.json'),flush=True)
