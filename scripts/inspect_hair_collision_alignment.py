import bpy,json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex';p=base/'jiggle_physics_20261031/candidate15_convex'
bpy.ops.wm.open_mainfile(filepath=str(p/'完整角色_Jiggle配置_未烘焙.blend'),load_ui=False,use_scripts=False);bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=m.find_armature();x=coords(m);ids=np.load(base/'fullhair_repro_20261030/input_body_aware/hair_ids.npy');field=ClosedColliderField(np.load(base/'fullhair_repro_20261030/input_body_aware/body.npy',mmap_mode='r')[0],np.load(base/'fullhair_repro_20261030/input_body_aware/body_faces.npy'))
rows=[]
for b in arm.pose.bones:
 if not b.name.startswith(('FrontHair','Sidehair')) or b.name not in m.vertex_groups:continue
 gi=m.vertex_groups[b.name].index;sel=[(int(i),sum(g.weight for g in m.data.vertices[int(i)].groups if g.group==gi)) for i in ids];sel=[(i,w) for i,w in sel if w>.2]
 if not sel:continue
 points=x[[i for i,w in sel]];center=np.average(points,axis=0,weights=[w for i,w in sel]);head=np.array(arm.matrix_world@b.head);tail=np.array(arm.matrix_world@b.tail);dist,_=field(np.array([head,tail,center]))
 rows.append(dict(bone=b.name,head_body_distance_m=float(dist[0]),tail_body_distance_m=float(dist[1]),weighted_mesh_center_body_distance_m=float(dist[2]),mesh_center_to_bone_head_m=float(np.linalg.norm(center-head)),render_radius95_from_tail_m=float(np.quantile(np.linalg.norm(points-tail,axis=1),.95))))
(p/'collision_alignment.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8');print(json.dumps(rows,ensure_ascii=False),flush=True)
