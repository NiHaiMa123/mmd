"""Exercise the shipped experimental API on an unrelated two-bone English rig."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'outputs/local_volume_skin_contract';out.mkdir(parents=True,exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--snapshot');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if a.snapshot:
 with zipfile.ZipFile(a.snapshot) as z:z.extractall(out/'snapshot')
 sys.path.insert(0,str(out/'snapshot/addon'))
else:sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.local_volume_skin import bake_local_volume_skin
from animation_contact_tools.surface import coords
from animation_contact_tools.track import fcurves
bpy.ops.wm.read_factory_settings(use_empty=True)
ad=bpy.data.armatures.new('EnglishRig');arm=bpy.data.objects.new('EnglishRig',ad);bpy.context.scene.collection.objects.link(arm);arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT')
upper=ad.edit_bones.new('Upper');upper.head=(0,0,0);upper.tail=(0,.5,0);tip=ad.edit_bones.new('Tip');tip.head=(0,.5,0);tip.tail=(0,1,0);tip.parent=upper;bpy.ops.object.mode_set(mode='OBJECT')
vertices=[(x,y,z) for y in (.3,.4,.5,.6,.7) for x,z in ((-.05,-.04),(.05,-.04),(.05,.04),(-.05,.04))];faces=[(0,3,2,1),(16,17,18,19)]
for ring in range(4):
 for k in range(4):faces.append((4*ring+k,4*ring+(k+1)%4,4*(ring+1)+(k+1)%4,4*(ring+1)+k))
data=bpy.data.meshes.new('JointSkin');data.from_pydata(vertices,[],faces);mesh=bpy.data.objects.new('JointSkin',data);bpy.context.scene.collection.objects.link(mesh);groups=[mesh.vertex_groups.new(name=n) for n in ('Upper','Tip')]
for i,(_,y,_) in enumerate(vertices):
 weight=np.clip((y-.3)/.4,0,1);groups[0].add([i],float(1-weight),'REPLACE');groups[1].add([i],float(weight),'REPLACE')
modifier=mesh.modifiers.new('LBS','ARMATURE');modifier.object=arm;mesh.shape_key_add(name='Basis');shape=mesh.shape_key_add(name='Morph');shape.data[7].co.x+=.015;shape.value=.35
bone=arm.pose.bones['Tip'];bone.rotation_mode='XYZ'
for frame,angle in ((1,0.),(3,1.2),(5,0.)):
 bone.rotation_euler.z=angle;bone.keyframe_insert('rotation_euler',frame=frame)
def raw_hash():
 h=hashlib.sha256()
 for key in data.shape_keys.key_blocks:
  values=np.array([tuple(v.co) for v in key.data],dtype='<f4');h.update(values.tobytes())
 for v in data.vertices:
  for g in v.groups:h.update(f'{v.index}:{g.group}:{g.weight}'.encode())
 return h.hexdigest()
before=raw_hash();action=arm.animation_data.action;source_keys=[[(tuple(k.co),k.interpolation) for k in curve.keyframe_points] for curve in fcurves(action)];ids=np.arange(4,16);mask=np.linspace(.2,1.,len(ids));frames=[1.5,2.,2.5,3.,3.5,4.,4.5];expected={};outside=np.array([i for i in range(len(vertices)) if i not in ids])
for frame in frames:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();linear=coords(mesh);modifier.use_deform_preserve_volume=True;bpy.context.view_layer.update();dual=coords(mesh);modifier.use_deform_preserve_volume=False;bpy.context.view_layer.update();t=np.clip(min(frame-2,4-frame)/.5,0,1);t=t*t*(3-2*t);value=linear.copy();value[ids]+=.8*t*mask[:,None]*(dual[ids]-linear[ids]);expected[frame]=value
result=bake_local_volume_skin(mesh,arm,ids,mask,'Tip',out/'skin.pc2',first=2,last=4,step=.125,blend=.8,fade=.5)
assert result['maximum_skin_displacement_m']>1e-4
bpy.ops.wm.save_as_mainfile(filepath=str(out/'EnglishJoint.blend'));bpy.ops.wm.open_mainfile(filepath=str(out/'EnglishJoint.blend'),use_scripts=False);mesh=bpy.data.objects['JointSkin'];arm=bpy.data.objects['EnglishRig'];data=mesh.data;modifier=next(m for m in mesh.modifiers if m.type=='ARMATURE');assert not modifier.use_deform_preserve_volume;assert raw_hash()==before
assert [[(tuple(k.co),k.interpolation) for k in c.keyframe_points] for c in fcurves(arm.animation_data.action)]==source_keys
maximum=0.
for frame in frames:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();error=float(np.max(np.abs(coords(mesh)-expected[frame])));maximum=max(maximum,error);assert error<2e-6,(frame,error)
summary=dict(status='SHIPPED_EXPERIMENT_ENGLISH_JOINT_BLEND_REOPEN_AND_SOURCE_PRESERVATION_PASS',maximum_error_m=maximum,source_weights_shapes_and_action_preserved=True,source_DQ_disabled=True,outside_window_original=True,metadata=result)
(out/'report.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print('LOCAL_VOLUME_CONTRACT',json.dumps(summary),flush=True)
