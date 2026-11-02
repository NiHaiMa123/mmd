import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.contact_broadphase import scoped_box_pairs
rng=np.random.default_rng(731);lo=rng.uniform(-1,1,(160,3));hi=lo+rng.uniform(0,.7,(160,3));scope=rng.random(160)<.22;actual=scoped_box_pairs(lo,hi,scope,chunk=7);pairs=set(zip(*actual));expected={(i,j) for i in range(160) for j in range(i+1,160) if (scope[i] or scope[j]) and np.all(lo[i]<=hi[j]) and np.all(lo[j]<=hi[i])};assert pairs==expected;assert len(pairs)==len(actual[0]);assert not len(scoped_box_pairs(lo,hi,np.zeros(160,bool))[0])
print('SCOPED_CONTACT_BROADPHASE_CONTRACT_PASS',len(pairs),flush=True)
