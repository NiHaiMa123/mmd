"""Rebuild angle-dependent joint skinning after the automatic arm route."""
import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions
from animation_contact_tools.local_volume_skin import bake_local_volume_skin
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True);p.add_argument('--first',type=float);p.add_argument('--last',type=float);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'prepared.json').exists():raise RuntimeError('Use fresh directory')
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False);profile=json.loads(Path(a.profile).read_text('utf8'));m=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];s=bpy.context.scene
route_file=Path(a.source).parent/'report.json';route=json.loads(route_file.read_text('utf8')) if route_file.exists() else {};first=a.first if a.first is not None else route.get('frames',[204,255.75])[0];last=a.last if a.last is not None else route.get('frames',[204,255.75])[1];timeline_last=s.frame_end
removed=[]
for mod in list(m.modifiers):
 if mod.name.startswith('Local joint volume'):
  names=[n.inputs['Name'].default_value for n in mod.node_group.nodes if n.bl_idname=='GeometryNodeInputNamedAttribute']
  removed.append(dict(modifier=mod.name,attributes=names));m.modifiers.remove(mod)
  for name in names:
   if name.startswith('HairContact_MeasuredIndex') and name in m.data.attributes:m.data.attributes.remove(m.data.attributes[name])
parts=regions(m,arm,profile);s.frame_set(1);arm.data.pose_position='REST';bpy.context.view_layer.update();rest=coords(m);arm.data.pose_position='POSE';bpy.context.view_layer.update();reports=[]
for side,chain in zip(['L','R'],profile['control_chains']):
 wrist=chain[2];group=m.vertex_groups[wrist].index;joint=np.array(arm.matrix_world@arm.data.bones[wrist].head_local);distance=np.linalg.norm(rest-joint,axis=1);u=np.clip((distance-.04)/.03,0,1);falloff=1-u*u*(3-2*u);weights=np.array([sum(g.weight for g in v.groups if g.group==group) for v in m.data.vertices])*falloff;eligible=set(parts['ids'].get('arm.'+side,[]))|set(parts['ids'].get('hand.'+side,[]));ids=np.array([i for i,w in enumerate(weights) if w>1e-6 and i in eligible]);mask=weights[ids]
 report=bake_local_volume_skin(m,arm,ids,mask,wrist,out/'cache'/('joint_'+side+'.pc2'),first=first,last=last,step=.0625,blend=1.,fade=1.,namespace='FullHairWrist'+side);reports.append(dict(side=side,**report));print('JOINT_REBAKED',side,report['maximum_skin_displacement_m'],flush=True)
s.frame_start=1;s.frame_end=timeline_last;s.frame_set(1);s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.fps=30
# Absolute inherited caches are preserved. Only these new caches become relative.
for report in reports:
 carrier=bpy.data.objects[report['cache']['carrier']]
 for mod in carrier.modifiers:
  if mod.type=='MESH_CACHE':mod.filepath='//cache/'+Path(report['cache']['cache']).name
candidate=out/'完整角色_自动避让与新腕部蒙皮.blend';bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True,relative_remap=False)
(out/'prepared.json').write_text(json.dumps(dict(source=a.source,candidate=str(candidate),removed_stale_joint_bindings=removed,joints=reports,protected_window=[256,321],weights_rest_mesh_actions_edited=False),ensure_ascii=False,indent=2),encoding='utf8');print('ROUTE_SKIN_READY',str(candidate),flush=True)
