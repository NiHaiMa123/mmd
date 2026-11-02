import bpy,json,sys,numpy as np
from pathlib import Path
from mathutils.bvhtree import BVHTree
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex';p=base/'jiggle_physics_20261031/native_outside20'
bpy.ops.wm.open_mainfile(filepath=str(p/'完整角色_Jiggle原版_原生表面约束_15秒.blend'),load_ui=False,use_scripts=False)
m=bpy.data.objects['东雪莲x达妮娅_素体'];body=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部'];md=next(md for md in m.modifiers if md.type=='SHRINKWRAP');z=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');ids=z['ids'];active=ids[~z['same_true_hard_root_mask']];rows=[]
for frame in [1,204]:
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();wrapped=coords(m)[active];md.show_viewport=False;bpy.context.view_layer.update();original=coords(m)[active];target=coords(body)
 dg=bpy.context.evaluated_depsgraph_get();ev=body.evaluated_get(dg);mesh=ev.to_mesh();faces=[tuple(poly.vertices) for poly in mesh.polygons];ev.to_mesh_clear()
 tree=BVHTree.FromPolygons(target.tolist(),faces);nearest=[tree.find_nearest(Vector(pt)) for pt in original];dots=np.array([np.dot(pt-np.array(hit[0]),np.array(hit[1])) for pt,hit in zip(original,nearest)]);displacement=np.linalg.norm(wrapped-original,axis=1);top=np.argsort(displacement)[-5:]
 field=ClosedColliderField(target,faces);signed,_=field(original[top]);examples=[]
 real=np.load(base/'fullhair_repro_20261030/input_body_aware/real_body_faces.npy').astype(bool)
 for j,dist in zip(top,signed):examples.append(dict(source_id=int(active[j]),nearest_is_real_skin=bool(real[nearest[j][2]]),native_normal_dot=float(dots[j]),ray_distance=float(dist),nearest_distance=float(nearest[j][3]),displacement=float(displacement[j]),original=original[j].tolist(),wrapped=wrapped[j].tolist(),target_point=list(nearest[j][0]),normal=list(nearest[j][1])))
 rows.append(dict(frame=frame,actor_matrix=list(map(list,m.matrix_world)),target_matrix=list(map(list,body.matrix_world)),native_negative_count=int((dots<0).sum()),moved_count=int((displacement>1e-6).sum()),examples=examples));md.show_viewport=True;bpy.context.view_layer.update()
(p/'native_sign_diagnostic.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8');print(json.dumps(rows,ensure_ascii=False),flush=True)
