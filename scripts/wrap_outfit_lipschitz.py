"""Static contact wrapping with geodesically bounded displacement gradients.

Uses coherent anatomical directions and propagates clearance over the garment
instead of independently sending neighbouring points to unrelated skin faces.
"""
import argparse,json,sys,subprocess
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import SKIN,HAND_PREFIX,inside_votes,triangle_crosses
from mmd_outfit.outfit_arap_contact import intersection_midpoint
from mmd_outfit.contact_position_override import install
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--iterations',type=int,default=5);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.levels=2;sub.render_levels=2
def capture(obj,skin_only=False):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles if not skin_only or mesh.materials[t.material_index].name in SKIN|{'Nails'}]);groups=[[(g.group,g.weight) for g in v.groups] for v in mesh.vertices];ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces,groups
skin,sf,_=capture(body,True);body_tree=BVHTree.FromPolygons(skin.tolist(),sf.tolist(),all_triangles=True);proxy,pf,_=capture(bpy.data.objects['Outfit_ClosedSkinContactProxy']);tree=BVHTree.FromPolygons(proxy.tolist(),pf.tolist(),all_triangles=True)
def head(name):return np.array(arm.matrix_world@arm.pose.bones[name].head)
paths={'core':(head('下半身'),head('首'))}
for side in ('L','R'):
    paths['upper.'+side]=(head('腕.'+side),head('ひじ.'+side));paths['fore.'+side]=(head('ひじ.'+side),head('手首.'+side))
def kind(name):
    bone=arm.pose.bones.get(name)
    while bone:
        for side in ('L','R'):
            if bone.name in ('ひじ.'+side,'手首.'+side,'手捩.'+side):return 'fore.'+side
            if bone.name=='腕.'+side:return 'upper.'+side
        bone=bone.parent
    return 'core'
def direction(points,kinds):
    result=np.zeros_like(points)
    for name,(begin,end) in paths.items():
        mask=np.array(kinds)==name
        if not mask.any():continue
        edge=end-begin;t=np.clip((points[mask]-begin)@edge/np.dot(edge,edge),0,1);axis=begin+t[:,None]*edge;delta=points[mask]-axis;norm=np.linalg.norm(delta,axis=1);result[mask]=delta/np.maximum(norm[:,None],1e-10)
    return result
def requirement(point,vector,force=False):
    q,n,j,d=tree.find_nearest(Vector(point))
    if q is None:return 0.
    signed=(Vector(point)-q).dot(n)
    if not force and (signed>=0 or not inside_votes(tree,Vector(point))):return 0.
    origin=point.copy();travel=0.
    for _ in range(20):
        hit,normal,index,distance=tree.ray_cast(Vector(origin),Vector(vector),.2-travel)
        if hit is None:return 0.
        travel=float(np.linalg.norm(np.array(hit)-point));origin=point+vector*(travel+.00002)
        if normal.dot(Vector(vector))>0:return travel+.003
        if travel>.19:break
    return 0.
report={'status':'BOUNDED_GRADIENT_STATIC_WRAP_REQUIRES_AUDIT','frame':325,'body_changed':False,'new_physics':False,'objects':{}}
for name in ('Cloth','SleeveLining'):
    obj=bpy.data.objects[name]
    if name=='SleeveLining':
        dense=obj.modifiers.new('Lining contact sampling','SUBSURF');dense.subdivision_type='SIMPLE';dense.levels=3;dense.render_levels=3
    source,faces,groups=capture(obj);co=source.copy();names={g.index:g.name for g in obj.vertex_groups if g.name in arm.pose.bones};dominant=[max(((w,names[g]) for g,w in gs if g in names),default=(0.,''))[1] for gs in groups];locked=np.array([n.startswith(HAND_PREFIX[1:]) for n in dominant]);kinds=[kind(n) for n in dominant]
    if name=='SleeveLining':
        kinds=[]
        for point in source:
            distances=[]
            for k in ('upper.L','upper.R'):
                begin,end=paths[k];edge=end-begin;t=np.clip(np.dot(point-begin,edge)/np.dot(edge,edge),0,1);distances.append((np.linalg.norm(point-begin-t*edge),k))
            kinds.append(min(distances)[1])
    # Nearest exterior normals provide a local outward direction. A distant
    # bone axis can point through another limb at a bent elbow.
    dirs=np.array([tree.find_nearest(Vector(point))[1][:] for point in source]);history=[]
    for iteration in range(a.iterations):
        needed=np.zeros(len(co));inside=0
        for i in range(len(co)):
            if locked[i]:continue
            needed[i]=requirement(co[i],dirs[i]);inside+=needed[i]>0
        gt=BVHTree.FromPolygons(co.tolist(),faces.tolist(),all_triangles=True);pairs=[(i,j) for i,j in gt.overlap(body_tree) if triangle_crosses([Vector(v) for v in co[faces[i]]],[Vector(v) for v in skin[sf[j]]])]
        for i,j in pairs:
            ids=faces[i];point=intersection_midpoint(co[ids],skin[sf[j]]);vec=dirs[ids].mean(axis=0);vec/=max(np.linalg.norm(vec),1e-10);amount=requirement(point,vec,True)
            for v in ids:
                if not locked[v]:needed[v]=max(needed[v],amount)
        row={'iteration':iteration,'inside_vertices':int(inside),'body_crossings':len(pairs),'max_requested_m':float(needed.max())};print('BOUNDED_CONTACT_WRAP',name,json.dumps(row),flush=True);history.append(row)
        if not needed.any():break
        payload=out/(name+'_field.npz');result=out/(name+'_field_result.npz');np.savez_compressed(payload,points=source,faces=faces,needed=needed,slope=np.array(.5));run=subprocess.run([str(ROOT/'tools/contact_stack/venv/Scripts/python.exe'),str(ROOT/'scripts/solve_lipschitz_contact_field.py'),'--input',str(payload),'--output',str(result)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if run.returncode:raise RuntimeError(run.stderr.decode(errors='replace'))
        with np.load(result) as z:field=z['field'].copy()
        field[locked]=0;co+=dirs*field[:,None];(out/'wrap_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    install(obj,co,325);movement=np.linalg.norm(co-source,axis=1);report['objects'][name]={'vertices':len(co),'maximum_displacement_m':float(movement.max()),'p99_displacement_m':float(np.quantile(movement,.99)),'history':history}
scene.frame_start=325;scene.frame_end=325;bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_BoundedWrap325.blend'),compress=True);(out/'wrap_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
