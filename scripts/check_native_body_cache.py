import bpy,json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
engine('import_export').ensure_mmd_tools()
base=ROOT.parent/'work/headswap_xl_codex';out=base/'standard_cloth_20261031/candidate03'
bpy.ops.wm.open_mainfile(filepath=str(out/'完整角色_原生发片Cloth_15秒.blend'),use_scripts=False,load_ui=False)
obj=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部'];cache=next(m for m in obj.modifiers if m.type=='MESH_CACHE');s=bpy.context.scene
expected=np.load(base/'fullhair_repro_20261030/input_body_aware/body.npy',mmap_mode='r');rows=[]
print('CACHE_SETTINGS',{k:str(getattr(cache,k)) for k in ['time_mode','play_mode','frame_start','frame_scale','eval_frame','eval_time','eval_factor','factor','interpolation','forward_axis','up_axis','flip_axis','filepath']},flush=True)
print('MATRIX',[list(r) for r in obj.matrix_world], 'HIDDEN',obj.hide_get(),obj.hide_viewport,obj.hide_render,flush=True)
for f in [1,69,175,242,331,450]:
 s.frame_set(f);bpy.context.view_layer.update();actual=coords(obj);target=expected[(f-1)*8]
 err=np.linalg.norm(actual-target,axis=1);means=np.array([np.mean(np.linalg.norm(actual-expected[k],axis=1)) for k in range(0,len(expected),8)])
 rows.append(dict(frame=f,max_error_m=float(err.max()),mean_error_m=float(err.mean()),closest_source_frame=int(means.argmin()+1),closest_mean_error_m=float(means.min())))
print('BODY_REPLAY',json.dumps(rows),flush=True);(out/'body_cache_replay.json').write_text(json.dumps(rows,indent=2),'utf8')
