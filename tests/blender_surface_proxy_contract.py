"""English-named rig: clean envelope, source preservation and scaled head motion."""
import json, sys
from pathlib import Path
import bpy, numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.mesh_hair_proxy import simulation_anchor,build_loft_proxy,display_positions_world,build_proxy
bpy.ops.wm.read_factory_settings(use_empty=True)
data=bpy.data.armatures.new('RigData');arm=bpy.data.objects.new('Rig',data);bpy.context.scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bone=data.edit_bones.new('Head');bone.head=(2,-1,3);bone.tail=(2,-1,3.2);bpy.ops.object.mode_set(mode='OBJECT');bpy.context.view_layer.update()
head0=np.array(arm.matrix_world@arm.pose.bones['Head'].matrix)
points=[];weights=[];faces=[]
for k in range(10):
 for j in range(8):
  angle=j*2*np.pi/8;points.append((2+.025*np.cos(angle),-1+.015*np.sin(angle),3.05-.04*k));weights.append(1. if k==0 else .4 if k==1 else 0.)
for k in range(9):
 for j in range(8):
  aa=k*8+j;bb=k*8+(j+1)%8;cc=(k+1)*8+(j+1)%8;dd=(k+1)*8+j;faces.extend([(aa,bb,cc),(aa,cc,dd)])
points=np.array(points);anchor,follow,origin=simulation_anchor(arm,'Head',10.)
proxy,display,info=build_loft_proxy((points-origin)*10,faces,weights,arm,'Head',margin=.01,anchor_target=anchor,attachment_mode='root_only')
assert info['initial_nonadjacent_proxy_intersections']==0 and info['boundary_edges']==0
assert info['partial_attachment_count']==0
np.testing.assert_allclose(display_positions_world(display)/10+origin,points,atol=1e-5)
original=np.array([v.co[:] for v in display.data.vertices])
arm.pose.bones['Head'].location=(.1,.04,-.03);arm.pose.bones['Head'].rotation_mode='XYZ';arm.pose.bones['Head'].rotation_euler=(.2,-.3,.4);bpy.context.view_layer.update()
delta=np.array(arm.matrix_world@arm.pose.bones['Head'].matrix)@np.linalg.inv(head0)
expected=points@delta[:3,:3].T+delta[:3,3]
np.testing.assert_allclose(display_positions_world(display)/10+origin,expected,atol=1e-5)
np.testing.assert_array_equal(np.array([v.co[:] for v in display.data.vertices]),original)
# Two crossing triangles must never become a physical surface silently.
try:build_proxy(np.array([(0,0,0),(1,0,0),(0,1,0),(.25,.25,-1),(.25,.25,1),(.75,.75,0)]),np.array([(0,1,2),(3,4,5)]),np.ones(6),arm,'Head')
except ValueError as e:assert 'initial intersections' in str(e),str(e)
else:raise AssertionError('Intersecting physical surface was accepted')
out=ROOT/'outputs/surface_proxy_contract';out.mkdir(parents=True,exist_ok=True);result=dict(status='CLEAN_ENVELOPE_ATTACHMENT_SCALE_AND_INTERSECTION_GUARD_PASS',proxy=info,original_rig_bones=list(arm.pose.bones.keys()))
(out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('SURFACE_PROXY_CONTRACT',json.dumps(result),flush=True)
