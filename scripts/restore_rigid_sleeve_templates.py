"""Fit intact sleeve templates in upper-arm frames, instead of crumpling them."""
import argparse,sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import SKIN,triangle_crosses,inside_votes
from mmd_outfit.contact_position_override import install
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);cloth=bpy.data.objects['Cloth'];body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm']
for m in cloth.modifiers:
    m.show_viewport=m.type in ('ARMATURE','SUBSURF');m.show_render=m.show_viewport
sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.show_viewport=False;sub.show_render=False
def capture(obj,skin=False):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles if not skin or mesh.materials[t.material_index].name in SKIN|{'Nails'}]);ev.to_mesh_clear();mat=np.array(obj.matrix_world);return co@mat[:3,:3].T+mat[:3,3],faces
skin,sf=capture(body,True);tree=BVHTree.FromPolygons(skin.tolist(),sf.tolist(),all_triangles=True);co,faces=capture(cloth);rest=np.array([v.co[:] for v in cloth.data.vertices]);_,weld=np.unique(np.rint(rest/1e-6).astype(np.int64),axis=0,return_inverse=True);parent=np.arange(weld.max()+1)
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for f in weld[faces]:
    for i in f[1:]:parent[root(int(i))]=root(int(f[0]))
labels=np.array([root(int(i)) for i in weld]);cm=np.array(cloth.matrix_world);rest=rest@cm[:3,:3].T+cm[:3,3];aw=np.array(arm.matrix_world);report={'status':'RIGID_SLEEVE_TEMPLATES_REQUIRES_AUDIT','frame':325,'source_body_changed':False,'new_physics':False,'sleeves':{}}
def bad(points,fs):
    bvh=BVHTree.FromPolygons(points.tolist(),fs.tolist(),all_triangles=True)
    for i,j in bvh.overlap(tree):
        if triangle_crosses([Vector(p) for p in points[fs[i]]],[Vector(p) for p in skin[sf[j]]]):return True
    active=points[np.unique(fs)]
    for point in active[::max(1,len(active)//150)]:
        q,n,j,d=tree.find_nearest(Vector(point))
        if d<.08 and (Vector(point)-q).dot(n)<-.0001 and inside_votes(tree,Vector(point)):return True
    return False
for side,component in [('L',14732),('R',4311)]:
    ids=np.flatnonzero(labels==component);which=np.flatnonzero((labels[faces[:,0]]==component)&np.all(rest[faces,2]>1.10,axis=1));lookup=np.full(len(co),-1,dtype=int);lookup[ids]=np.arange(len(ids));fs=lookup[faces[which]];bone=arm.pose.bones['腕.'+side];begin=aw[:3,:3]@np.array(bone.bone.head_local)+aw[:3,3];end=aw[:3,:3]@np.array(arm.data.bones['ひじ.'+side].head_local)+aw[:3,3];axis=end-begin;axis/=np.linalg.norm(axis);delta=aw@np.array(bone.matrix)@np.linalg.inv(np.array(bone.bone.matrix_local))@np.linalg.inv(aw);p=rest[ids];along=(p-begin)@axis;radial=p-begin-along[:,None]*axis;possibilities=[];blend=np.clip((rest[ids,2]-1.02)/.06,0,1);blend=blend*blend*(3-2*blend)
    for length in (1.,.95,.9,.85,.8,.75,.7):
        for width in (1.,1.08,1.16,1.25,1.35,1.5,1.7):
            for shift in (0.,.005,.01,.02,.03,.04,-.005,-.01):
                for angle in (0.,15.,-15.,30.,-30.):
                    r=np.array(Quaternion(Vector(axis),np.deg2rad(angle)).to_matrix());candidate=begin+(along*length+shift)[:,None]*axis+(radial@r.T)*width;candidate=candidate@delta[:3,:3].T+delta[:3,3];candidate=co[ids]+(candidate-co[ids])*blend[:,None];cost=abs(1-length)*.1+abs(1-width)*.05+abs(shift)+abs(angle)*.0001;possibilities.append((cost,length,width,shift,angle,candidate))
    solution=None
    for cost,length,width,shift,angle,points in sorted(possibilities,key=lambda x:x[0]):
        if not bad(points,fs):solution=(length,width,shift,angle,points);break
    if solution:co[ids]=solution[-1]
    row={'component':component,'vertices':len(ids),'checked_faces':len(fs),'scope':'upper puff only; tail transition unaccepted','resolved':solution is not None,'axial_scale':solution[0] if solution else None,'radial_scale':solution[1] if solution else None,'axial_shift_m':solution[2] if solution else None,'roll_degrees':solution[3] if solution else None};report['sleeves'][side]=row;print('RIGID_SLEEVE_TEMPLATE',json.dumps(row),flush=True)
mod=install(cloth,co,325);bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=list(cloth.modifiers).index(sub));sub.show_viewport=True;sub.show_render=True;sub.levels=2;sub.render_levels=2;scene.frame_start=325;scene.frame_end=325;bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_RigidSleeveTemplates325.blend'),compress=True);(out/'template_fit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
