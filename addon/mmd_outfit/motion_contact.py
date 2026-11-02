"""Evaluated-skin contact audit and bounded skeletal contact correction.

This deliberately does not claim continuous collision detection or a cloth
solver. Open regional surfaces provide local signed-distance constraints;
triangle intersections are reported independently. Original actions are copied.
"""
import math
from collections import Counter
import numpy as np
import bpy
from mathutils import Vector, Quaternion, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri

ARM_PREFIX=('腕','ひじ','手捩','手首','親指','人指','中指','薬指','小指')
HAND_PREFIX=('手首','親指','人指','中指','薬指','小指')
SKIN={'Body','面','面1','肌','Keqing_NeckBlend'}

def skin_regions(body,arm):
    names={g.index:g.name for g in body.vertex_groups if not g.name.startswith('mmd_')}
    dominant=[]
    for v in body.data.vertices:
        weights=[(g.weight,names[g.group]) for g in v.groups if g.group in names]
        dominant.append(max(weights,default=(0.,''))[1])
    region=[]
    for i,name in enumerate(dominant):
        if name.endswith(('.L','.R')) and name.startswith(ARM_PREFIX):r='arm'+name[-2:]
        elif name.endswith(('.L','.R')) and name.startswith(('足','ひざ','足首','足先','つま先')):r='leg'+name[-2:]
        elif name.startswith(('頭','首','目','両目')):r='head'
        elif name.startswith(('上半身','下半身','腰','胸','乳','鎖骨','腹','おっぱい')):r='torso'
        else:r='excluded'
        region.append(r)
    faces={r:[] for r in set(region)}
    body.data.calc_loop_triangles()
    for f in body.data.loop_triangles:
        if body.data.materials[f.material_index].name not in SKIN:continue
        votes=Counter(region[i] for i in f.vertices);r,v=votes.most_common(1)[0]
        if v==len(f.vertices):faces[r].append(tuple(f.vertices))
    ids={r:sorted({i for f in fs for i in f}) for r,fs in faces.items()}
    # Deterministic 7 mm rest-space samples, not a complete mesh certificate.
    samples={}
    for r,indices in ids.items():
        vox={}
        for i in indices:vox.setdefault(tuple(int(math.floor(c/.007)) for c in body.data.vertices[i].co),i)
        samples[r]=list(vox.values())
    return dict(dominant=dominant,faces=faces,ids=ids,samples=samples,extra_objects=[])

def add_glove_hands(regions,body,arm,cloth):
    """This outfit stores the visible gloved hands in Cloth, not Body.

    Evaluate only those rigidly skinned faces, avoiding stale cloth caches.
    The temporary audit mesh is never substituted for the visible model.
    """
    names={g.index:g.name for g in cloth.vertex_groups if not g.name.startswith('mmd_') and g.name in arm.pose.bones}
    dom=[max(((g.weight,names[g.group]) for g in v.groups if g.group in names),default=(0.,''))[1] for v in cloth.data.vertices]
    chosen={v.index for v in cloth.data.vertices if dom[v.index].startswith(HAND_PREFIX)}
    cloth.data.calc_loop_triangles()
    fs=[tuple(f.vertices) for f in cloth.data.loop_triangles if all(i in chosen for i in f.vertices)]
    chosen=sorted({i for f in fs for i in f});remap={i:j for j,i in enumerate(chosen)}
    mesh=bpy.data.meshes.new('ContactAuditGlovedHands');mesh.from_pydata([cloth.data.vertices[i].co for i in chosen],[],[tuple(remap[i] for i in f) for f in fs]);mesh.update()
    obj=bpy.data.objects.new('ContactAuditGlovedHands',mesh);bpy.context.scene.collection.objects.link(obj);obj.matrix_world=cloth.matrix_world;obj.hide_render=True;obj.hide_set(True)
    groups={g.index:obj.vertex_groups.new(name=g.name) for g in cloth.vertex_groups if g.index in names}
    for j,i in enumerate(chosen):
        for g in cloth.data.vertices[i].groups:
            if g.group in groups:groups[g.group].add([j],g.weight,'REPLACE')
    original=next(m for m in cloth.modifiers if m.type=='ARMATURE')
    mod=obj.modifiers.new('Actual hand skinning','ARMATURE');mod.object=arm;mod.use_deform_preserve_volume=original.use_deform_preserve_volume
    offset=len(body.data.vertices);regions['extra_objects'].append(obj)
    for side in ('.L','.R'):
        r='arm'+side;additional=[tuple(offset+remap[i] for i in f) for f in fs if all(dom[i].endswith(side) for i in f)]
        regions['faces'][r].extend(additional);indices=sorted({i for f in additional for i in f});regions['ids'][r].extend(indices)
        vox={}
        for i in indices:vox.setdefault(tuple(int(math.floor(c/.005)) for c in mesh.vertices[i-offset].co),i)
        regions['samples'][r].extend(vox.values())
    return dict(hand_vertices=len(chosen),hand_faces=len(fs),source='Cloth skinned glove geometry; Body has no hand vertices')

