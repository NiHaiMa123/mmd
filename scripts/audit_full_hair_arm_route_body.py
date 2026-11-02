"""Check actual body surfaces in the automatically modified motion window."""
import argparse,sys,json,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True);p.add_argument('--first',type=float,default=204);p.add_argument('--last',type=float,default=255.75);p.add_argument('--step',type=float,default=.25);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False);profile=json.loads(Path(a.profile).read_text('utf8'));m=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(m,arm,profile);rows=[];started=time.monotonic()
for f in np.arange(a.first,a.last+a.step*.1,a.step):
 bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();r=audit_frame(m,arm,profile,parts,hair=False,cap=1000000);row=dict(frame=float(f),ordinary_crossings=r['ordinary_crossings'],ordinary_contained_samples=r['ordinary_contained_samples'],pairs=[x for x in r['pairs'] if x['triangle_crossings'] or x['contained_samples']]);rows.append(row)
 if len(rows)%20==0:print('ARM_ROUTE_BODY_AUDIT',f,row['ordinary_crossings'],row['ordinary_contained_samples'],flush=True)
result=dict(status='BODY_ROUTE_SAMPLED_PASS' if not any(x['ordinary_crossings'] or x['ordinary_contained_samples'] for x in rows) else 'BODY_ROUTE_HAS_RESIDUAL_CONTACTS',source=a.source,samples=len(rows),step=a.step,rows=rows,protected_window_untouched=[256,321],seconds=time.monotonic()-started);Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('ARM_ROUTE_BODY_COMPLETE',result['status'],flush=True)
