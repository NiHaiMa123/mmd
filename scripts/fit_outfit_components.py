"""Fit disconnected garment pieces with coherent anatomical transforms."""
import argparse,json,sys
from collections import Counter
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import SKIN,triangle_crosses,inside_votes,HAND_PREFIX
from mmd_outfit.contact_position_override import install
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.show_viewport=False;sub.show_render=False
def capture(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles]);mats=np.array([t.material_index for t in mesh.loop_triangles]);weights=[[(g.group,g.weight) for g in v.groups] for v in mesh.vertices];names=[m.name for m in mesh.materials];ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces,mats,weights,names
skin,sf,sm,_,skin_mats=capture(body);sf=sf[np.array([skin_mats[int(m)] in SKIN for m in sm])];tree=BVHTree.FromPolygons(skin.tolist(),sf.tolist(),all_triangles=True);co,faces,materials,weights,names=capture(cloth);source=co.copy();rest=np.array([v.co[:] for v in cloth.data.vertices]);_,weld=np.unique(np.rint(rest/1e-6).astype(np.int64),axis=0,return_inverse=True);parent=np.arange(int(weld.max())+1)
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for face in weld[faces]:
    for i in face[1:]:parent[root(int(i))]=root(int(face[0]))
labels=np.array([root(int(v)) for v in weld]);components=sorted(np.unique(labels),key=lambda c:-np.sum(labels==c));group_names={g.index:g.name for g in cloth.vertex_groups if g.name in arm.pose.bones};dominant=[max(((w,group_names[g]) for g,w in gs if g in group_names),default=(0.,''))[1] for gs in weights]
def head(name):return np.array(arm.matrix_world@arm.pose.bones[name].head)
core_origin=head('下半身');core_axis=head('首')-core_origin;core_axis/=np.linalg.norm(core_axis)
def kind(name):
    if name.startswith(('スカート','裙')):return 'skirt'
    bone=arm.pose.bones.get(name)
    while bone:
        for s in ('L','R'):
            if bone.name in ('ひじ.'+s,'手首.'+s,'手捩.'+s):return 'fore.'+s
            if bone.name=='腕.'+s:return 'upper.'+s
        bone=bone.parent
    return 'core'
def checks(points,local_faces,full=False):
    bvh=BVHTree.FromPolygons(points.tolist(),local_faces.tolist(),all_triangles=True);count=0
    for i,j in bvh.overlap(tree):
        if triangle_crosses([Vector(v) for v in points[local_faces[i]]],[Vector(v) for v in skin[sf[j]]]):
            count+=1
            if not full:return 1
    if count:return count
    for point in points[::max(1,len(points)//60)]:
        q,n,i,d=tree.find_nearest(Vector(point))
        if d<.08 and (Vector(point)-q).dot(n)<-.00005 and inside_votes(tree,Vector(point)):return 1
    return 0
report={'status':'COMPONENT_CONTACT_FIT_REQUIRES_AUDIT','frame':325,'body_coordinates_changed':False,'components':[]}
for serial,c in enumerate(components):
    ids=np.flatnonzero(labels==c);selected=np.flatnonzero(labels[faces[:,0]]==c);fs=faces[selected];mapping={int(v):i for i,v in enumerate(ids)};local_faces=np.array([[mapping[int(v)] for v in f] for f in fs]);points=co[ids].copy();before=checks(points,local_faces)
    if not before:continue
    kinds=[kind(dominant[i]) for i in ids];part=max(set(kinds),key=kinds.count);origin=core_origin.copy();axis=core_axis.copy();fore=part.startswith('fore')
    if part.startswith(('upper','fore')):
        s=part[-1];origin=head(('ひじ.' if fore else '腕.')+s);axis=head(('手首.' if fore else 'ひじ.')+s)-origin;axis/=np.linalg.norm(axis)
    along=(points-origin)@axis;radial=points-origin-along[:,None]*axis;mean=radial.mean(axis=0);direction=mean/np.linalg.norm(mean) if np.linalg.norm(mean)>.001 else np.zeros(3);protection=np.array([dominant[i].startswith(HAND_PREFIX[1:]) for i in ids]);taper=np.ones(len(ids))
    if fore:
        span=np.linalg.norm(head('手首.'+part[-1])-origin);t=np.clip((1.10-along/span)/.30,0.,1.);taper=t*t*(3-2*t);taper[protection]=0.
    possibilities=[]
    for scale in (1.,1.04,1.08,1.12,1.18,1.25,1.35,1.5,1.7,2.):
        for shift in (0.,.005,.01,.02,.035,.05,.07):
            for mode in ('outward','axial','axial_negative'):
                angles=(0.,15.,-15.,30.,-30.,60.,-60.,90.,-90.) if part.startswith('upper') else (0.,15.,-15.,30.,-30.) if fore else (0.,)
                for angle in angles:
                    rotation=np.array(Quaternion(Vector(axis),np.deg2rad(angle)).to_matrix());rotated=(points-origin)@rotation.T+origin;delta=(rotated-points)*taper[:,None]+radial*(scale-1)*taper[:,None]+(axis if mode=='axial' else -axis if mode=='axial_negative' else direction)*shift*taper[:,None];movement=np.linalg.norm(delta,axis=1).max()
                    if movement>(.6 if part.startswith('upper') else .16):continue
                    possibilities.append((float(movement)+.015*(scale-1),scale,shift,mode,delta,angle))
    best=None
    for cost,scale,shift,mode,delta,angle in sorted(possibilities,key=lambda v:v[0]):
        if not checks(points+delta,local_faces):best=(scale,shift,mode,delta,angle);break
    if best is not None:co[ids]=points+best[3]
    row={'component':int(c),'vertices':len(ids),'part':part,'dominant_bones':Counter(dominant[i] for i in ids).most_common(8),'source_rest_bounds_m':[rest[ids].min(axis=0).tolist(),rest[ids].max(axis=0).tolist()],'materials':sorted(set(names[int(m)] for m in materials[selected])),'resolved':best is not None,'scale':best[0] if best else None,'shift_m':best[1] if best else None,'shift_mode':best[2] if best else None,'roll_degrees':best[4] if best else None,'max_displacement_m':float(np.linalg.norm(co[ids]-points,axis=1).max())};report['components'].append(row);print('COHERENT_GARMENT_PART',serial,json.dumps(row,ensure_ascii=False),flush=True);(out/'component_fit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
modifier=install(cloth,co,325);bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);bpy.ops.object.modifier_move_to_index(modifier=modifier.name,index=list(cloth.modifiers).index(sub));sub.show_viewport=True;sub.show_render=True;sub.levels=1;sub.render_levels=1;report['unresolved_components']=sum(not r['resolved'] for r in report['components']);report['max_displacement_m']=float(np.linalg.norm(co-source,axis=1).max());scene.frame_start=325;scene.frame_end=325;bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_Components325.blend'),compress=True);(out/'component_fit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
