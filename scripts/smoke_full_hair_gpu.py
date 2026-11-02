import sys,json,time
from pathlib import Path
import numpy as np
import warp as wp
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.gpu_surface import SurfaceProjector
src=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input';out=src.parent
initial=np.load(src/'hair_initial.npy');edges=np.load(src/'hair_edges.npy');faces=np.load(src/'hair_faces.npy');body=np.load(src/'body.npy',mmap_mode='r');bf=np.load(src/'body_faces.npy');start=time.monotonic();solver=SurfaceProjector(initial,edges,faces,body[0],bf,rest=np.load(src/'hair_original.npy'),body_real_faces=np.load(src/'real_body_faces.npy'));d,_=solver.distances(initial);print('DISTANCE',float(d.min()),int((d<-.0001).sum()),flush=True)
start=time.monotonic();solver.project(iterations=8,margin=.0005,lo=.9,hi=1.1,triangles=True,max_displacement=.02);wp.synchronize();print('PROJECT_SECONDS',time.monotonic()-start,solver.metrics(),flush=True);start=time.monotonic();solver.project(iterations=64,margin=.0005,lo=.9,hi=1.1,triangles=True,max_displacement=.02);wp.synchronize();report=dict(elapsed_64_s=time.monotonic()-start,metrics=solver.metrics());(out/'gpu_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('GPU_SMOKE',json.dumps(report),flush=True)


