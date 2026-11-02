"""Sparse local/global ARAP step with unilateral surface-contact constraints."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import cg,LinearOperator
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
with np.load(a.input) as z:d={k:z[k] for k in z.files}
rest=d['rest'];x=d['current'].copy();edges=d['edges'];n=len(x);rows=d['rows'];cols=d['cols'];values=d['values'];bound=d['bound'];locked=d['locked'].astype(bool);A=sparse.coo_matrix((values,(rows,cols)),shape=(len(bound),n*3)).tocsr();e0,e1=edges.T;diff=rest[e0]-rest[e1];degree=np.bincount(edges.reshape(-1),minlength=n);L=sparse.diags(degree)-sparse.coo_matrix((np.ones(len(edges)*2),(np.r_[e0,e1],np.r_[e1,e0])),shape=(n,n)).tocsr();base=sparse.kron(L,sparse.eye(3),format='csr')+sparse.eye(n*3,format='csr')*.02;free=np.repeat(~locked,3);fixed=~free;restflat=rest.ravel();failures=[]
for iteration in range(8):
    current=x[e0]-x[e1];cov=np.zeros((n,3,3));outer=np.einsum('ni,nj->nij',current,diff);np.add.at(cov,e0,outer);np.add.at(cov,e1,outer);u,s,vt=np.linalg.svd(cov);r=u@vt;negative=np.linalg.det(r)<0;u[negative,:,-1]*=-1;r=u@vt;rotated=np.einsum('nij,nj->ni',(r[e0]+r[e1])*.5,diff);rhs=np.zeros((n,3));np.add.at(rhs,e0,rotated);np.add.at(rhs,e1,-rotated);rhs=rhs.ravel()+.02*restflat
    active=np.asarray(A@x.ravel()<bound+.00005).reshape(-1);C=A[active];b=bound[active];weight=2000.;H=base+weight*(C.T@C);rhs+=weight*np.asarray(C.T@b).reshape(-1);Hfree=H[free][:,free].tocsr();right=rhs[free]-H[free][:,fixed]@restflat[fixed];diag=Hfree.diagonal();pre=LinearOperator(Hfree.shape,matvec=lambda v:v/np.maximum(diag,1e-12));solution,info=cg(Hfree,right,x0=x.ravel()[free],M=pre,rtol=1e-8,atol=1e-10,maxiter=600)
    if info:failures.append(int(info))
    flat=restflat.copy();flat[free]=solution;x=flat.reshape(-1,3);delta=x-rest;length=np.linalg.norm(delta,axis=1);x=rest+delta*np.minimum(1.,.10/np.maximum(length,1e-12))[:,None]
np.savez_compressed(a.output,points=x,cg_nonconvergence=np.array(failures,dtype=int),max_constraint_violation=np.array(float(np.maximum(0,bound-A@x.ravel()).max()) if len(bound) else 0.))
