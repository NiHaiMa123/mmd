"""Geometry contracts: true crossing, contact, false BVH candidates, parity."""
import sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import triangle_crosses,inside_votes,smooth_offset_track
tri=lambda rows:[Vector(r) for r in rows]
a=tri([(0,0,0),(1,0,0),(0,1,0)])
assert triangle_crosses(a,tri([(.2,.2,-.3),(.2,.2,.3),(.8,.2,0)]))
# Overlapping axis-aligned bounds do not imply triangle penetration.
assert not triangle_crosses(a,tri([(.8,.8,-1),(.8,.8,1),(1,1,0)]))
assert not triangle_crosses(a,tri([(0,0,0),(1,0,0),(0,1,0)]))
co=[(x,y,z) for x in (-1,1) for y in (-1,1) for z in (-1,1)]
faces=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)];tree=BVHTree.FromPolygons(co,faces)
assert inside_votes(tree,Vector((.15,.13,.21)))
assert not inside_votes(tree,Vector((1.3,0,0)))
track=np.zeros((31,18));track[15,0]=.4;smooth=smooth_offset_track(track)
assert np.linalg.norm(np.diff(smooth,axis=0),axis=1).max()<np.linalg.norm(np.diff(track,axis=0),axis=1).max()*.3
assert np.allclose(smooth[:,1:],0) and np.allclose(smooth[:,0],smooth[::-1,0])
print('MOTION_CONTACT_CONTRACT_PASS',flush=True)
