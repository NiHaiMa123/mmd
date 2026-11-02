"""Render a completed cloth cache; never recalculate or change physics."""
import sys,argparse,json,time
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--width',type=int,default=1920);p.add_argument('--height',type=int,default=1080);p.add_argument('--step',type=int,choices=(1,2),default=1);p.add_argument('--limit',type=int);p.add_argument('--priority-start',type=int);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.fit).resolve();engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
sim=next(m for m in bpy.data.objects['ClothSimulationSurface'].modifiers if m.type=='CLOTH');assert sim.point_cache.is_baked
scene=bpy.context.scene;first=int(scene.get('outfit_preview_first',1));last=int(scene.get('outfit_preview_last',450));assert last-first+1==450
# Temporary subdivision choice for the review render; the project is preserved.
for m in bpy.data.objects['Cloth'].modifiers:
    if m.type=='SUBSURF':m.render_levels=min(m.render_levels,1)
scene.render.resolution_x=a.width;scene.render.resolution_y=a.height;scene.render.resolution_percentage=100
plan={'width':a.width,'height':a.height,'native_render':True,'source_fps':30,'fps':30/a.step,'step':a.step,'first':first,'last':last,'expected_frames':450//a.step}
if (out/'render_plan.json').exists():
    previous=json.loads((out/'render_plan.json').read_text(encoding='utf-8'))
    assert all(previous.get(k)==plan[k] for k in ('width','height','step','first','last')),'Existing frames use a different render plan; use a separate output directory'
(out/'render_plan.json').write_text(json.dumps(plan),encoding='utf-8')
start=time.monotonic()
frames=list(range(first,last+1,a.step))
if a.priority_start:frames=[f for f in frames if f>=a.priority_start]+[f for f in frames if f<a.priority_start]
if a.limit:frames=frames[:a.limit]
for index,frame in enumerate(frames):
    scene.frame_set(frame);scene.render.filepath=str(out/'frames'/f'f{frame:04d}.png')
    if not Path(scene.render.filepath).is_file():bpy.ops.render.render(write_still=True)
    if index%15==0:
        row={'source_frame':frame-first+1,'rendered':index+1,'total':len(frames),'elapsed_s':time.monotonic()-start};(out/'render_progress.json').write_text(json.dumps(row),encoding='utf-8');print('CACHED_PREVIEW_RENDER',json.dumps(row),flush=True)
(out/'render_progress.json').write_text(json.dumps({'status':'complete' if len(frames)==plan['expected_frames'] else 'partial','source_frame':450 if len(frames)==plan['expected_frames'] else frames[-1]-first+1,'rendered':len(frames),'total':plan['expected_frames'],'elapsed_s':time.monotonic()-start}),encoding='utf-8')
print('CACHED_PREVIEW_RENDER_COMPLETE',len(frames),flush=True)
