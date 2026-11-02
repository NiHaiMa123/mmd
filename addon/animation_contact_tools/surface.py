"""Rig-profile-based evaluated-surface audit, independent of MMD operators."""
import math
from collections import defaultdict,Counter
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri

DEFAULT_PAIRS=[('arm.L','head'),('arm.R','head'),('arm.L','torso'),('arm.R','torso'),
 ('hand.L','head'),('hand.R','head'),('hand.L','torso'),('hand.R','torso'),
 ('leg.L','leg.R'),('arm.L','arm.R'),('hand.L','hand.R'),('hand.L','arm.R'),('hand.R','arm.L')]
for _a,_b in [('hand.L','arm.L'),('hand.R','arm.R'),('head','torso')]+[(a,b) for a in ('arm.L','arm.R','hand.L','hand.R') for b in ('leg.L','leg.R')]+[(a,b) for a in ('leg.L','leg.R') for b in ('head','torso')]:
    if not any(frozenset((_a,_b))==frozenset(p) for p in DEFAULT_PAIRS):DEFAULT_PAIRS.append((_a,_b))

def mmd_profile(mesh,arm):
    """Only this adapter knows Japanese MMD aliases; the auditor uses a profile."""
    roles=defaultdict(list);assigned={};anchors=[]
    for b in arm.pose.bones:
        alias=getattr(getattr(b,'mmd_bone',None),'name_j','') or b.name
        side='.L' if alias.startswith('左') else '.R' if alias.startswith('右') else None
        stem=alias[1:] if side else alias
        if side and stem.startswith(('手首','親指','人指','中指','薬指','小指')):r='hand'+side
        elif side and stem.startswith(('肩','腕','ひじ','手捩')):r='arm'+side
        elif side and stem.startswith(('足','ひざ','つま先')):r='leg'+side
        elif stem.startswith(('頭','首','目','両目')):r='head'
        elif stem.startswith(('上半身','下半身','腰','胸','乳','鎖骨','腹','おっぱい','センター','グルーブ','全ての親')):r='torso'
        else:continue
        roles[r].append(b.name);assigned[b.name]=r
        if alias in ('頭','首'):anchors.append(b.name)
    for b in arm.data.bones:
        if b.name in assigned:continue
        parent=b.parent
        while parent and parent.name not in assigned:parent=parent.parent
        if parent:roles[assigned[parent.name]].append(b.name)
    return {'schema':1,'mesh':mesh.name,'armature':arm.name,'units_to_m':1.,'bone_roles':dict(roles),
            'surface_attribute':'SurfaceClass','body_classes':[1],'head_classes':[2],'hair_classes':[3],
            'exclude_classes':[0,4,5],'pairs':DEFAULT_PAIRS,
            'protected_pairs':[],
            'protected_windows':[],'clearance_m':.003,'sample_step':5,
            'root_hair_head_weight':.8,'root_hair_anchor_bones':anchors,
            'note':'Mark intentional contacts with protected_windows; ordinary bilateral contacts remain audited.'}

