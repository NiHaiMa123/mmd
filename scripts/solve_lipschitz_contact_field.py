"""Smallest geodesically Lipschitz field above all contact displacements."""
import argparse,numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
with np.load(a.input) as z:points=z['points'];faces=z['faces'];needed=z['needed'];slope=float(z['slope'])
_,weld=np.unique(np.rint(points/1e-6).astype(np.int64),axis=0,return_inverse=True);n=int(weld.max())+1;wpoints=np.zeros((n,3));np.add.at(wpoints,weld,points);wpoints/=np.bincount(weld)[:,None];bound=np.zeros(n);np.maximum.at(bound,weld,needed);tri=weld[faces];edges=np.unique(np.sort(np.concatenate((tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]])),axis=1),axis=0);length=np.linalg.norm(wpoints[edges[:,0]]-wpoints[edges[:,1]],axis=1)*slope;active=np.flatnonzero(bound>0);height=float(bound.max()+.0001);rows=np.r_[edges[:,0],edges[:,1],np.full(len(active),n)];cols=np.r_[edges[:,1],edges[:,0],active];values=np.r_[length,length,height-bound[active]];graph=sparse.coo_matrix((values,(rows,cols)),shape=(n+1,n+1)).tocsr();dist=dijkstra(graph,indices=n,directed=True);field=np.maximum(0,height-dist[:n]);np.savez_compressed(a.output,field=field[weld]);print('LIPSCHITZ_CONTACT_FIELD',n,len(active),float(field.max()))
