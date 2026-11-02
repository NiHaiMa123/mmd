"""Compose accepted part transforms and fit dense residuals to closed skin.

This produces one explicitly limited pose. The original body, clothing data,
UVs, and morphs are retained. No triangle/body masks hide remaining crossings.
"""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import HAND_PREFIX,inside_votes
from mmd_outfit.contact_position_override import install
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--parts',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);cloth=bpy.data.objects['Cloth'];arm=bpy.data.objects['达妮娅_arm'];proxy=bpy.data.objects['Outfit_ClosedSkinContactProxy'];sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.show_viewport=False;sub.show_render=False;binding=cloth.modifiers['Panels follow actual posed body']
def capture(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles]);groups=[[(g.group,g.weight) for g in v.groups] for v in mesh.vertices];ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces,groups
current,_,_=capture(cloth);binding.show_viewport=False;raw,_,_=capture(cloth);binding.show_viewport=True
with bpy.data.libraries.load(str(Path(a.parts).resolve()),link=False) as (src,dst):dst.objects=['Cloth_StaticContactPositions']
loaded=dst.objects[0]
if loaded is None:raise ValueError('Part-fit position helper missing')
matrix=np.array(loaded.matrix_world);part=np.array([v.co[:] for v in loaded.data.vertices]);part=part@matrix[:3,:3].T+matrix[:3,3];weights=np.array([v.value for v in cloth.data.attributes['OutfitLiveSkinBinding'].data]);composed=current+(part-raw)*(1-weights[:,None]);bpy.data.objects.remove(loaded,do_unlink=True);mod=install(cloth,composed,325);bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=list(cloth.modifiers).index(sub));sub.show_viewport=True;sub.show_render=True;sub.levels=2;sub.render_levels=2
skin,skin_faces,_=capture(proxy);tree=BVHTree.FromPolygons(skin.tolist(),skin_faces.tolist(),all_triangles=True);report={'status':'DENSE_STATIC_CONTACT_WRAP_REQUIRES_AUDIT','frame':325,'body_coordinates_changed':False,'new_cloth_simulation':False,'objects':{}}
for name in ('Cloth','SleeveLining'):
    obj=bpy.data.objects[name];co,faces,groups=capture(obj);source=co.copy();names={g.index:g.name for g in obj.vertex_groups if g.name in arm.pose.bones};locked=np.array([max(((w,names[g]) for g,w in gs if g in names),default=(0.,''))[1].startswith(HAND_PREFIX[1:]) for gs in groups]);history=[]
    for iteration in range(3):
        changed=0;max_depth=0.
        for i in range(len(co)):
            if locked[i]:continue
            q,n,j,d=tree.find_nearest(Vector(co[i]))
            if q is None:continue
            signed=(Vector(co[i])-q).dot(n)
            if signed<-.000001:
                if not inside_votes(tree,Vector(co[i])):continue
                co[i]=np.array(q)+np.array(n)*.0015;changed+=1;max_depth=max(max_depth,d)
            elif d<.0015 and signed>=0:co[i]+=np.array(n)*(.0015-d);changed+=1
        history.append({'iteration':iteration,'changed_vertices':changed,'max_inside_depth_m':max_depth});print('DENSE_CLOTHING_WRAP',name,json.dumps(history[-1]),flush=True)
        if not changed:break
    modifier=install(obj,co,325);delta=np.linalg.norm(co-source,axis=1);report['objects'][name]={'vertices':len(co),'changed_vertices':int(np.sum(delta>1e-7)),'max_displacement_m':float(delta.max()),'p99_displacement_m':float(np.quantile(delta,.99)),'locked_finger_vertices':int(locked.sum()),'history':history};(out/'wrap_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
stock=bpy.data.objects.get('ContinuousExteriorNylon')
if stock:
    for polygon in stock.data.polygons:polygon.use_smooth=True
scene.frame_start=325;scene.frame_end=325;scene.frame_set(325);scene['outfit_contact_scope']='Pose 325 only; real-body and layer audits required';bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_BodyContact325.blend'),compress=True);(out/'wrap_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
