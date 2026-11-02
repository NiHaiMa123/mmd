"""Locate whole-clip body conflicts with a legal, head-transported hair clump.

This plans space for a later physical solve; it is not dynamic-hair acceptance.
"""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions,audit_frame
from animation_contact_tools.hair_bundle_profile import resolve_bundle
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--bundle',required=True);p.add_argument('--initial',required=True);p.add_argument('--out',required=True);p.add_argument('--first',type=float,default=1);p.add_argument('--last',type=float,default=450);p.add_argument('--step',type=float,default=.25);p.add_argument('--reference-frame',type=float,default=1);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise ValueError('Use a fresh planning output directory')
config=json.loads(Path(a.bundle).read_text('utf8'));profile=json.loads(Path(config['source_profile']).read_text('utf8'));profile['pairs']=[];initial=np.load(a.initial)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];bundle=resolve_bundle(mesh,arm,regions(mesh,arm,profile),config);np.testing.assert_array_equal(initial['ids'],bundle['ids']);scene=bpy.context.scene;scene.frame_set(int(a.reference_frame),subframe=a.reference_frame%1);bpy.context.view_layer.update();reference=np.array(arm.matrix_world@arm.pose.bones[config['anchor_bone']].matrix);rows=[]
for k,f in enumerate(np.arange(a.first,a.last+.00001,a.step)):
 scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();head=np.array(arm.matrix_world@arm.pose.bones[config['anchor_bone']].matrix);delta=head@np.linalg.inv(reference);co=coords(mesh);co[bundle['ids']]=initial['coordinates']@delta[:3,:3].T+delta[:3,3];audit=audit_frame(mesh,arm,profile,bundle['parts'],hair=True,cap=1000000,coordinates_m=co);rows.append(dict(frame=float(f),crossings=audit['ordinary_crossings'],pairs=[(r['pair'],r['triangle_crossings']) for r in audit['pairs'] if r['triangle_crossings']]))
 if k%256==0:print('CLUMP_SPACE',float(f),sum(x['crossings']>0 for x in rows),flush=True)
failed=[r for r in rows if r['crossings']];windows=[]
for row in failed:
 if not windows or row['frame']-windows[-1][1]>a.step*1.01:windows.append([row['frame'],row['frame']])
 else:windows[-1][1]=row['frame']
result=dict(status='STATIC_CLUMP_SPACE_PLANNING_ONLY',source=a.source,bundle=a.bundle,frames=[a.first,a.last],step_frames=a.step,sample_count=len(rows),failed_samples=len(failed),conflict_windows=windows,samples=rows,dynamic_hair_accepted=False,ccd_proven=False)
(out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('CLUMP_SPACE_COMPLETE',json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