def regions(mesh,arm,profile):
    if profile.get('schema')!=1:raise ValueError('Unsupported rig profile schema')
    if float(profile.get('units_to_m',1.))<=0:raise ValueError('units_to_m must be positive')
    classes=[set(profile[k]) for k in ('body_classes','head_classes','hair_classes','exclude_classes')]
    if any(a&b for i,a in enumerate(classes) for b in classes[i+1:]):raise ValueError('Surface classes must be disjoint')
    missing=[n for names in profile['bone_roles'].values() for n in names if n not in arm.pose.bones]
    if missing:raise ValueError('Profile references missing bones: '+', '.join(missing[:10]))
    data=mesh.data;data.calc_loop_triangles();group_roles={}
    for role,bones in profile['bone_roles'].items():
        for name in bones:
            if name in mesh.vertex_groups:group_roles[mesh.vertex_groups[name].index]=role
    anchor_groups={mesh.vertex_groups[n].index for n in profile.get('root_hair_anchor_bones',[]) if n in mesh.vertex_groups}
    scores=[];head_weight=[]
    for v in data.vertices:
        s=defaultdict(float)
        for g in v.groups:
            if g.group in group_roles:s[group_roles[g.group]]+=g.weight
        scores.append(s);head_weight.append(sum(g.weight for g in v.groups if g.group in anchor_groups))
    attr=data.attributes.get(profile.get('surface_attribute',''))
    if attr is None:raise ValueError('Explicit FACE surface classification required; use a profile/attribute instead of height guesses')
    if attr.domain!='FACE':raise ValueError('Surface class must be a FACE attribute')
    faces=defaultdict(list);source_faces=defaultdict(list);excluded=Counter()
    for tri in data.loop_triangles:
        cls=int(attr.data[tri.polygon_index].value);ids=tuple(tri.vertices)
        if cls in profile['exclude_classes']:excluded[str(cls)]+=1;continue
        if cls in profile['head_classes']:role='head'
        elif cls in profile['hair_classes']:
            role='hair_root' if sum(head_weight[i] for i in ids)/3>=profile.get('root_hair_head_weight',.8) else 'hair_mobile'
        elif cls in profile['body_classes']:
            total=defaultdict(float)
            for i in ids:
                for r,w in scores[i].items():total[r]+=w
            role=max(total,key=total.get) if total else 'unmapped_body'
        else:excluded[str(cls)]+=1;continue
        faces[role].append(ids);source_faces[role].append(tri.polygon_index)
    ids={r:sorted({i for f in fs for i in f}) for r,fs in faces.items()}
    samples={}
    mw=np.asarray(mesh.matrix_world);local=np.array([v.co[:] for v in data.vertices]);rest=(local@mw[:3,:3].T+mw[:3,3])*profile.get('units_to_m',1.)
    spacing=.012
    for r,indices in ids.items():
        vox={}
        for i in indices:vox.setdefault(tuple(math.floor(c/spacing) for c in rest[i]),i)
        samples[r]=list(vox.values())
    _,weld=np.unique(np.rint(rest*1e6).astype(np.int64),axis=0,return_inverse=True);closed={}
    for r,fs in faces.items():
        edge_count=Counter()
        for f in fs:
            vi=[int(weld[i]) for i in f]
            for a,b in zip(vi,(vi[1],vi[2],vi[0])):
                if a!=b:edge_count[tuple(sorted((a,b)))]+=1
        closed[r]=bool(edge_count) and all(n==2 for n in edge_count.values())
    return {'faces':dict(faces),'source_faces':dict(source_faces),'ids':ids,'samples':samples,'closed':closed,
            'excluded_surface_triangles':dict(excluded),'missing_body_mapping':len(faces.get('unmapped_body',[]))}

def coords(mesh):
    ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());data=ev.to_mesh()
    ar=np.empty(len(data.vertices)*3,dtype=np.float32);data.vertices.foreach_get('co',ar);ev.to_mesh_clear()
    ar=ar.reshape(-1,3);mw=np.asarray(mesh.matrix_world)
    return ar@mw[:3,:3].T+mw[:3,3]

def crosses(a,b,tolerance=.00002):
    """Strict non-coplanar crossing; touching is deliberately not penetration."""
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
            if 0<=t<=1 and not any((p-hit).length<1e-6 for p in points):points.append(hit)
    return len(points)>1 and max((p-q).length for p in points for q in points)>tolerance

def inside_closed(tree,point):
    votes=0
    for direction in (Vector((.819,.413,.397)).normalized(),Vector((-.337,.873,.351)).normalized(),Vector((.231,-.455,.86)).normalized()):
        origin=point.copy();hits=0
        for _ in range(64):
            q,n,fi,d=tree.ray_cast(origin,direction,100)
            if q is None:break
            hits+=1;origin=q+direction*.00001
        votes+=hits%2
    return votes>=2

