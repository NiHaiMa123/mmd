"""Fit the intact outfit with smooth bone-domain scale/translation fields."""
import argparse,json,subprocess,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import SKIN,HAND_PREFIX,triangle_crosses,inside_votes
from mmd_outfit.outfit_arap_contact import intersection_midpoint
from mmd_outfit.contact_position_override import install
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--iterations',type=int,default=25);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.show_viewport=False;sub.show_render=False
def capture(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles]);mats=np.array([t.material_index for t in mesh.loop_triangles]);groups=[[(g.group,g.weight) for g in v.groups] for v in mesh.vertices];names=[m.name for m in mesh.materials];ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces,mats,groups,names
skin,sf,sm,_,materials=capture(body);sf=sf[np.array([materials[int(i)] in SKIN for i in sm])];bt=BVHTree.FromPolygons(skin.tolist(),sf.tolist(),all_triangles=True);normals=np.cross(skin[sf[:,1]]-skin[sf[:,0]],skin[sf[:,2]]-skin[sf[:,0]]);normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-14);source,faces,_,groups,_=capture(cloth)
domains=['下半身','上半身','上半身2','上半身3','首','腕.L','ひじ.L','手首.L','腕.R','ひじ.R','手首.R'];domains=[name for name in domains if name in arm.pose.bones];dof=5*len(domains);names={g.index:g.name for g in cloth.vertex_groups if g.name in arm.pose.bones};weights=np.zeros((len(source),len(domains)));fixed=np.zeros(len(source),dtype=bool)
for i,gs in enumerate(groups):
    dominant=max(((w,names[g]) for g,w in gs if g in names),default=(0.,''))[1];fixed[i]=dominant.startswith(HAND_PREFIX[1:])
    for g,w in gs:
        if g not in names:continue
        bone=arm.pose.bones[names[g]]
        while bone and bone.name not in domains:bone=bone.parent
        if bone:weights[i,domains.index(bone.name)]+=w
    if weights[i].sum()<1e-10:weights[i,0]=1.
weights/=weights.sum(axis=1,keepdims=True);J=np.zeros((len(source),3,dof));world=np.array(arm.matrix_world)
for j,name in enumerate(domains):
    bone=arm.pose.bones[name];origin=np.array(arm.matrix_world@bone.head);axis=np.array(arm.matrix_world@bone.tail)-origin;axis/=np.linalg.norm(axis);reference=np.array([1.,0,0]) if abs(axis[0])<.8 else np.array([0.,1,0]);v=reference-axis*np.dot(reference,axis);v/=np.linalg.norm(v);w=np.cross(axis,v);relative=source-origin;W=weights[:,j,None];J[:,:,5*j]=W*((relative@v)[:,None]*v);J[:,:,5*j+1]=W*((relative@w)[:,None]*w)
    for k,vector in enumerate((v,w,axis),2):J[:,:,5*j+k]=W*vector
J[fixed]=0.;flat=J.reshape(-1,dof);H=flat.T@flat/len(source)+np.diag(np.tile([.00001,.00001,.001,.001,.001],len(domains)));parameters=np.zeros(dof);lower=np.tile([-.1,-.1,-.07,-.07,-.07],len(domains));upper=np.tile([1.,1.,.07,.07,.07],len(domains));x=source.copy();pool={};history=[];previous=np.arange(len(source));last_inside=[]
for iteration in range(a.iterations):
    ct=BVHTree.FromPolygons(x.tolist(),faces.tolist(),all_triangles=True);pairs=[(i,j) for i,j in ct.overlap(bt) if triangle_crosses([Vector(v) for v in x[faces[i]]],[Vector(v) for v in skin[sf[j]]])];active=np.arange(len(source)) if iteration%5==0 else np.unique(np.r_[previous,faces[np.array([i for i,j in pairs],dtype=int)].reshape(-1)]);inside=[]
    for i in active:
        if fixed[i]:continue
        q,n,j,d=bt.find_nearest(Vector(x[i]))
        if q is not None and d<.10 and (Vector(x[i])-q).dot(n)<-.00001 and inside_votes(bt,Vector(x[i])):pool[('v',int(i),j)]=(np.array(n)@J[i],float(np.dot(q,n))+.002-float(np.dot(source[i],n)));inside.append(i)
    for i,j in pairs:
        ids=faces[i];u,v,w=x[ids];point=intersection_midpoint(x[ids],skin[sf[j]]);uv=np.linalg.lstsq(np.column_stack((v-u,w-u)),point-u,rcond=None)[0];bary=np.maximum(0.,[1-uv.sum(),uv[0],uv[1]]);bary/=max(sum(bary),1e-12);pool[('f',i,j)]=(normals[j]@np.einsum('i,ijk->jk',bary,J[ids]),float(normals[j]@skin[sf[j,0]])+.002-float(normals[j]@(bary@source[ids])))
    previous=np.unique(np.r_[inside,faces[np.array([i for i,j in pairs],dtype=int)].reshape(-1)]).astype(int);last_inside=inside
    if not pairs and not inside:history.append({'iteration':iteration,'crossings':0,'inside_vertices':0});break
    A=np.array([item[0] for item in pool.values()]);b=np.array([item[1] for item in pool.values()]);np.savez_compressed(out/'constraints.npz',H=H,A=A,b=b,parameters=parameters,lower=lower,upper=upper);result=out/'step.npz';run=subprocess.run([str(ROOT/'tools/contact_stack/venv/Scripts/python.exe'),str(ROOT/'scripts/solve_garment_field.py'),'--input',str(out/'constraints.npz'),'--output',str(result)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if run.returncode:raise RuntimeError(run.stderr.decode(errors='replace'))
    with np.load(result) as z:parameters=z['parameters'].copy();violation=float(z['violation']);message=str(z['message'])
    x=source+np.einsum('ijk,k->ij',J,parameters);row={'iteration':iteration,'crossings':len(pairs),'inside_vertices':len(inside),'constraints':len(b),'violation_m':violation,'max_displacement_m':float(np.linalg.norm(x-source,axis=1).max()),'solver':message};history.append(row);(out/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8');print('SKELETAL_GARMENT_FIELD',json.dumps(row),flush=True)
modifier=install(cloth,x,325);bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);bpy.ops.object.modifier_move_to_index(modifier=modifier.name,index=list(cloth.modifiers).index(sub));sub.show_viewport=True;sub.show_render=True;sub.levels=1;sub.render_levels=1;scene.frame_start=325;scene.frame_end=325;report={'status':'SKELETAL_GARMENT_FIELD_REQUIRES_INDEPENDENT_AUDIT','domains':domains,'parameters':parameters.tolist(),'history':history,'last_inside_vertices':len(last_inside),'frame':325,'new_physical_solve':False,'body_mesh_modified':False};(out/'field_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_Field325.blend'),compress=True)
