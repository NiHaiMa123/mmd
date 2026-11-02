import bpy,json,sys,shutil,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
engine('import_export').ensure_mmd_tools()
p=ROOT.parent/'work/headswap_xl_codex/standard_cloth_20261031/candidate06'
bpy.ops.wm.open_mainfile(filepath=str(p/'完整角色_原生发片Cloth_15秒.blend'),load_ui=False,use_scripts=False)
h=bpy.data.objects['完整头发_原生Cloth_实际发片'];cl=next(m for m in h.modifiers if m.type=='CLOTH');pc=cl.point_cache
props={r.identifier:getattr(pc,r.identifier) for r in pc.bl_rna.properties if r.type in {'STRING','INT','BOOLEAN'} and r.identifier!='rna_type'}
print('CACHEPROPS',json.dumps(props,ensure_ascii=False),flush=True)
print('OBJECT',h.name,h.library,bpy.data.filepath,flush=True)
print('MODS',[(m.name,m.type,m.show_viewport,m.show_render) for m in h.modifiers],flush=True)
for mode in ['original','positive_range','external','named_ascii']:
 if mode=='positive_range':pc.frame_start=1
 if mode=='external':
  pc.filepath=str(p/'blendcache_完整角色_原生发片Cloth_15秒');pc.use_external=True
 if mode=='named_ascii':
  dest=p/'native_cache_replay';dest.mkdir(exist_ok=True)
  for file in (p/'blendcache_完整角色_原生发片Cloth_15秒').glob('*.bphys'):
   target=dest/('NativeHair_'+file.name.rsplit('_',2)[1]+'_'+file.name.rsplit('_',1)[1])
   if not target.exists():shutil.copy2(file,target)
  pc.use_external=False;pc.name='NativeHair';pc.filepath=str(dest);pc.use_external=True
 rows=[]
 print('MODEPROPS',mode,pc.name,pc.index,pc.filepath,pc.frame_start,pc.frame_end,flush=True)
 for frame in [1,69,331]:
  bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();x=coords(h)
  cl.show_viewport=False;bpy.context.view_layer.update();raw=coords(h)
  cl.show_viewport=True;bpy.context.view_layer.update()
  row=dict(frame=frame,physical_difference_p95=float(np.quantile(np.linalg.norm(x-raw,axis=1),.95)),info=pc.info,index=pc.index,name=pc.name,start=pc.frame_start,end=pc.frame_end)
  rows.append(row);print(mode,json.dumps(row,ensure_ascii=False),flush=True)
 (p/('cache_path_probe_'+mode+'.json')).write_text(json.dumps(dict(properties=props,rows=rows),ensure_ascii=False,indent=2),'utf8')