def audit_frame(mesh,arm,profile,parts=None,hair=True,cap=400,coordinates_m=None,return_witness_pairs=False):
    parts=parts or regions(mesh,arm,profile);co=coords(mesh)*profile.get('units_to_m',1.) if coordinates_m is None else np.asarray(coordinates_m);world=co.tolist()
    if len(co)!=len(mesh.data.vertices):raise ValueError('Evaluated topology changed; supply a stable-topology audit mesh adapter')
    trees={r:BVHTree.FromPolygons(world,fs,all_triangles=True) for r,fs in parts['faces'].items() if fs}
    pairs=[tuple(p) for p in profile['pairs']]
    pairs += [(r,r) for r in profile.get('self_collision_regions',[])]
    if hair:
        pairs += [('hair_mobile',r) for r in ('head','torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R')]
        pairs += [('hair_root',r) for r in ('head','torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R')]
    protected={frozenset(x) for x in profile.get('protected_pairs',[])};rows=[]
    for a,b in pairs:
        if a not in trees or b not in trees:continue
        candidates=trees[a].overlap(trees[b]);count=0;examples=[];used_a=set();used_b=set();truncated=False;witnesses=[]
        for ia,ib in candidates:
            if a==b and ia>=ib:continue
            ta,tb=parts['faces'][a][ia],parts['faces'][b][ib]
            if set(ta)&set(tb):continue # shared anatomical seam, not a crossing
            if crosses([Vector(co[i]) for i in ta],[Vector(co[i]) for i in tb]):
                count+=1;used_a.update(ta);used_b.update(tb)
                if return_witness_pairs:witnesses.append((list(ta),list(tb)))
                if len(examples)<6:
                    examples.append({'a_triangle':list(ta),'b_triangle':list(tb),
                       'point':co[list(ta)].mean(0).tolist(),'a_polygon':parts['source_faces'][a][ia],'b_polygon':parts['source_faces'][b][ib]})
                if count>=cap:truncated=True;break
        contained=0
        for mover,target,indices in [(a,b,used_a),(b,a,used_b)]:
            if not parts.get('closed',{}).get(target):continue
            lower=co[parts['ids'][target]].min(0);upper=co[parts['ids'][target]].max(0)
            candidates=parts['samples'][mover]
            sampled=[candidates[j] for j in np.linspace(0,len(candidates)-1,min(len(candidates),160),dtype=int)] if candidates else []
            for i in sampled:
                if np.any(co[i]<lower) or np.any(co[i]>upper):continue
                p=Vector(co[i]);q,n,fi,d=trees[target].find_nearest(p)
                if q is not None and d>.0001 and inside_closed(trees[target],p):contained+=1;indices.add(i)
        classification='deferred_bilateral_contact' if frozenset((a,b)) in protected else 'ordinary_collision'
        frame=float(bpy.context.scene.frame_current_final)
        for window in profile.get('protected_windows',[]):
            if window['start']<=frame<=window['end'] and not a.startswith('hair') and any(r.startswith(('arm','hand')) for r in (a,b)):
                classification='deferred_intentional_window'
        rows.append({'pair':[a,b],'classification':classification,
          'triangle_crossings':count,'count_is_lower_bound':truncated,'bvh_candidates':len(candidates),
          'contained_samples':contained,'containment_status':'checked_closed_regions' if parts.get('closed',{}).get(a) and parts.get('closed',{}).get(b) else 'partial_open_regions_untested',
          'moving_vertices':sorted(used_a),'target_vertices':sorted(used_b),'examples':examples})
        if return_witness_pairs:rows[-1]['witness_pairs']=witnesses
    return {'frame':float(bpy.context.scene.frame_current_final),'pairs':rows,
      'ordinary_crossings':sum(r['triangle_crossings'] for r in rows if r['classification']=='ordinary_collision'),
      'ordinary_contained_samples':sum(r['contained_samples'] for r in rows if r['classification']=='ordinary_collision'),
      'deferred_crossings':sum(r['triangle_crossings'] for r in rows if r['classification']!='ordinary_collision')}

def intervals(rows):
    result=[];active={}
    for row in rows:
        f=row['frame'];present={tuple(p['pair']):p for p in row['pairs'] if p['triangle_crossings'] or p.get('contained_samples',0)}
        for pair in list(active):
            if pair not in present:result.append(active.pop(pair))
        for pair,p in present.items():
            if pair not in active:active[pair]={'pair':list(pair),'start_sample':f,'last_sample':f,'peak_crossings':0,'classification':p['classification']}
            active[pair]['last_sample']=f;active[pair]['peak_crossings']=max(active[pair]['peak_crossings'],p['triangle_crossings'])
    result.extend(active.values());return result
