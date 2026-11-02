"""Linearized contact of fixed attachment samples against deforming skin.

The closed field supplies orientation-independent signs. Contact derivatives
follow a nearest-triangle barycentric point; rebuild after each nonlinear step.
"""
import numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform
from .closed_collider_field import ClosedColliderField


def attachment_contacts(co,skin_ids,skin_faces,points,clearance):
    field=ClosedColliderField(co[skin_ids],skin_faces)
    distance,normal=field(points);indices=np.flatnonzero(distance<clearance)
    triangles=[];weights=[]
    basis=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
    for i in indices:
        q,n,fi,d=field.tree.find_nearest(Vector(points[i]));face=field.faces[fi]
        if len(face)!=3:raise ValueError('Attachment contact requires triangulated closed skin')
        ids=np.asarray(skin_ids)[list(face)];w=barycentric_transform(q,*[Vector(co[j]) for j in ids],*basis)
        triangles.append(ids);weights.append(w[:])
    triangles=np.asarray(triangles,dtype=int).reshape(-1,3);weights=np.asarray(weights,dtype=float).reshape(-1,3)
    return {'distance':distance[indices], 'normal':normal[indices], 'triangles':triangles,'weights':weights,
            'surface':attachment_surface(co,triangles,weights),'minimum_distance':float(distance.min())}


def attachment_surface(co,triangles,weights):
    return np.einsum('fi,fij->fj',weights,co[triangles])


def attachment_linear_gap(co,contacts):
    delta=attachment_surface(co,contacts['triangles'],contacts['weights'])-contacts['surface']
    return contacts['distance']-np.einsum('ij,ij->i',delta,contacts['normal'])
