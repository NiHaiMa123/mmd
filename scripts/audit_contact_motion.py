"""Audit the actual 15 second sequence; does not modify the source file."""
import argparse,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,contacts,compact,add_glove_hands
p=argparse.ArgumentParser();p.add_argument('--step',type=int,default=1);p.add_argument('--frames',nargs='*',type=float);p.add_argument('--source',default='outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend');p.add_argument('--label',default='before');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/a.source),load_ui=False,use_scripts=False)
body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm']
for o in bpy.data.objects:
    if o.type=='MESH' and o!=body:o.hide_viewport=True
regions=skin_regions(body,arm);hands=add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);out=ROOT/'outputs/cynical_cloth15/contact_motion';out.mkdir(exist_ok=True)
report=dict(method='bidirectional local signed surface samples + regional triangle overlaps; not CCD',sample_spacing_m=.007,scope='arms/torso/head, arm/arm, leg/leg; excludes adjacent anatomical seams and non-skin materials',regions={r:dict(vertices=len(regions['ids'][r]),faces=len(fs),samples=len(regions['samples'][r])) for r,fs in regions['faces'].items()},frames={})
report['hands']=hands
for f in a.frames or range(47,497,a.step):
    bpy.context.scene.frame_set(int(f),subframe=f%1);audit=contacts(body,arm,regions);report['frames'][str(f)]=compact(audit)
    if a.frames:report['frames'][str(f)]['constraints']=audit['constraints']
    if len(report['frames'])%30==0:print('CONTACT_AUDIT',f,compact(audit),flush=True)
(out/f'audit_{a.label}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('CONTACT_AUDIT_COMPLETE',str(out),flush=True)
