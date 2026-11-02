import bpy,json,sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'E:\project\mmd\mmd_repo');JOB=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/blender_native_units';state=bpy.app.driver_namespace['MMD_NATIVE_UNITS_LEGACY_20261030']
sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.surface import coords,crosses
from animation_contact_tools.closed_collider_field import ClosedColliderField
s=bpy.data.scenes[state['scene']];s.rigidbody_world.enabled=False;s.frame_set(1);bpy.context.view_layer.update();root=bpy.data.objects[state['root']]
rigids=[o for o in root.children_recursive if o.rigid_body];body=[o for o in rigids if o.rigid_body.kinematic];hair=[o for o in rigids if not o.rigid_body.kinematic]
excluded={frozenset((o.rigid_body_constraint.object1.name,o.rigid_body_constraint.object2.name)) for o in root.children_recursive if o.rigid_body_constraint and o.rigid_body_constraint.enabled and o.rigid_body_constraint.disable_collisions and o.rigid_body_constraint.object1 and o.rigid_body_constraint.object2}
meshes={}
for o in rigids:
    c=coords(o);o.data.calc_loop_triangles();t=np.asarray([tri.vertices[:] for tri in o.data.loop_triangles],dtype=np.int32);tree=BVHTree.FromPolygons(c.tolist(),t.tolist(),all_triangles=True);meshes[o.name]=(c,t,tree,c.min(0),c.max(0))
hits=[]
for h in hair:
    hc,hf,ht,hmin,hmax=meshes[h.name]
    for b in body:
        if frozenset((h.name,b.name)) in excluded:continue
        bc,bf,bt,bmin,bmax=meshes[b.name]
        if np.any(hmax<bmin) or np.any(bmax<hmin):continue
        centre=Vector(bc.mean(0));p,n,_,_=bt.find_nearest(centre);outward=1 if (centre-p).dot(n)<0 else -1;dist=[]
        for v in hc:
            q=Vector(v);p,n,_,d=bt.find_nearest(q);dist.append(float(d) if (q-p).dot(n)*outward>=0 else -float(d))
        hcentre=Vector(hc.mean(0));hp,hn,_,_=ht.find_nearest(hcentre);hsign=1 if (hcentre-hp).dot(hn)<0 else -1;body_inside=0
        for v in bc:
            q=Vector(v);hp,hn,_,hd=ht.find_nearest(q)
            if (q-hp).dot(hn)*hsign<0 and hd>.001:body_inside+=1
        crossings=0
        for hi,bi in ht.overlap(bt):
            if crosses([Vector(v) for v in hc[hf[hi]]],[Vector(v) for v in bc[bf[bi]]]):crossings+=1
        if min(dist)<-.001 or crossings or body_inside:hits.append(dict(hair=h.name,hair_bone=h.mmd_rigid.bone,body=b.name,body_bone=b.mmd_rigid.bone,minimum_hair_vertex_distance_m=min(dist)*.08,triangle_crossings=crossings,body_vertices_inside_hair_proxy=body_inside))
data=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware';skin=np.load(data/'body.npy',mmap_mode='r')[0];bf=np.load(data/'body_faces.npy');field=ClosedColliderField(skin,bf);outside=[]
for b in body:
    c,t,*_=meshes[b.name];points=np.vstack([c,c[t].mean(1)])*.08;d,_=field(points);outside.append(dict(object=b.name,bone=b.mmd_rigid.bone,max_outside_skin_m=float(d.max()),outside_samples=int((d>.001).sum()),samples=len(d),group=b.mmd_rigid.collision_group_number))
target=np.load(data/'hair_initial.npy');m=bpy.data.objects[state['mesh']];mapped=np.load(JOB/'native_vertex_map.npy');bind=float(np.linalg.norm(coords(m)[mapped]*.08-target,axis=1).max())
report=dict(stage='INITIAL_PROXY_AUDIT',physics_disabled=True,visible_initial_replay_error_m=bind,allowed_hair_body_proxy_overlap_pairs=sorted(hits,key=lambda x:x['minimum_hair_vertex_distance_m']),body_proxy_skin_coverage=sorted(outside,key=lambda x:x['max_outside_skin_m'],reverse=True))
(JOB/'proxy_initial_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(dict(bind_error=bind,overlap_pairs=len(hits),worst=report['allowed_hair_body_proxy_overlap_pairs'][:8],outside=report['body_proxy_skin_coverage'][:5]),ensure_ascii=False))
