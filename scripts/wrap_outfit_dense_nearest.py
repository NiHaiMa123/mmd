"""Direct dense exterior fitting diagnostic; never a dynamic acceptance."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import HAND_PREFIX,inside_votes
from mmd_outfit.contact_position_override import install
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);arm=bpy.data.objects['达妮娅_arm'];cloth=bpy.data.objects['Cloth'];sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.levels=2;sub.render_levels=2
def capture(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles]);groups=[[(g.group,g.weight) for g in v.groups] for v in mesh.vertices];ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces,groups
skin,sf,_=capture(bpy.data.objects['Outfit_ClosedSkinContactProxy']);tree=BVHTree.FromPolygons(skin.tolist(),sf.tolist(),all_triangles=True);report={'status':'DENSE_NEAREST_REQUIRES_AUDIT','frame':325,'body_changed':False,'physics':False,'objects':{}}
for name in ('Cloth','SleeveLining'):
    obj=bpy.data.objects[name]
    if name=='SleeveLining':
        sub=obj.modifiers.new('Lining dense contact samples','SUBSURF');sub.subdivision_type='SIMPLE';sub.levels=2;sub.render_levels=2
    co,faces,groups=capture(obj);source=co.copy();names={g.index:g.name for g in obj.vertex_groups if g.name in arm.pose.bones};locked=np.array([max(((w,names[g]) for g,w in gs if g in names),default=(0.,''))[1].startswith(HAND_PREFIX[1:]) for gs in groups]);history=[]
    for iteration in range(3):
        changed=0;depth=0.
        for i in range(len(co)):
            if locked[i]:continue
            q,n,j,d=tree.find_nearest(Vector(co[i]));signed=(Vector(co[i])-q).dot(n)
            if signed<0 and inside_votes(tree,Vector(co[i])):co[i]=np.array(q)+np.array(n)*.002;changed+=1;depth=max(depth,d)
        row={'iteration':iteration,'changed':changed,'max_depth_m':depth};history.append(row);print(name,json.dumps(row),flush=True)
        if not changed:break
    install(obj,co,325);movement=np.linalg.norm(co-source,axis=1);report['objects'][name]={'max_displacement_m':float(movement.max()),'p99_m':float(np.quantile(movement,.99)),'history':history}
scene.frame_start=325;scene.frame_end=325;bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_DenseNearest325.blend'),compress=True);(out/'fit_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