def add_fixed_outfit_collider(regions,body,arm,cloth):
    """Non-simulated torso/forearm garment surfaces also block the cloth."""
    selection=cloth.data.attributes.get('OutfitStructuredClothSelection')
    if selection is None:raise ValueError('Explicit simulated garment selection is required')
    names={g.index:g.name for g in cloth.vertex_groups if g.name in arm.pose.bones}
    dom=[max(((g.weight,names[g.group]) for g in v.groups if g.group in names),default=(0.,''))[1] for v in cloth.data.vertices]
    cloth.data.calc_loop_triangles();fs=[tuple(f.vertices) for f in cloth.data.loop_triangles if all(not selection.data[i].value and not dom[i].startswith(HAND_PREFIX+('頭',)) and cloth.data.vertices[i].co.z<1.40 for i in f.vertices)]
    chosen=sorted({i for f in fs for i in f});remap={i:j for j,i in enumerate(chosen)};mesh=bpy.data.meshes.new('FixedOutfitContactSurface');mesh.from_pydata([cloth.data.vertices[i].co for i in chosen],[],[tuple(remap[i] for i in f) for f in fs]);mesh.update();obj=bpy.data.objects.new('FixedOutfitContactSurface',mesh);bpy.context.scene.collection.objects.link(obj);obj.matrix_world=cloth.matrix_world;obj.hide_render=True;obj.hide_set(True)
    groups={i:obj.vertex_groups.new(name=n) for i,n in names.items()}
    for j,i in enumerate(chosen):
        for g in cloth.data.vertices[i].groups:
            if g.group in groups:groups[g.group].add([j],g.weight,'REPLACE')
    original=next(m for m in cloth.modifiers if m.type=='ARMATURE');mod=obj.modifiers.new('Fixed clothing skinning','ARMATURE');mod.object=arm;mod.use_deform_preserve_volume=original.use_deform_preserve_volume
    offset=len(body.data.vertices)+sum(len(o.data.vertices) for o in regions['extra_objects']);regions['extra_objects'].append(obj);r='fixed_outfit';regions['faces'][r]=[tuple(offset+remap[i] for i in f) for f in fs];regions['ids'][r]=list(range(offset,offset+len(chosen)));regions['samples'][r]=[]
    return dict(vertices=len(chosen),triangles=len(fs),scope='non-simulated torso and forearm clothing; excludes existing hand collider and head pieces')

PAIRS=[('arm.L','torso'),('arm.R','torso'),('arm.L','head'),('arm.R','head'),('arm.L','arm.R'),('leg.L','leg.R')]

RAY_DIRECTIONS=[Vector(v).normalized() for v in ((.819,.413,.397),(-.337,.873,.351),(.231,-.455,.86))]
def inside_votes(tree,point):
    """Three-ray parity rejects back-facing nearest points outside a part.

    Region cuts are still open, so this is a practical classifier, not a
    watertight-solid certificate. Independent triangle crossings remain in QA.
    """
    inside=0
    for direction in RAY_DIRECTIONS:
        origin=point.copy();hits=0
        for _ in range(16):
            hit,normal,index,distance=tree.ray_cast(origin,direction,3.)
            if hit is None:break
            hits+=1;origin=hit+direction*.00002
        inside+=hits%2
    return inside>=2

