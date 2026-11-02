import sys,json,time,argparse
from pathlib import Path
import numpy as np
import warp as wp
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.gpu_surface import SurfaceProjector
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--rounds',type=int,default=120);a=p.parse_args();src=Path(a.input);out=Path(a.out);out.mkdir(exist_ok=True,parents=True)
x=np.load(src/'hair_initial.npy');solver=SurfaceProjector(x,np.load(src/'hair_edges.npy'),np.load(src/'hair_faces.npy'),np.load(src/'body.npy',mmap_mode='r')[0],np.load(src/'body_faces.npy'),rest=np.load(src/'hair_original.npy'),body_real_faces=np.load(src/'real_body_faces.npy'));start=time.monotonic();history=[];best=None
for k in range(a.rounds+1):
 row=dict(round=k,self_crossings=solver.self_crossings(),**solver.metrics(),elapsed_s=time.monotonic()-start);history.append(row);print('GPU_INITIAL_UNTANGLE',json.dumps(row),flush=True)
 if row['inside_vertices']==0 and row['min_edge_ratio']>=.895 and row['max_edge_ratio']<=1.105 and (best is None or row['self_crossings']<best[0]):best=(row['self_crossings'],solver.positions().copy(),row);np.save(out/'best_positions.npy',best[1])
 np.save(out/'checkpoint.npy',solver.positions());(out/'progress.json').write_text(json.dumps(row,indent=2),encoding='utf8')
 if row['self_crossings']==0 and row['inside_vertices']==0:break
 solver.project(iterations=64,margin=.0005,lo=.9,hi=1.1,triangles=True,max_displacement=.04,self_contacts=True,self_margin=.0002)
(out/'report.json').write_text(json.dumps(dict(status='INITIAL_REQUIRES_INDEPENDENT_VALIDATION',history=history,selected=None if best is None else best[2],physics_started=False),indent=2),encoding='utf8')
