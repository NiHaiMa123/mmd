"""Shared time-key reduction bounded by the worst prescribed vertex error."""
import numpy as np


def reduce_trajectory_keys(positions,times,tolerance,chunk=64):
    positions=np.asarray(positions);times=np.asarray(times,dtype=float)
    if positions.ndim!=3 or positions.shape[0]!=len(times) or positions.shape[1]<1 or positions.shape[2]!=3 or len(times)<2:
        raise ValueError('At least two frames x vertices x 3 required')
    if not np.all(np.isfinite(positions)) or not np.all(np.isfinite(times)) or np.any(np.diff(times)<=0) or not np.isfinite(tolerance) or tolerance<=0 or chunk<1:
        raise ValueError('Finite trajectories, increasing times and positive error bound required')
    keep={0,len(times)-1};stack=[(0,len(times)-1)];bound=tolerance*tolerance
    while stack:
        left,right=stack.pop()
        if right-left<2:continue
        largest=-1.;split=None
        for start in range(left+1,right,chunk):
            stop=min(start+chunk,right);u=(times[start:stop]-times[left])/(times[right]-times[left]);predicted=positions[left][None,:,:]*(1-u[:,None,None])+positions[right][None,:,:]*u[:,None,None];delta=positions[start:stop]-predicted;error=np.einsum('fvi,fvi->fv',delta,delta).max(axis=1);index=int(np.argmax(error))
            if error[index]>largest:largest=float(error[index]);split=start+index
        if largest>bound:keep.add(split);stack.extend(((left,split),(split,right)))
    keys=np.array(sorted(keep),dtype=int);maximum=0.
    for left,right in zip(keys,keys[1:]):
        for start in range(left,right+1,chunk):
            stop=min(start+chunk,right+1);u=(times[start:stop]-times[left])/(times[right]-times[left]);predicted=positions[left][None,:,:]*(1-u[:,None,None])+positions[right][None,:,:]*u[:,None,None];maximum=max(maximum,float(np.linalg.norm(positions[start:stop]-predicted,axis=2).max()))
    return keys,dict(source_keys=len(times),retained_keys=len(keys),tolerance_m=float(tolerance),measured_maximum_vertex_error_m=maximum,source_positions_changed=False,continuous_error_bound_proven=False)
