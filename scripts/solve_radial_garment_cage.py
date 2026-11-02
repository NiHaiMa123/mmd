"""Smooth positive radial garment displacement, shared across material layers."""
import argparse,json
import numpy as np
from scipy.ndimage import maximum_filter,gaussian_filter,distance_transform_edt,map_coordinates
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
with np.load(a.input) as z:d={k:z[k] for k in z.files}
skin=d['skin'];points=d['points'];step=.005;nangle=120;low=min(skin[:,2].min(),points[:,2].min())-.03;high=max(skin[:,2].max(),points[:,2].max())+.03;nz=int(np.ceil((high-low)/step))+1
def polar(p):return np.linalg.norm(p[:,:2],axis=1),np.clip((p[:,2]-low)/step,0,nz-1),(np.arctan2(p[:,1],p[:,0])+np.pi)/(2*np.pi)*nangle
def filled_grid(values,z,theta,maximum=True):
    grid=np.full((nz,nangle),-np.inf);np.maximum.at(grid,(np.rint(z).astype(int),np.rint(theta).astype(int)%nangle),values);grid=maximum_filter(grid,size=(5,5),mode=('nearest','wrap'));valid=np.isfinite(grid);tiled=np.tile(grid,(1,3));bad=~np.isfinite(tiled);idx=distance_transform_edt(bad,return_distances=False,return_indices=True);tiled[bad]=tiled[tuple(idx[:,bad])];return tiled[:,nangle:2*nangle]
radius,z,theta=polar(skin);field=filled_grid(radius,z,theta);field=np.maximum(field,gaussian_filter(field,(1.5,1.5),mode=('nearest','wrap')))+.005
r,z,t=polar(points);sample=lambda g:map_coordinates(np.pad(g,((0,0),(1,1)),mode='wrap'),[z,t+1],order=1,mode='nearest');needed=np.maximum(0,sample(field)-r);growth=np.full((nz,nangle),0.);np.maximum.at(growth,(np.rint(z).astype(int),np.rint(t).astype(int)%nangle),needed);growth=maximum_filter(growth,size=(5,5),mode=('nearest','wrap'));growth=np.maximum(growth,gaussian_filter(growth,(2.5,2.5),mode=('nearest','wrap')));dr=sample(growth);result=points.copy();result[:,:2]*=(1+dr/np.maximum(r,1e-6))[:,None];np.savez_compressed(a.output,points=result,displacement=dr);print(json.dumps({'max_radial_change_m':float(dr.max()),'p99_m':float(np.quantile(dr,.99))}))
