"""Read-only collider geometry diagnosis of the baked short-side-hair lift."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
import numpy as np

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
p=argparse.ArgumentParser();p.add_argument('--root',required=True)
p.add_argument('--report-name',default='floating_short_hair_analysis.json')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(a.root)
base=repo.parent/'work/headswap_xl_codex'
accepted=base/'jiggle_root_point_dance_075_15_20261102'
config=json.loads((root/'configuration.json').read_text('utf8'))
preparation=json.loads((Path(config['source']).parent/'configuration.json').read_text('utf8'))
path=Path(preparation['plugin']['source_dir'])/'__init__.py'
spec=importlib.util.spec_from_file_location('jiggle_read_only_collision_formula',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
# No register(), no bake, no handlers: use only the upstream pure collision test.
engine('import_export').ensure_mmd_tools()
settings={r['name']:r for r in config['settings']}
skin=np.load(base/'fullhair_repro_20261030/input_body_aware/skin_ids.npy')
faces=np.load(base/'fullhair_repro_20261030/input_body_aware/body_faces.npy')
points={};rows=[];frames=[1,226,331,376,450]
receipt=json.loads((accepted/'bake_report.json').read_text('utf8'))
bpy.ops.wm.open_mainfile(filepath=receipt['blend'],load_ui=False,use_scripts=False)
scene=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature()
for f in frames:
    scene.frame_set(f);bpy.context.view_layer.update()
    co=coords(actor);field=ClosedColliderField(co[skin],faces)
    for side in ['L','R']:
        for i in range(3,8):
            name=f'Sidehair{i}.{side}';bone=arm.pose.bones[name]
            position=arm.matrix_world@bone.head
            radius=settings[bone.parent.name]['collision_radius']
            holder=SimpleNamespace(bone=bone,parent=SimpleNamespace(jiggle_settings=SimpleNamespace(collision_radius=radius)))
            world_radius=sum((bone.id_data.matrix_world@bone.matrix).to_scale())/3*radius
            distance,_=field(np.array([position[:]]))
            contacts=[]
            for collider in bpy.data.collections['Jiggle_Physics_Colliders'].objects:
                projected=module.VirtualParticle.empty_collide(holder,collider,position.copy())
                delta=projected-position
                holder.parent.jiggle_settings.collision_radius=0.
                zero_projected=module.VirtualParticle.empty_collide(holder,collider,position.copy())
                holder.parent.jiggle_settings.collision_radius=radius
                if delta.length>.001:
                    contacts.append(dict(collider=collider.name,projection_cm=delta.length*100,
                                         vertical_projection_cm=delta.z*100,
                                         zero_hair_radius_projection_cm=(zero_projected-position).length*100,
                                         zero_hair_radius_vertical_projection_cm=(zero_projected-position).z*100,
                                         projection_vector_cm=(np.array(delta)*100).tolist()))
            contacts.sort(key=lambda x:x['projection_cm'],reverse=True)
            rows.append(dict(frame=f,bone=name,actual_skin_signed_distance_cm=float(distance[0]*100),
                             world_hair_collision_radius_cm=world_radius*100,
                             upstream_individual_collider_responses=contacts))
        points[f,side]=np.array(arm.matrix_world@arm.pose.bones[f'Sidehair7.{side}'].tail)
candidate=json.loads((root/'bake_report.json').read_text('utf8'))
bpy.ops.wm.open_mainfile(filepath=candidate['blend'],load_ui=False,use_scripts=False)
scene=bpy.context.scene;arm=bpy.data.objects['东雪莲x达妮娅_骨架'];lift=[]
for f in frames:
    scene.frame_set(f);bpy.context.view_layer.update()
    for side in ['L','R']:
        point=np.array(arm.matrix_world@arm.pose.bones[f'Sidehair7.{side}'].tail)
        delta=(point-points[f,side])*100
        lift.append(dict(frame=f,side=side,tip_vertical_change_cm=float(delta[2]),tip_displacement_cm=float(np.linalg.norm(delta))))
report=dict(status='READ_ONLY_COLLIDER_LIFT_DIAGNOSIS',baseline=str(accepted),candidate=str(root),
            individual_collider_tests=rows,short_sidehair_tip_changes=lift,
            note='Pure upstream collision formula evaluated on approved no-collision bone points; each collider tested independently. This diagnoses proxy geometry, not a new dynamics solve or proof of all preceding contact history.',
            simulation_started=False,geometry_changed=False,pose_changed=False)
(root/a.report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(status=report['status'],tip_changes=lift),ensure_ascii=False),flush=True)