def triangle_crosses(a,b,tolerance=.00002):
    """Non-coplanar segment crossing; grazing contact is not penetration."""
    points=[]
    for first,second in ((a,b),(b,a)):
        normal=(second[1]-second[0]).cross(second[2]-second[0])
        if normal.length<1e-12:continue
        normal.normalize();signed=[(p-second[0]).dot(normal) for p in first]
        if min(signed)>-1e-7 or max(signed)<1e-7:continue
        for k in range(3):
            start,end=first[k],first[(k+1)%3];direction=end-start
            if direction.length_squared<1e-16:continue
            hit=intersect_ray_tri(*second,direction,start,True)
            if hit is None:continue
            t=(hit-start).dot(direction)/direction.length_squared
            if -1e-6<=t<=1+1e-6 and not any((p-hit).length<1e-6 for p in points):points.append(hit)
    return len(points)>1 and max((p-q).length for p in points for q in points)>tolerance

def evaluated_coords(body):
    obj=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=obj.to_mesh()
    co=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',co);obj.to_mesh_clear()
    co=co.reshape(-1,3);matrix=np.asarray(body.matrix_world)
    return co@matrix[:3,:3].T+matrix[:3,3]

def all_coords(body,regions):
    return np.concatenate([evaluated_coords(o) for o in [body]+regions.get('extra_objects',[])])

def contacts(body,arm,regions,margin=.002,mesh_crossings=True,first_crossing=False,sample_contacts=True):
    co=all_coords(body,regions)
    trees={r:BVHTree.FromPolygons(co.tolist(),fs,all_triangles=False) for r,fs in regions['faces'].items() if fs and r!='excluded'}
    rows=[];constraints=[]
    for a,b in PAIRS:
        if a not in trees or b not in trees:continue
        near=[]
        # Both directions avoid missing a thin finger or asymmetric sampling.
        for moving,target in ((a,b),(b,a)):
            for i in regions['samples'][moving] if sample_contacts else []:
                p=Vector(co[i]);q,n,fi,d=trees[target].find_nearest(p)
                if q is None:continue
                signed=(p-q).dot(n)
                # Boundary nearest points do not define a signed solid. Reject
                # tangential/open-cut directions; keep local normal contacts.
                if d>.08 or (d>1e-6 and abs(signed)/d<.65):continue
                # A second surface exit must exist toward the interior. A
                # negative nearest normal alone mislabels points behind the
                # open shoulder cut as being inside an arm.
                if signed<0:
                    # Exclude the open shoulder cut from arm signed tests.
                    if target.startswith('arm'):
                        shoulder=arm.matrix_world@arm.pose.bones['腕'+target[-2:]].head
                        elbow=arm.matrix_world@arm.pose.bones['ひじ'+target[-2:]].head
                        axis=elbow-shoulder
                        if (q-shoulder).dot(axis)/axis.length_squared<.1:continue
                    if not inside_votes(trees[target],p):continue
                if signed<margin:
                    near.append(dict(vertex=i,region=moving,target=target,gap_m=signed,distance_m=d,point=list(p),target_point=list(q),normal=list(n),target_triangle=regions['faces'][target][fi]))
        overlaps=trees[a].overlap(trees[b]) if mesh_crossings else []
        confirmed=0
        for i,j in overlaps:
            if triangle_crosses([Vector(co[k]) for k in regions['faces'][a][i]],[Vector(co[k]) for k in regions['faces'][b][j]]):
                confirmed+=1
                if first_crossing:break
        rows.append(dict(pair=[a,b],near_samples=len(near),penetrating_samples=sum(c['gap_m']<-.001 for c in near),min_local_gap_m=min((c['gap_m'] for c in near),default=None),bvh_candidate_pairs=len(overlaps),triangle_crossings=confirmed))
        constraints.extend(near)
    return dict(pairs=rows,positions=co,constraints=constraints)

def compact(audit):
    return dict(pairs=audit['pairs'],penetrating_samples=sum(p['penetrating_samples'] for p in audit['pairs']),triangle_crossings=sum(p['triangle_crossings'] for p in audit['pairs']))

def active_constraints(audit):
    # Do not drive the torso toward an arm's open anatomical cut. Hands and
    # arms are the movable bodies in this first constrained-motion stage.
    return [c for c in audit['constraints'] if c['region'].startswith('arm') or (c['region']=='head' and c['target'].startswith('arm'))]

def rotation_vector(v):
    angle=float(np.linalg.norm(v))
    return Quaternion(Vector(v)/angle,angle) if angle>1e-10 else Quaternion()

