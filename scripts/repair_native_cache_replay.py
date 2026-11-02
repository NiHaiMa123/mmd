"""Repackage existing native positive-frame cache; do not resimulate."""
import bpy,json,sys,shutil,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
engine('import_export').ensure_mmd_tools()
base=ROOT.parent/'work/headswap_xl_codex/standard_cloth_20261031';src=base/'candidate06';out=base/'candidate07_replay';out.mkdir(exist_ok=True);dest=out/'native_cache';dest.mkdir(exist_ok=True)
for f in (src/'blendcache_完整角色_原生发片Cloth_15秒').glob('*.bphys'):
 frame=int(f.name.rsplit('_',2)[1])
 if frame>=0:
  target=dest/f'NativeHair_{frame:06d}_00.bphys'
  if not target.exists():shutil.copy2(f,target)
bpy.ops.wm.open_mainfile(filepath=str(src/'完整角色_原生发片Cloth_15秒.blend'),use_scripts=False,load_ui=False)
h=bpy.data.objects['完整头发_原生Cloth_实际发片'];cl=next(m for m in h.modifiers if m.type=='CLOTH');pc=cl.point_cache
pc.filepath=str(dest);pc.name='NativeHair';pc.use_external=True;pc.frame_start=1;pc.frame_end=450
h.update_tag();bpy.context.view_layer.update()
path=out/'完整角色_原生发片Cloth_15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False,load_ui=False)
h=bpy.data.objects['完整头发_原生Cloth_实际发片'];cl=next(m for m in h.modifiers if m.type=='CLOTH');pc=cl.point_cache
rows=[]
for frame in [1,69,331]:
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();x=coords(h)
 cl.show_viewport=False;bpy.context.view_layer.update();raw=coords(h)
 cl.show_viewport=True;bpy.context.view_layer.update()
 row=dict(frame=frame,physical_difference_p95=float(np.quantile(np.linalg.norm(x-raw,axis=1),.95)),info=pc.info,start=pc.frame_start,end=pc.frame_end)
 rows.append(row);print('REPLAY',json.dumps(row,ensure_ascii=False),flush=True)
(out/'replay_report.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
