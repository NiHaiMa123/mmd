import sys,json,argparse,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
from animation_contact_tools.mmd_hair import build_hair_only
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True);p.add_argument('--mode',choices=['preserve','hybrid','legacy_physics'],default='preserve');p.add_argument('--hair-dq',action='store_true');p.add_argument('--pin-roots',action='store_true');p.add_argument('--pin-fringe',action='store_true');p.add_argument('--initial-fit');p.add_argument('--surface-body',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.source).resolve()),load_ui=False,use_scripts=False)
profile=json.loads(Path(a.profile).read_text('utf8'));profile['hair_mmd_rigid_mode']=a.mode;mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
profile['hair_pin_chain_roots']=a.pin_roots
if a.pin_fringe:profile['hair_kinematic_bones']=[b.name for b in arm.pose.bones if b.name.startswith('FrontHair')]
if a.initial_fit:
 from animation_contact_tools.hair_projector import HairProjector
 from animation_contact_tools.projector import exp_quat
 h=HairProjector(mesh,arm,profile,parts);x=np.load(a.initial_fit)['offsets'];profile['hair_initial_pose']={b.name:list(exp_quat(x[3*i:3*i+3])) for i,b in enumerate(h.bones)}
(out/'rig_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8')
sampled=sorted(set(range(1,451,15))|{1,100,226,240,285,361,450});reference={};source_skin={};hair_faces=parts['faces'].get('hair_mobile',[])+parts['faces'].get('hair_root',[]);hairids=sorted({i for f in hair_faces for i in f});skinids=sorted({i for r,ids in parts['ids'].items() if not r.startswith('hair') for i in ids});edges=np.unique(np.sort(np.array([(a,b) for f in hair_faces for a,b in zip(f,(f[1],f[2],f[0]))]),axis=1),axis=0)
if a.hair_dq:
 bpy.context.scene.frame_set(1);bpy.context.view_layer.update();before=coords(mesh);mask=mesh.vertex_groups.new(name='HairContact_DQ_Mask');mask.add(hairids,1,'REPLACE');index=next(i for i,m in enumerate(mesh.modifiers) if m.type=='ARMATURE');dq=mesh.modifiers.new('Hair-only preserve volume','ARMATURE');dq.object=arm;dq.vertex_group=mask.name;dq.use_multi_modifier=True;dq.use_deform_preserve_volume=True;mesh.modifiers.move(len(mesh.modifiers)-1,index+1);bpy.context.view_layer.update();assert float(np.max(np.abs(coords(mesh)[skinids]-before[skinids])))<2e-6
for frame in sampled:
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();co=coords(mesh);reference[frame]=np.linalg.norm(co[edges[:,1]]-co[edges[:,0]],axis=1);source_skin[frame]=co[skinids].copy()
surface_obj=None;surface_info=None
if a.surface_body:
 from animation_contact_tools.body_surface_cache import bake_body_surface,enable_body_surface
 surface_obj,surface_info=bake_body_surface(mesh,profile,out)
bpy.context.scene.frame_set(1);bpy.context.view_layer.update();report={'source':a.source,'setup':build_hair_only(mesh,arm,profile),'samples':[],'status':'SIMULATING'}
if surface_obj:
 surface_info['rigid']=enable_body_surface(surface_obj);report['body_surface_collider']=surface_info
start=time.monotonic()
for frame in range(1,451):
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
 if frame in reference:
  row=audit_frame(mesh,arm,profile,parts,hair=True);co=coords(mesh);length=np.linalg.norm(co[edges[:,1]]-co[edges[:,0]],axis=1);ratio=length/np.maximum(reference[frame],1e-8)
  valid=reference[frame]>.0005;row['edge_ratio_min']=float(ratio.min());row['edge_ratio_max']=float(ratio.max());row['edge_ratio_p99']=float(np.quantile(ratio,.99));row['valid_edge_ratio_max']=float(ratio[valid].max());row['valid_edge_ratio_p99']=float(np.percentile(ratio[valid],99));row['body_skin_max_error_m']=float(np.max(np.abs(co[skinids]-source_skin[frame])));report['samples'].append(row)
  if frame in (1,100,226,240,285,361,450):np.savez_compressed(out/f'keypose{frame:04}.npz',coordinates=co)
  print('NATIVE_HAIR_SAMPLE',frame,row['ordinary_crossings'],row['edge_ratio_max'],flush=True)
  (out/'hair_backend_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
report['status']='PROXY_PHYSICS_PROBE_REQUIRES_SURFACE_AND_DEFORMATION_ACCEPTANCE';report['seconds']=time.monotonic()-start
(out/'hair_backend_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'NativeHair_LiveProbe_NotAccepted.blend'),compress=True)
print('NATIVE_HAIR_PROBE_COMPLETE',report['seconds'],flush=True)
