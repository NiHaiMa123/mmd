"""Orientation-independent sampled distance queries on closed collider unions."""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


class ClosedColliderField:
    def __init__(self,vertices,faces):
        self.vertices=np.asarray(vertices,dtype=float);self.faces=[tuple(f) for f in faces];self.tree=BVHTree.FromPolygons(self.vertices.tolist(),self.faces);parent=np.arange(len(vertices))
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=int(parent[i])
            return i
        for face in faces:
            root=find(face[0])
            for i in face[1:]:parent[find(i)]=root
        groups={}
        for face in faces:groups.setdefault(find(face[0]),[]).append(tuple(face))
        self.components=[]
        for fs in groups.values():
            ids=np.array(sorted({i for f in fs for i in f}));points=self.vertices[ids];self.components.append({'faces':fs,'minimum':points.min(0)-1e-8,'maximum':points.max(0)+1e-8,'tree':None})
        self.minimum=np.array([c['minimum'] for c in self.components]);self.maximum=np.array([c['maximum'] for c in self.components]);self.directions=[Vector(v).normalized() for v in [(1,.371,.219),(.173,1,.427),(.293,.191,1)]];self.cache={};self.ray_classifications=0;self.sign_reuses=0

    def inside(self,point,candidates=None):
        candidates=np.flatnonzero(np.all(point>=self.minimum,axis=1)&np.all(point<=self.maximum,axis=1)) if candidates is None else candidates
        for index in candidates:
            component=self.components[index]
            if component['tree'] is None:component['tree']=BVHTree.FromPolygons(self.vertices.tolist(),component['faces'])
            votes=0
            for direction in self.directions:
                # Construct each next origin from double-precision cumulative
                # travel. A float32 BVH hit can round back onto the same face;
                # repeated zero-distance hits must not change ray parity.
                origin=Vector(point);hits=0;travel=0.;queries=0
                vector=np.asarray(direction,dtype=float);epsilon=1e-6
                while hits<128 and queries<512:
                    queries+=1
                    q,n,index,d=component['tree'].ray_cast(origin,direction,100.)
                    if q is None:break
                    position=float(np.dot(np.asarray(q,dtype=float)-point,vector))
                    if queries>1 and position<=travel+epsilon*.25:
                        travel+=epsilon*4
                    else:
                        hits+=1;travel=position+epsilon
                    origin=Vector(point+vector*travel)
                if hits==128 or queries==512:raise RuntimeError('Closed-collider ray exceeded its distinct crossing/progress limit')
                votes+=hits%2
            self.ray_classifications+=1
            if votes>=2:return True
        return False

    def __call__(self,points):
        points=np.asarray(points,dtype=float);distance=np.empty(len(points));normal=np.empty_like(points);signs=np.empty(len(points),dtype=bool);previous=self.cache.get(len(points));deltas=np.empty_like(points);fallback=np.empty_like(points)
        for j,point in enumerate(points):
            q,n,index,d=self.tree.find_nearest(Vector(point));distance[j]=d;deltas[j]=point-np.asarray(q);fallback[j]=n
        reused=np.zeros(len(points),dtype=bool) if previous is None else np.linalg.norm(points-previous[0],axis=1)<.9*previous[1]-1e-7
        if previous is not None:signs[reused]=previous[2][reused];self.sign_reuses+=int(reused.sum())
        fresh=np.flatnonzero(~reused)
        for start in range(0,len(fresh),4096):
            block=fresh[start:start+4096];p=points[block];boxes=np.all(p[:,None,:]>=self.minimum[None,:,:],axis=2)&np.all(p[:,None,:]<=self.maximum[None,:,:],axis=2)
            for k,j in enumerate(block):signs[j]=self.inside(points[j],np.flatnonzero(boxes[k]))
        normal=deltas/np.maximum(distance[:,None],1e-12);normal[signs]*=-1;normal[distance<=1e-10]=fallback[distance<=1e-10];distance[signs]*=-1
        self.cache[len(points)]=(points.copy(),np.abs(distance),signs.copy())
        return distance,normal
