"""Fit native sphere colliders once; the upstream Jiggle solver stays unchanged."""
import argparse
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField

p=argparse.ArgumentParser();p.add_argument('--out',required=True)
p.add_argument('--tolerance-cm',type=float,default=5.)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out)
out.mkdir(parents=True,exist_ok=True)
assert not (out/'collider_profile.json').exists()
base=repo.parent/'work/headswap_xl_codex';started=time.monotonic()
recipe=json.loads((base/'jiggle_root_point_dance_075_15_20261102/configuration.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=recipe['source'],load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature()
skin_ids=np.load(base/'fullhair_repro_20261030/input_body_aware/skin_ids.npy')
faces=np.load(base/'fullhair_repro_20261030/input_body_aware/body_faces.npy')
co=coords(actor);skin=co[skin_ids];field=ClosedColliderField(skin,faces)
old=list(bpy.data.collections['Jiggle_Physics_Colliders'].objects)
major=[o.constraints[0].subtarget for o in old]
groups={g.index:g.name for g in actor.vertex_groups}
nearest={}
for bone in arm.data.bones:
    b=bone
    while b and b.name not in major:b=b.parent
    nearest[bone.name]=b.name if b else None
weights=[]
for vi in skin_ids:
    score={}
    for g in actor.data.vertices[int(vi)].groups:
        n=nearest.get(groups[g.group])
        if n:score[n]=score.get(n,0)+g.weight
    weights.append(score)
# Regular spatial samples propose primitive centres. Distance to the actual
# closed skin determines each radius, not the old enclosing ellipsoid radius.
seed=[]
for obj in old:
    mat=np.array(obj.matrix_world);r=np.linalg.norm(mat[:3,:3],axis=0)
    axes=[np.linspace(-1,1,max(3,int(np.ceil(2*x/.015))+1)) for x in r]
    q=np.array(np.meshgrid(*axes,indexing='ij')).reshape(3,-1).T
    q=q[np.linalg.norm(q,axis=1)<1]
    seed.extend(q@mat[:3,:3].T+mat[:3,3])
seed=np.unique(np.round(np.asarray(seed),5),axis=0)
distance,_=field(seed);tolerance=a.tolerance_cm/100
valid=np.flatnonzero(distance<-(tolerance+.002))
assert len(valid),'No body core supports the requested intrusion tolerance'
selected=[]
for i in valid[np.argsort(distance[valid])]:
    centre=seed[i];radius=float(-distance[i]-tolerance)
    if any(np.linalg.norm(centre-q['world_center'])<q['radius_m']*.8 for q in selected):continue
    _,_,fi,_=field.tree.find_nearest(Vector(centre))
    score={}
    for v in faces[fi]:
        for n,w in weights[int(v)].items():score[n]=score.get(n,0)+w
    assert score
    bone=max(score,key=score.get)
    inv=np.linalg.inv(np.array(arm.matrix_world@arm.pose.bones[bone].matrix))
    local=inv[:3,:3]@centre+inv[:3,3]
    selected.append(dict(name=f'Jiggle_InnerSkin_{len(selected):03d}_{bone}',bone=bone,
                         center=local.tolist(),radius_m=radius,
                         world_center=centre.tolist(),skin_clearance_at_center_m=float(-distance[i])))
assert len(selected)<300,('Unexpected primitive count',len(selected))
# Check every original hair bone point against the same native sphere shape
# expanded by its upstream collision radius. This is a static geometry audit.
settings={r['name']:r for r in recipe['settings']};contacts=[]
for name,setting in settings.items():
    if not setting['enabled']:continue
    bone=arm.pose.bones[name]
    for kind,point,radius in [('head',arm.matrix_world@bone.head,
                              settings.get(bone.parent.name,setting)['collision_radius']),
                             ('tail',arm.matrix_world@bone.tail,setting['collision_radius'])]:
        for sphere in selected:
            overlap=sphere['radius_m']+radius-np.linalg.norm(np.array(point)-sphere['world_center'])
            if overlap>.0001:contacts.append(dict(bone=name,point=kind,collider=sphere['name'],projection_cm=float(overlap*100)))
coverage=np.max(np.array([q['radius_m']-np.linalg.norm(seed[valid]-q['world_center'],axis=1) for q in selected]),axis=0)
profile=dict(status='STATIC_NATIVE_SPHERE_PROFILE_REQUIRES_DYNAMIC_REVIEW',source=recipe['source'],
             method='Union of skin-inscribed native sphere empties; one-time geometry fit, upstream Jiggle unchanged',
             actual_skin_inset_m=tolerance,existing_hair_collision_radii_retained=True,
             tolerance_scope='Approximate bone-sphere contact envelope; actual rendered hair still requires independent depth verification',
             primitives=selected,initial_contacts=contacts,initial_max_projection_cm=max([r['projection_cm'] for r in contacts],default=0),
             sample_spacing_m=.015,seed_count=len(seed),core_seed_count=len(valid),
             uncovered_core_seed_fraction=float(np.mean(coverage<0)),
             maximum_core_seed_gap_m=float(max(0,-coverage.min())),
             simulation_started=False,source_modified=False,elapsed_s=time.monotonic()-started)
(out/'collider_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in profile.items() if k not in ['primitives','initial_contacts']},ensure_ascii=False),flush=True)
