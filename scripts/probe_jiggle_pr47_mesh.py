"""Exercise the unmodified community mesh function and inspect character initial contact."""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
import numpy as np
from mathutils import Vector

repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
p=argparse.ArgumentParser();p.add_argument('--root',required=True)
p.add_argument('--boundary-only',action='store_true')
p.add_argument('--frame',type=int,default=1)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(a.root)
prov=json.loads((root/'plugin_provenance.json').read_text('utf8'))
path=Path(prov['source_dir'])/'__init__.py'
assert hashlib.sha256(path.read_bytes()).hexdigest()==prov['source_sha256']
spec=importlib.util.spec_from_file_location('community_mesh_readonly_probe',path)
plugin=importlib.util.module_from_spec(spec);spec.loader.exec_module(plugin)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2,location=(.1,0,0))
cube=bpy.context.object;cube.scale=(.1,1,1)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
bpy.context.view_layer.update()
cases=[('outside_near',(-.005,0,0),(-.025,0,0),(-.01,0,0)),
       ('cross_front',(.05,0,0),(-.05,0,0),(-.01,0,0)),
       ('outside_stationary',(-.05,0,0),(-.05,0,0),(-.05,0,0)),
       ('inside_stationary',(.05,0,0),(.05,0,0),(.05,0,0)),
       ('exit_from_inside',(-.03,0,0),(.05,0,0),(-.03,0,0))]
if a.boundary_only:
    cases.insert(2,('cross_front_shallow',(.005,0,0),(-.025,0,0),(-.01,0,0)))
tests=[]
for name,position,last,expected in cases:
    holder=SimpleNamespace(parent=SimpleNamespace(jiggle_settings=SimpleNamespace(collision_radius=.01)),position_last=Vector(last))
    try:
        result=plugin.VirtualParticle.mesh_collide(holder,cube,bpy.context.evaluated_depsgraph_get(),Vector(position))
        error=(result-Vector(expected)).length
        tests.append(dict(name=name,result=list(result),expected=expected,error_m=error,passed=error<1e-6))
    except Exception as exc:
        tests.append(dict(name=name,passed=False,error=repr(exc)))
report=dict(status='COMMUNITY_MESH_FUNCTION_PROBE',cases=tests,passed=all(r['passed'] for r in tests),plugin_source_sha256=prov['source_sha256'],solver_modified=False,simulation_started=False)
(root/('function_boundary_probe.json' if a.boundary_only else 'function_probe.json' if a.frame==1 else 'function_probe_at_worst_frame.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
if a.boundary_only:
    print(json.dumps(report,ensure_ascii=False),flush=True)
    raise SystemExit(0)
assert report['passed'],tests
base=repo.parent/'work/headswap_xl_codex'
cfg=json.loads((base/'jiggle_root_point_dance_075_15_20261102/configuration.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools()
source=cfg['source'] if a.frame==1 else json.loads((root/'candidate01/bake_report.json').read_text('utf8'))['blend']
bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(a.frame);bpy.context.view_layer.update()
actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature()
collider=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部']
skin_ids=np.load(base/'fullhair_repro_20261030/input_body_aware/skin_ids.npy')
faces=np.load(base/'fullhair_repro_20261030/input_body_aware/body_faces.npy')
skin=coords(actor)[skin_ids];co=coords(collider)
assert np.abs(co-skin).max()<5e-6
assert np.abs(np.array(collider.matrix_world)-np.eye(4)).max()<1e-9
field=ClosedColliderField(skin,faces);settings={r['name']:r for r in cfg['settings']}
rows=[]
for name,setting in settings.items():
    if not setting['enabled']:continue
    bone=arm.pose.bones[name]
    for kind,position,radius in [('head',arm.matrix_world@bone.head,settings.get(bone.parent.name,setting)['collision_radius']),('tail',arm.matrix_world@bone.tail,setting['collision_radius'])]:
        holder=SimpleNamespace(parent=SimpleNamespace(jiggle_settings=SimpleNamespace(collision_radius=radius)),position_last=position.copy())
        result=plugin.VirtualParticle.mesh_collide(holder,collider,bpy.context.evaluated_depsgraph_get(),position.copy())
        distance,_=field(np.array([position[:]]));delta=result-position
        rows.append(dict(bone=name,point=kind,skin_signed_distance_cm=float(distance[0]*100),projection_cm=delta.length*100,vertical_projection_cm=delta.z*100))
character=dict(status='INITIAL_CHARACTER_NATIVE_MESH_CONTACT_REVIEW' if a.frame==1 else 'BAKED_CHARACTER_MESH_CONTACT_DIAGNOSIS',frame=a.frame,rows=rows,
               max_projection_cm=max(r['projection_cm'] for r in rows),
               maximum_bone_point_depth_cm=max(0,-min(r['skin_signed_distance_cm'] for r in rows)),
               stationary_point_test_only=True,actual_integrator_state_not_reconstructed=True,
               sidehair=[r for r in rows if r['bone'].startswith('Sidehair')],
               mesh_matches_animated_skin=True,inside_points_are_ignored_by_backface_policy=True,
               simulation_started=False,geometry_changed=False,solver_modified=False)
(root/('initial_contact_probe.json' if a.frame==1 else 'worst_frame_contact_probe.json')).write_text(json.dumps(character,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(function_probe_passed=report['passed'],max_initial_projection_cm=character['max_projection_cm'],sidehair=character['sidehair']),ensure_ascii=False),flush=True)
