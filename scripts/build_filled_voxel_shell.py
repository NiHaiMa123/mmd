"""Unsigned voxel exterior: fill enclosed cavities before surface extraction."""
import argparse,json
import numpy as np
import trimesh
from scipy.ndimage import binary_fill_holes,binary_dilation
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--pitch',type=float,default=.002);a=p.parse_args()
with np.load(a.input) as z:co=z['points'];faces=z['faces']
used=np.unique(faces);mapping=np.full(len(co),-1,dtype=int);mapping[used]=np.arange(len(used));mesh=trimesh.Trimesh(vertices=co[used],faces=mapping[faces],process=False);grid=mesh.voxelized(a.pitch);matrix=np.pad(grid.matrix,3);filled=binary_fill_holes(matrix);filled=binary_dilation(filled,structure=np.ones((3,3,3),dtype=bool));origin=grid.transform[:3,3]-3*a.pitch;all_quads=[]
corners=[[(1,-1,-1),(1,1,-1),(1,1,1),(1,-1,1)],[(-1,-1,-1),(-1,-1,1),(-1,1,1),(-1,1,-1)],[(-1,1,-1),(-1,1,1),(1,1,1),(1,1,-1)],[(-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1)],[(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)],[(-1,-1,-1),(-1,1,-1),(1,1,-1),(1,-1,-1)]]
for index,(axis,direction) in enumerate(((0,1),(0,-1),(1,1),(1,-1),(2,1),(2,-1))):
    neighbor=np.roll(filled,-direction,axis=axis);boundary=filled&~neighbor;indices=np.argwhere(boundary);all_quads.append(indices[:,None,:]*2+np.array(corners[index])[None,:,:])
quads=np.concatenate(all_quads);unique,inverse=np.unique(quads.reshape(-1,3),axis=0,return_inverse=True);points=origin+unique*a.pitch*.5;faces=inverse.reshape(-1,4);np.savez_compressed(a.output,points=points,faces=faces);print(json.dumps({'grid':list(filled.shape),'surface_vertices':len(points),'surface_quads':len(faces),'pitch_m':a.pitch}),flush=True)
