"""Export exact animated skin and explicit hair rest/anchor data, without dynamics."""
import argparse,json,sys,time
from pathlib import Path
import numpy as np
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--initial',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True);p.add_argument('--first',type=float,default=1);p.add_argument('--last',type=float,default=450);p.add_argument('--step',type=float,default=.25);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(exist_ok=True,parents=True)
if (out/'export_complete.json').exists():raise RuntimeError('Use fresh export directory')
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False);s=bpy.context.scene;profile=json.loads(Path(a.profile).read_text('utf8'));m=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']]
with np.load(a.initial) as z:d={k:z[k] for k in z.files}
ids=d['ids'];initial=d.get('corrected_initial_world',d.get('coordinates'));assert initial is not None
skin,skinfaces,meta=build_exact_skin_topology(m,arm,profile,triangulate=True,include_face_sources=True);np.save(out/'real_body_faces.npy',(~np.asarray(meta.pop('closure_face_mask'),dtype=bool)).astype(np.int32));np.save(out/'body_faces.npy',np.asarray(skinfaces,dtype=np.int32));np.save(out/'skin_ids.npy',skin);np.save(out/'hair_ids.npy',ids)
roles=list(profile['bone_roles']);group_names={g.index:g.name for g in m.vertex_groups};bone_role={name:i for i,role in enumerate(roles) for name in profile['bone_roles'][role]};skin_weights=np.zeros((len(skin),len(roles)))
for j,i in enumerate(skin):
 for g in m.data.vertices[i].groups:
  role=bone_role.get(group_names[g.group])
  if role is not None:skin_weights[j,role]+=g.weight
np.save(out/'body_face_role.npy',skin_weights[np.asarray(skinfaces)].sum(1).argmax(1).astype(np.int32));(out/'body_role_names.json').write_text(json.dumps(roles,ensure_ascii=False),encoding='utf8')
lookup=np.full(len(m.data.vertices),-1,dtype=int);lookup[ids]=np.arange(len(ids));m.data.calc_loop_triangles();hairfaces=np.array([lookup[list(t.vertices)] for t in m.data.loop_triangles if np.all(lookup[list(t.vertices)]>=0)]);edges=np.array([lookup[list(e.vertices)] for e in m.data.edges if np.all(lookup[list(e.vertices)]>=0)]);np.save(out/'hair_faces.npy',hairfaces.astype(np.int32));np.save(out/'hair_edges.npy',edges.astype(np.int32));np.save(out/'hair_initial.npy',initial.astype(np.float32));np.save(out/'hair_original.npy',d.get('original_initial_world',d.get('original')).astype(np.float32))
anchors=profile['root_hair_anchor_bones'];gn={g.index:g.name for g in m.vertex_groups};weights=np.array([[sum(g.weight for g in m.data.vertices[i].groups if gn[g.group]==name) for name in anchors] for i in ids]);np.save(out/'anchor_weights.npy',weights.astype(np.float32));hard=np.array(d.get('same_true_hard_root_mask',d.get('true_hard_roots')),dtype=bool);np.save(out/'hard_roots.npy',hard)
# Distance across adjacent triangles is a rest-curvature constraint, not a seam weld.
from collections import defaultdict
adj=defaultdict(list)
for tri in hairfaces:
 for aa,bb,cc in [(tri[0],tri[1],tri[2]),(tri[1],tri[2],tri[0]),(tri[2],tri[0],tri[1])]:adj[tuple(sorted([int(aa),int(bb)]))].append(int(cc))
bend=np.array([v for v in adj.values() if len(v)==2 and v[0]!=v[1]],dtype=np.int32);np.save(out/'bend_pairs.npy',bend)
frames=np.arange(a.first,a.last+a.step*.1,a.step);body=np.lib.format.open_memmap(out/'body.npy',mode='w+',dtype='<f4',shape=(len(frames),len(skin),3));heads=np.lib.format.open_memmap(out/'anchors.npy',mode='w+',dtype='<f8',shape=(len(frames),len(anchors),4,4));start=time.monotonic()
for k,f in enumerate(frames):
 s.frame_set(int(f),subframe=float(f%1));bpy.context.view_layer.update();body[k]=coords(m)[skin]
 for j,name in enumerate(anchors):heads[k,j]=np.array(arm.matrix_world@arm.pose.bones[name].matrix)
 if k%120==0:
  body.flush();heads.flush();(out/'export_progress.json').write_text(json.dumps(dict(frame=float(f),samples=k+1,total=len(frames),elapsed_s=time.monotonic()-start)),encoding='utf8');print('EXACT_EXPORT',k,float(f),flush=True)
body.flush();heads.flush();manifest=dict(schema=1,source_blend=a.source,initial_file=a.initial,rig_profile=a.profile,frames=[a.first,a.last],sample_step=a.step,fps=30,samples=len(frames),hair_vertices=len(ids),hair_faces=len(hairfaces),skin_vertices=len(skin),skin_faces=len(skinfaces),true_hard_roots=int(hard.sum()),anchor_bones=anchors,anchor_policy='original head/neck weights on corrected initial locations',skin_topology=meta,physics_started=False,elapsed_s=time.monotonic()-start)
(out/'export_complete.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print('EXACT_EXPORT_DONE',json.dumps(manifest,ensure_ascii=False),flush=True)

