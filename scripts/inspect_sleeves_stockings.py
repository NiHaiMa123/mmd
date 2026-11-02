"""Inspect complete sleeve layers and the uncovered hip/stocking contact."""
import argparse,sys,json
from pathlib import Path
from collections import defaultdict,Counter
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
from bridal_multiview_review import crossing

def parts(obj,mat_names):
    result=[];names={g.index:g.name for g in obj.vertex_groups}
    for name in mat_names:
        faces=[f for f in obj.data.polygons if obj.data.materials[f.material_index].mmd_material.name_j==name]
        parent={i:i for f in faces for i in f.vertices};positions={}
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        def union(i,j):
            i,j=find(i),find(j)
            if i!=j:parent[j]=i
        for i in parent:
            key=tuple(round(c,6) for c in obj.data.vertices[i].co)
            if key in positions:union(i,positions[key])
            else:positions[key]=i
        for face in faces:
            for i in face.vertices[1:]:union(face.vertices[0],i)
        groups=defaultdict(list)
        for i in parent:groups[find(i)].append(i)
        for ids in groups.values():
            if len(ids)<100:continue
            bones=Counter(names[g.group] for i in ids for g in obj.data.vertices[i].groups if g.weight>.01 and not names[g.group].startswith('mmd_'))
            if not any(n.startswith(('袖_','袖環')) for n in bones):continue
            points=[obj.data.vertices[i].co for i in ids];used=set(ids)
            result.append({'material':name,'vertices':ids,'faces':[f.index for f in faces if all(i in used for i in f.vertices)],'side':'L' if sum(p.x for p in points)>0 else 'R','bounds':[[min(p[k] for p in points),max(p[k] for p in points)] for k in range(3)],'bones':dict(bones)})
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    ie,render=engine('import_export'),engine('extraction');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.blend,load_ui=False,use_scripts=False)
    cloth=bpy.data.objects['Cloth'];body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    report={'source':a.blend,'sleeves':parts(cloth,['新規','服+jinshu']),'bones':{n:{'head':list(arm.data.bones[n].head_local),'tail':list(arm.data.bones[n].tail_local)} for n in ['下半身','上半身','上半身2','腕.L','腕.R','ひじ.L','ひじ.R']}}
    body_names={g.index:g.name for g in body.vertex_groups};stock_faces=[f.index for f in cloth.data.polygons if cloth.data.materials[f.material_index].mmd_material.name_j=='腿']
    report['stockings']={'faces':len(stock_faces),'body_low_bone_counts':dict(Counter(max(((g.weight,body_names[g.group]) for g in v.groups if not body_names[g.group].startswith('mmd_')),default=(0,'NONE'))[1] for v in body.data.vertices if v.co.z<1.10))}
    write_json(out/'inventory.json',report)
    original=list(bpy.data.objects)
    for obj in original:obj.hide_render=True
    scene=bpy.context.scene;render._setup_render(scene,1000,1000);render._setup_lights(scene)
    data=bpy.data.cameras.new('GarmentInspect');data.type='ORTHO';cam=bpy.data.objects.new('GarmentInspect',data);scene.collection.objects.link(cam);scene.camera=cam
    for obj in ie.model_meshes():obj.hide_render=False
    for name,direction,center,scale in [('torso_front',(0,-1,.05),(0,.02,1.2),.85),('torso_back',(0,1,.05),(0,.02,1.2),.85),('sleeve_L_outer',(1,-.7,.25),(.235,.02,1.2),.40),('sleeve_L_above',(0,-.3,1),(.235,.02,1.2),.40),('legs_front',(0,-1,.02),(0,.02,.61),1.2),('legs_back',(0,1,.02),(0,.02,.61),1.2)]:
        center=Vector(center);data.ortho_scale=scale;cam.location=center+Vector(direction).normalized()*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{name}.png');bpy.ops.render.render(write_still=True)
    # Retain only stockings on the garment for a genuine hip coverage view.
    mesh=bpy.data.meshes.new_from_object(cloth.evaluated_get(bpy.context.evaluated_depsgraph_get()),preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.delete(bm,geom=[f for f in bm.faces if mesh.materials[f.material_index].mmd_material.name_j!='腿'],context='FACES');bm.to_mesh(mesh);bm.free()
    copy=bpy.data.objects.new('StockingInspection',mesh);scene.collection.objects.link(copy);copy.matrix_world=cloth.matrix_world
    for obj in ie.model_meshes():obj.hide_render=obj!=body
    data.ortho_scale=.45;center=Vector((0,.03,.93));cam.location=center+Vector((0,3,.05));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/'hips_back_no_skirt.png');bpy.ops.render.render(write_still=True)
    deps=bpy.context.evaluated_depsgraph_get();bme=bpy.data.meshes.new_from_object(body.evaluated_get(deps),depsgraph=deps);bme.calc_loop_triangles();mesh.calc_loop_triangles()
    bp=[body.matrix_world@v.co for v in bme.vertices];sp=[copy.matrix_world@v.co for v in mesh.vertices]
    bt=[t.vertices[:] for t in bme.loop_triangles if all(.75<bp[i].z<1.1 for i in t.vertices) and bme.materials[t.material_index].mmd_material.name_j=='Body'];st=[t.vertices[:] for t in mesh.loop_triangles if all(.75<sp[i].z<1.1 for i in t.vertices)]
    bvh=BVHTree.FromPolygons(bp,bt,all_triangles=True);svh=BVHTree.FromPolygons(sp,st,all_triangles=True);segments=[]
    for i,j in bvh.overlap(svh):
        segment=crossing([bp[k] for k in bt[i]],[sp[k] for k in st[j]])
        if segment:segments.append([list(p) for p in segment])
    report['hip_contacts']={'crossing_pairs':len(segments),'segments':segments};write_json(out/'inventory.json',report)
    print('SLEEVE_STOCKING_INSPECTION',json.dumps({'sleeves':[{k:v for k,v in row.items() if k not in ('vertices','faces')} for row in report['sleeves']],'hip_crossing_pairs':len(segments),'bones':report['bones']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
