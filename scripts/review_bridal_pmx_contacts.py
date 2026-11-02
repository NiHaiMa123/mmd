"""Round-trip shoe contact checks on the actual exported PMX and VMD."""
import argparse,sys,json
from pathlib import Path
from collections import Counter
import bpy
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json
from bridal_multiview_review import crossing
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--frames',type=int,nargs='+',default=[1,121,256,3401]);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.fit).resolve()
ie=engine('import_export');ie.clear_scene();objects=ie.import_pmx(str(folder/'mmd/model.pmx'));mesh=ie.model_meshes(objects)[0];arm=next(o for o in objects if o.type=='ARMATURE')
bpy.context.view_layer.objects.active=arm;arm.select_set(True)
bpy.ops.mmd_tools.import_vmd(filepath=str(folder/'mmd/grounded.vmd'),scale=.08,rename_bones=True,margin=0,log_level='ERROR')
mesh.data.calc_loop_triangles();groups={}
for side,sign in [('L',1),('R',-1)]:
    skin=[];shoes=[]
    for tri in mesh.data.loop_triangles:
        indices=tuple(tri.vertices);points=[mesh.data.vertices[i].co for i in indices]
        if not all(p.x*sign>0 for p in points):continue
        material=mesh.data.materials[tri.material_index].name
        if material=='WhiteBridal':shoes.append((indices,material))
        elif all(p.z<.27 for p in points):skin.append((indices,material))
    groups[side]=(skin,shoes)
report={'pmx':str(folder/'mmd/model.pmx'),'vmd':str(folder/'mmd/grounded.vmd'),'frames':{},'scope':'exported PMX sampled foot/stocking versus shoe triangles; 20 micrometre segment cutoff; no dynamics'}
for frame in a.frames:
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh()
    points=[mesh.matrix_world@v.co for v in me.vertices]
    for side,(skin,shoes) in groups.items():
        skin_tree=BVHTree.FromPolygons(points,[v for v,m in skin],all_triangles=True)
        shoe_tree=BVHTree.FromPolygons(points,[v for v,m in shoes],all_triangles=True)
        counts=Counter()
        for i,j in skin_tree.overlap(shoe_tree):
            if crossing([points[k] for k in skin[i][0]],[points[k] for k in shoes[j][0]]):counts[skin[i][1]]+=1
        report['frames'][f'{frame}_{side}']={'crossing_pairs':sum(counts.values()),'by_layer_material':dict(counts)}
        print('PMX_CONTACTS',frame,side,sum(counts.values()),dict(counts),flush=True)
    evaluated.to_mesh_clear();write_json(folder/'pmx_contact_review.json',report)
assert all(r['crossing_pairs']==0 for r in report['frames'].values()),'Exported PMX foot/shoe contacts remain'
print('PMX_CONTACTS_VERIFIED',flush=True)
