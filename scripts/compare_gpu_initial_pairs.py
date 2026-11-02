import sys,json
from pathlib import Path
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.surface import crosses
out=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030';src=out/'input';pairs=np.load(out/'gpu_initial_intersection_pairs.npy');h=np.load(src/'hair_initial.npy');b=np.load(src/'body.npy',mmap_mode='r')[0];hf=np.load(src/'hair_faces.npy');bf=np.load(src/'body_faces.npy');passed=[]
for i,j in pairs:
 if crosses([Vector(v) for v in h[hf[i]]],[Vector(v) for v in b[bf[j]]]):passed.append([int(i),int(j)])
(out/'cpu_gpu_pair_comparison.json').write_text(json.dumps(dict(gpu_pairs=len(pairs),independent_blender_strict_crossings=len(passed),actual_pairs=passed),indent=2),encoding='utf8');print('CPU_GPU_CHECK',len(pairs),len(passed),flush=True)
