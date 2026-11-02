"""A dropped sphere must actually fall and land after repairing a missing world."""
import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.physics_world import ensure_world_members
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-.05));floor=bpy.context.object;floor.scale=(2,2,.1);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);bpy.ops.rigidbody.object_add();floor.rigid_body.type='PASSIVE'
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.1,location=(0,0,1));ball=bpy.context.object;bpy.ops.rigidbody.object_add();ball.rigid_body.collision_shape='SPHERE';ball.rigid_body.use_margin=True;ball.rigid_body.collision_margin=.001
world=bpy.context.scene.rigidbody_world;world.collection=None;world.constraints=None
assert ball.rigid_body is not None and world.collection is None
repair=ensure_world_members([floor,ball]);assert repair['world_rigids_relinked']==2
world.enabled=True;world.substeps_per_frame=10;world.solver_iterations=20;world.point_cache.frame_end=60
zs=[]
for frame in range(1,61):
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();zs.append(float(ball.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation.z))
assert min(zs)<.12 and .085<zs[-1]<.12,zs[-1]
result={'status':'MISSING_WORLD_REPAIRED_AND_FALLING_SPHERE_CONTACT_PASS','membership':repair,'initial_z':zs[0],'final_z':zs[-1],'mmd_tools_required':False}
out=ROOT/'outputs/physics_world_contract';out.mkdir(parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('PHYSICS_WORLD_CONTRACT',json.dumps(result),flush=True)
