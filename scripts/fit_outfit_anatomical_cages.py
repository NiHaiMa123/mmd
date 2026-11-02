"""One-pose garment cage fitting, preserving source UVs and material layers."""
import argparse,json,sys,subprocess
from pathlib import Path
from collections import Counter
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import SKIN,ARM_PREFIX
from mmd_outfit.contact_position_override import install
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);cloth=bpy.data.objects['Cloth'];body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.show_viewport=False;sub.show_render=False
def capture(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles]);mats=np.array([t.material_index for t in mesh.loop_triangles]);ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces,mats
co,faces,_=capture(cloth);source=co.copy();skin,sf,sm=capture(body);rest=np.array([v.co[:] for v in cloth.data.vertices]);_,weld=np.unique(np.rint(rest/1e-6).astype(np.int64),axis=0,return_inverse=True);parent=np.arange(weld.max()+1)
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for f in weld[faces]:
    for i in f[1:]:parent[root(int(i))]=root(int(f[0]))
labels=np.array([root(int(i)) for i in weld]);bnames={g.index:g.name for g in body.vertex_groups if g.name in arm.data.bones};dominant=[max(((g.weight,bnames[g.group]) for g in v.groups if g.group in bnames),default=(0.,''))[1] for v in body.data.vertices];used=np.zeros(len(skin),dtype=bool);used[np.unique(sf[np.array([body.data.materials[int(m)].name in SKIN for m in sm])])]=True
report={'status':'STATIC_CAGE_FIT_REQUIRES_AUDIT','frame':325,'body_changed':False,'physics':False,'pieces':[]}
for part,components in [('core',[13948,5977]),('arm.L',[14732]),('arm.R',[4311])]:
    ids=np.flatnonzero(np.isin(labels,components));bone=arm.pose.bones['上半身3' if part=='core' else '腕.'+part[-1]];matrix=np.array(arm.matrix_world@bone.matrix@bone.bone.matrix_local.inverted());inv=np.linalg.inv(matrix)
    if part=='core':selected=np.array([used[i] and n.startswith(('上半身','下半身','腰','胸','乳','腹','おっぱい','首')) for i,n in enumerate(dominant)])
    else:selected=np.array([used[i] and n.endswith('.'+part[-1]) and n.startswith(ARM_PREFIX) for i,n in enumerate(dominant)])
    points=co[ids]@inv[:3,:3].T+inv[:3,3];bodypoints=skin[selected]@inv[:3,:3].T+inv[:3,3]
    # The arm's rest axis becomes z for the cylindrical cage.
    rotation=np.eye(3);origin=np.zeros(3)
    if part!='core':
        begin=np.array(bone.bone.head_local);end=np.array(arm.data.bones['ひじ.'+part[-1]].head_local);axis=end-begin;axis/=np.linalg.norm(axis);x=np.cross(axis,[0,1,0]);x/=np.linalg.norm(x);y=np.cross(axis,x);rotation=np.column_stack((x,y,axis));origin=begin;points=(points-origin)@rotation;bodypoints=(bodypoints-origin)@rotation
        # Upper-arm fitting only. Forearm and hanging tails are distinct domains.
        span=np.linalg.norm(end-begin);bodypoints=bodypoints[(bodypoints[:,2]>=-.01)&(bodypoints[:,2]<=span+.01)];eligible=(rest[ids,2]>1.08);ids=ids[eligible];points=points[eligible]
    payload=out/(part+'.npz');result=out/(part+'_fit.npz');np.savez_compressed(payload,skin=bodypoints,points=points);run=subprocess.run([str(ROOT/'tools/contact_stack/venv/Scripts/python.exe'),str(ROOT/'scripts/solve_radial_garment_cage.py'),'--input',str(payload),'--output',str(result)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if run.returncode:raise RuntimeError(run.stderr.decode(errors='replace'))
    with np.load(result) as z:points=z['points'].copy();dr=z['displacement'].copy()
    if part!='core':points=points@rotation.T+origin
    co[ids]=points@matrix[:3,:3].T+matrix[:3,3];row={'part':part,'vertices':len(ids),'maximum_radial_change_m':float(dr.max())};report['pieces'].append(row);print('ANATOMICAL_CAGE',json.dumps(row),flush=True)
mod=install(cloth,co,325);bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=list(cloth.modifiers).index(sub));sub.show_viewport=True;sub.show_render=True;sub.levels=2;sub.render_levels=2;report['max_displacement_m']=float(np.linalg.norm(co-source,axis=1).max());bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_Cages325.blend'),compress=True);(out/'cage_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
