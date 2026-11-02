"""Small convex fitting problem in a smooth skeletal garment cage."""
import argparse
import numpy as np
from scipy.optimize import minimize
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
with np.load(a.input) as z:d={k:z[k] for k in z.files}
H=d['H'];A=d['A'];b=d['b'];x=d['parameters'];bounds=list(zip(d['lower'],d['upper']))
sol=minimize(lambda q:float(.5*q@H@q),x,jac=lambda q:H@q,method='SLSQP',bounds=bounds,constraints={'type':'ineq','fun':lambda q:A@q-b,'jac':lambda q:A},options={'maxiter':250,'ftol':1e-12})
if not sol.success:
    def loss(q):
        v=np.maximum(0.,b-A@q);return float(.5*q@H@q+5000*np.dot(v,v)),H@q-10000*(A.T@v)
    sol=minimize(loss,sol.x,jac=True,method='L-BFGS-B',bounds=bounds,options={'maxiter':1500,'ftol':1e-14,'gtol':1e-10})
np.savez_compressed(a.output,parameters=sol.x,violation=np.array(float(np.maximum(0.,b-A@sol.x).max()) if len(b) else 0.),success=np.array(sol.success),message=np.array(str(sol.message)))
