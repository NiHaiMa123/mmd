import sys,json,time,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
from animation_contact_tools.native_hair_surface import build_native_hair_surface
parser=argparse.ArgumentParser();parser.add_argument('--zero-mass-pins',action='store_true');parser.add_argument('--embedded-roots',action='store_true');parser.add_argument('--head-local',action='store_true');parser.add_argument('--split-colliders',action='store_true');parser.add_argument('--substeps',type=int,default=5);parser.add_argument('--iterations',type=int,default=20);parser.add_argument('--tag',default='native_xpbd_probe');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'hair_tests_v2'/options.tag;out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p)
bpy.context.scene.frame_set(1);bpy.context.view_layer.update();base=coords(mesh);hairids=set(parts['ids']['hair_root']+parts['ids']['hair_mobile']);skinids=[i for i in range(len(base)) if i not in hairids];edges=np.array([e.vertices[:] for e in mesh.data.edges if all(i in hairids for i in e.vertices)]);length=np.linalg.norm(base[edges[:,0]]-base[edges[:,1]],axis=1);valid=length>.0005
p['hair_coordinate_bone']='頭'
backend=build_native_hair_surface(mesh,arm,p,parts,substeps=options.substeps,iterations=options.iterations,zero_mass_pins=options.zero_mass_pins,embedded_root_pins=options.embedded_roots,head_local=options.head_local,split_colliders=options.split_colliders);scene=bpy.context.scene;scene.frame_start=-30
for bake in backend['simulation_modifier'].bakes:bake.use_custom_simulation_frame_range=True;bake.frame_start=-30;bake.frame_end=450
for track in arm.animation_data.nla_tracks:
 for strip in track.strips:strip.extrapolation='HOLD'
rows=[];start=time.monotonic()
for f in range(-30,31):
 scene.frame_set(f);bpy.context.view_layer.update();co=coords(mesh)
 if not np.all(np.isfinite(co)):raise RuntimeError('Non-finite simulated coordinates')
 if f%10==0 or f==1:
  source=coords(backend['reference']);a=audit_frame(mesh,arm,p,parts,hair=True,cap=3000);ratio=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1)[valid]/length[valid];pin_ids=backend['representatives'][backend['pinweights']>.5];r={'frame':f,'crossings':sum(r['triangle_crossings'] for r in a['pairs'] if r['pair'][0].startswith('hair')),'pairs':[{'pair':r['pair'],'crossings':r['triangle_crossings']} for r in a['pairs'] if r['pair'][0].startswith('hair') and r['triangle_crossings']],'max_delta_m':float(np.linalg.norm(co-source,axis=1).max()),'body_max_error_m':float(np.max(np.abs(co[skinids]-source[skinids]))),'pin_max_error_m':float(np.linalg.norm(co[pin_ids]-source[pin_ids],axis=1).max()),'edge_ratio_max':float(ratio.max()),'edge_ratio_p99':float(np.percentile(ratio,99))};rows.append(r);print('NATIVE_XPBD_HAIR',json.dumps(r),flush=True)
  (out/'probe.json').write_text(json.dumps({'metadata':backend['metadata'],'samples':rows,'seconds':time.monotonic()-start,'accepted':False},ensure_ascii=False,indent=2),encoding='utf8')
np.save(out/'frame30_coords.npy',coords(mesh));bpy.ops.wm.save_as_mainfile(filepath=str(out/'NativeXPBD_Hair_Probe.blend'),compress=True)
