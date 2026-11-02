import sys,json,time,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.strain_hair import StrainHairProjector
from animation_contact_tools.projector import FrameProjector
parser=argparse.ArgumentParser();parser.add_argument('--frames',type=int,nargs='+',default=[226,240]);parser.add_argument('--analytic',action='store_true');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'hair_tests_v2/body_feedback';out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p)
hp=dict(p,hair_collision_targets=['torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R'],hair_strain_scale_m=.03,hair_analytic_jacobian=options.analytic)
bp=dict(p,extra_contact_targets=['hair_root'],preserve_wrist_orientation=False);bp['pairs']=[pair for pair in p['pairs'] if pair[0].startswith(('arm','hand'))]+[(r,'hair_root') for r in ('arm.L','arm.R','hand.L','hand.R')]
hair=StrainHairProjector(mesh,arm,hp,parts,limit_degrees=30,max_active=18);body=FrameProjector(mesh,arm,bp,parts,p['control_chains'],limit_degrees=15);rows=[]
for frame in options.frames:
 for bone in hair.bones:bone.rotation_quaternion=(1,0,0,0)
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();source=coords(mesh);primary={n:np.array(arm.pose.bones[n].matrix) for n in ('頭','上半身3','下半身','左足ＩＫ','右足ＩＫ') if n in arm.pose.bones};body.capture();hair.capture();start=time.monotonic();bx=np.zeros(body.n);hx=np.zeros(hair.n);details=[]
 for it in range(3):
  bx,br=body.solve(initial=bx,iterations=35);hx,hr=hair.solve(initial=hx,iterations=45,preferred=hx);details.append({'iteration':it,'body':br,'hair':hr});print('HAIR_BODY_ALTERNATION',frame,it,br.get('remaining_crossings'),hr['remaining_target_crossings'],hr['edge_ratio_max'],flush=True)
  if not hr['remaining_target_crossings'] and hr['edge_ratio_max']<1.1 and hr['edge_ratio_min']>.9:break
 co=coords(mesh);skinids=sorted(set(range(len(co)))-set(parts['ids']['hair_root']+parts['ids']['hair_mobile']));row={'frame':frame,'seconds':time.monotonic()-start,'details':details,'primary_bone_matrix_error':max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))) for n,m in primary.items()),'max_body_surface_movement_m':float(np.linalg.norm(co[skinids]-source[skinids],axis=1).max())};rows.append(row);np.savez_compressed(out/f'frame{frame:04}.npz',coordinates=co,hair_offsets=hx,body_offsets=bx);(out/'probe.json').write_text(json.dumps({'samples':rows,'full_hair_accepted':False},ensure_ascii=False,indent=2),encoding='utf8')