class ArmContactProjector:
    """Small bounded pose optimization using *evaluated* Blender skinning.

    Finite differences include the rig's twist helpers and constraints. Only
    arm/elbow/wrist controls change; root and foot IK channels stay untouched.
    Infeasible constraints are returned, never declared solved by hiding skin.
    """
    def __init__(self,body,arm,regions,margin=.010,limit_degrees=32,preserve_hand_orientation=False):
        self.body=body;self.arm=arm;self.regions=regions;self.margin=margin
        self.names=[p+'.'+s for s in ('L','R') for p in ('腕','ひじ','手首')]
        self.bones=[arm.pose.bones[n] for n in self.names]
        self.limit=math.radians(limit_degrees)
        self.preserve_hand_orientation=preserve_hand_orientation

    def capture(self):
        self.base=[b.rotation_quaternion.copy() for b in self.bones]
        self.hand_matrices=[self.bones[i].matrix.copy() for i in (2,5)]

    def hand_translation_seed(self,delta,pole_angles=None):
        """Two-link IK seed: translate both hand targets, retaining gestures.

        The source elbow supplies the pole; rotations preserve bone lengths.
        Evaluated-skin projection still validates the result afterwards.
        """
        if pole_angles is not None:
            pole_angles=np.asarray(pole_angles,dtype=float)
            if pole_angles.shape!=(2,) or not np.isfinite(pole_angles).all():raise ValueError('Supply two finite elbow pole angles in radians')
        self.apply(np.zeros(18));world=self.arm.matrix_world;inverse=world.inverted()
        anchors=[[(world@self.bones[i+j].head).copy() for j in range(3)] for i in (0,3)]
        shifts=np.asarray(delta)
        for group,(s,e,w) in enumerate(anchors):
            shift=shifts[group] if shifts.ndim==2 else shifts
            upper,elbow,wrist=self.bones[3*group:3*group+3];target=w+Vector(shift);l1=(e-s).length;l2=(w-e).length;axis=target-s;distance=min(max(axis.length,abs(l1-l2)+1e-5),l1+l2-1e-5);axis.normalize();target=s+axis*distance
            pole=e-s-axis*(e-s).dot(axis)
            if pole.length<1e-7:pole=axis.cross(Vector((0,0,1)))
            pole.normalize()
            if pole_angles is not None:pole=Quaternion(axis,float(pole_angles[group]))@pole
            along=(l1*l1+distance*distance-l2*l2)/(2*distance);height=math.sqrt(max(0,l1*l1-along*along));desired_elbow=s+axis*along+pole*height
            def aim(bone,origin,old,new):
                q=old.rotation_difference(new);change=Matrix.Translation(origin)@q.to_matrix().to_4x4()@Matrix.Translation(-origin);bone.matrix=inverse@change@world@bone.matrix;self.arm.update_tag();bpy.context.view_layer.update()
            aim(upper,s,e-s,desired_elbow-s);actual_e=world@elbow.head;actual_w=world@wrist.head;aim(elbow,actual_e,actual_w-actual_e,target-actual_e)
            pose=self.hand_matrices[group].copy();pose.translation=wrist.head;wrist.matrix=pose;self.arm.update_tag();bpy.context.view_layer.update()
        result=np.zeros(18)
        for i,bone in enumerate(self.bones):
            q=self.base[i].inverted()@bone.rotation_quaternion
            if q.w<0:q.negate()
            result[3*i:3*i+3]=q.to_exponential_map()
        return result

    def apply(self,x):
        for i,b in enumerate(self.bones):b.rotation_quaternion=self.base[i]@rotation_vector(x[3*i:3*i+3])
        self.arm.update_tag();bpy.context.view_layer.update()
        if self.preserve_hand_orientation:
            for i,matrix in zip((2,5),self.hand_matrices):
                target=matrix.copy();target.translation=self.bones[i].head;self.bones[i].matrix=target
            self.arm.update_tag();bpy.context.view_layer.update()

    def objective(self,audit,x):
        cs=active_constraints(audit)
        residual=np.array([max(0,self.margin-c['gap_m']) for c in cs])
        # Worst violations matter even when hundreds of fingers are close.
        prior=x-self.preferred
        return float(np.sum(residual**2)+self.prior_weight*np.dot(prior,prior))

    def solve(self,initial=None,iterations=18,preferred=None,prior_weight=.0002):
        x=np.zeros(len(self.bones)*3) if initial is None else np.array(initial,dtype=float).copy()
        self.preferred=np.zeros_like(x) if preferred is None else np.array(preferred,dtype=float)
        self.prior_weight=prior_weight
        if self.preserve_hand_orientation:
            for i in (6,15):x[i:i+3]=0;self.preferred[i:i+3]=0
        for i in range(len(self.bones)):
            part=x[3*i:3*i+3];length=np.linalg.norm(part)
            if length>self.limit:part*=self.limit/length
        self.apply(x);audit=contacts(self.body,self.arm,self.regions,self.margin,False)
        history=[]
        for iteration in range(iterations):
            cs=active_constraints(audit)
            if not cs:break
            # Finite-difference noise and the pose prior leave micrometre
            # residuals at the contact envelope. Do not spend 18 full rig
            # evaluations repeatedly chasing a sub-0.5 mm envelope error.
            if max(self.margin-c['gap_m'] for c in cs)<.0005:break
            # Stratify by part-pair and vertex so dense glove topology cannot
            # drown out a deeply intersecting upper arm.
            buckets={}
            for c in cs:buckets.setdefault((c['region'],c['target']),[]).append(c)
            cs=[c for bucket in buckets.values() for c in sorted(bucket,key=lambda c:c['gap_m'])[:160]]
            co=audit['positions'];normals=np.array([c['normal'] for c in cs]);ids=np.array([c['vertex'] for c in cs]);target_ids=np.array([c['target_triangle'] for c in cs])
            bary=[]
            for c in cs:
                tri=co[list(c['target_triangle'])];q=np.array(c['target_point']);v0=tri[1]-tri[0];v1=tri[2]-tri[0]
                uv=np.linalg.lstsq(np.column_stack((v0,v1)),q-tri[0],rcond=None)[0];bary.append([1-uv.sum(),uv[0],uv[1]])
            bary=np.array(bary);jac=np.zeros((len(cs),len(x)));eps=.001
            for j in range(len(x)):
                if self.preserve_hand_orientation and j//3 in (2,5):continue
                test=x.copy();test[j]+=eps;self.apply(test);different=all_coords(self.body,self.regions)-co
                relative=different[ids]-(different[target_ids]*bary[:,:,None]).sum(axis=1)
                jac[:,j]=np.einsum('ij,ij->i',relative,normals)/eps
            self.apply(x)
            rhs=np.array([self.margin-c['gap_m'] for c in cs])
            lhs=jac.T@jac+np.eye(len(x))*.0006
            step=np.linalg.solve(lhs,jac.T@rhs-self.prior_weight*(x-self.preferred))
            for i in range(len(self.bones)):
                part=step[3*i:3*i+3];length=np.linalg.norm(part)
                if length>math.radians(4):part*=math.radians(4)/length
            old=self.objective(audit,x);accepted=False
            for scale in (1.,.5,.25,.1):
                candidate=x+step*scale
                for i in range(len(self.bones)):
                    part=candidate[3*i:3*i+3];length=np.linalg.norm(part)
                    if length>self.limit:part*=self.limit/length
                self.apply(candidate);test=contacts(self.body,self.arm,self.regions,self.margin,False)
                score=self.objective(test,candidate)
                if score<old-1e-10:
                    x=candidate;audit=test;accepted=True;break
            history.append(dict(iteration=iteration,objective=self.objective(audit,x),accepted=accepted))
            if not accepted:self.apply(x);break
        self.apply(x)
        return x,dict(iterations=history,remaining=compact(contacts(self.body,self.arm,self.regions,self.margin,True)),max_control_delta_deg=float(max(np.linalg.norm(x[i:i+3]) for i in range(0,len(x),3))*180/math.pi))

def smooth_offset_track(track,radius=5,sigma=2.0):
    """Symmetric look-ahead avoids late reactive jumps into a contact."""
    track=np.asarray(track,dtype=float);offsets=np.arange(-radius,radius+1);weights=np.exp(-.5*(offsets/sigma)**2);weights/=weights.sum()
    padded=np.pad(track,((radius,radius),(0,0)),mode='edge')
    return sum(w*padded[i:i+len(track)] for i,w in enumerate(weights))

def audit_current_pose(body,arm,glove_mesh=None,margin=.002):
    """Small agent-facing API. Does not save or change an action/mesh."""
    regions=skin_regions(body,arm)
    try:
        if glove_mesh is not None:add_glove_hands(regions,body,arm,glove_mesh)
        return compact(contacts(body,arm,regions,margin,True))
    finally:
        for obj in regions['extra_objects']:bpy.data.objects.remove(obj,do_unlink=True)
