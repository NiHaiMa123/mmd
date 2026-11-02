# SPDX-License-Identifier: Apache-2.0
# Adapted portions: Copyright 2025 Ryoichi Ando (ZOZO, Inc.).
# See THIRD_PARTY_NOTICES.md and PPF_APACHE_LICENSE.txt.
"""Bounded-memory boxes for cloth against dense prescribed colliders.

The adapter follows PPF's static-collider policy: collider/collider pairs are
not resolved, while every cloth/cloth and cloth/collider pair is retained.
Candidate-cache logic is adapted from the Apache-2.0 PPF add-on's
core/shell_untangle.py (Ryoichi Ando / ZOZO, pinned 2026-10-19 distribution).
"""
import numpy as np

def scoped_box_pairs(lo,hi,scope,chunk=32):
    lo=np.asarray(lo);hi=np.asarray(hi);scope=np.asarray(scope,dtype=bool);active=np.flatnonzero(scope);left=[];right=[]
    for start in range(0,len(active),chunk):
        ids=active[start:start+chunk];hit=np.ones((len(ids),len(lo)),dtype=bool)
        for axis in range(3):hit&=(lo[ids,axis,None]<=hi[None,:,axis])&(lo[None,:,axis]<=hi[ids,axis,None])
        row,col=np.nonzero(hit);a=ids[row];keep=(a!=col)&(~scope[col]|(a<col));a=a[keep];b=col[keep];left.append(np.minimum(a,b));right.append(np.maximum(a,b))
    return (np.concatenate(left),np.concatenate(right)) if left else (np.empty(0,np.int64),np.empty(0,np.int64))

def install_static_collider_policy(module):
    """Install only in our portable worker, without editing vendor files."""
    def candidates(sc,vert,held_too=False):
        tv=vert[sc.tri];reach=(sc.tri_off+.5*sc.clearance)[:,None];grown=reach+.5*sc.guard;lo=tv.min(axis=1);hi=tv.max(axis=1);cached=sc.nlist
        if cached is not None and cached['held_too']==held_too and float(grown.max())<=cached['grown'] and 2*float(np.abs(vert-cached['vert']).max())<=cached['skin']:
            ia,ib,share=cached['ia'],cached['ib'],cached['share']
        else:
            # Whole static surfaces represent prescribed collider unions.
            # Fixed vertices on a partly movable cloth remain CLOTH here.
            owners=np.array([sc.free[begin:end].any() for _,begin,end in sc.spans]);scope=owners[sc.tri_surface];skin=module._SKIN*sc.edge;ia,ib=scoped_box_pairs(lo-grown-skin,hi+grown+skin,scope);ta,tb=sc.tri[ia],sc.tri[ib];share=(ta[:,:,None]==tb[:,None,:]).any(axis=(1,2))
            if not held_too:
                keep=sc.free[ta].any(axis=1)|sc.free[tb].any(axis=1);ia,ib,share=ia[keep],ib[keep],share[keep]
            sc.nlist=dict(held_too=held_too,grown=float(grown.max()),skin=skin,vert=vert.copy(),ia=ia,ib=ib,share=share)
        if not len(ia):return ia,ib,np.empty(0,bool),np.empty(0,bool)
        meet=np.all(lo[ia]-grown[ia]<=hi[ib]+grown[ib],axis=1)&np.all(lo[ib]-grown[ib]<=hi[ia]+grown[ia],axis=1);ia,ib,share=ia[meet],ib[meet],share[meet];near=np.all(lo[ia]-reach[ia]<=hi[ib]+reach[ib],axis=1)&np.all(lo[ib]-reach[ib]<=hi[ia]+reach[ia],axis=1)
        return ia,ib,share,near
    module._candidate_pairs=candidates
