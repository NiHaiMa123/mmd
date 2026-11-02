"""Inspect reference blend data only: no auto scripts, playback, bake or render."""
import collections
import hashlib
import json
from pathlib import Path
import bpy

ROOT = Path(r'E:\project\mmd\work\hair_reference_projects_20261102')
files = [ROOT/'Wiggle2_2023_bug_reproduction.blend']
downloads = json.loads((ROOT/'source_blend_downloads.json').read_text(encoding='utf-8'))
files += [Path(row['path']) for row in downloads if row['status']=='DOWNLOADED_SIZE_AND_HASH_CHECKED']
rows = []


def plain(value):
    if hasattr(value, 'to_dict'):
        return {k:plain(v) for k,v in value.to_dict().items()}
    if hasattr(value, 'to_list'):
        return value.to_list()
    if isinstance(value,(bool,int,float,str)) or value is None:
        return value
    return str(value)


for path in files:
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    scene = bpy.context.scene
    objects, rigs, particles = [], [], []
    for obj in bpy.data.objects:
        objects.append(dict(name=obj.name,type=obj.type,modifiers=[dict(name=m.name,type=m.type) for m in obj.modifiers]))
        if obj.type=='ARMATURE':
            bones=[]
            for bone in obj.pose.bones:
                props={key:plain(bone[key]) for key in bone.keys() if 'wiggle' in key.lower() or 'jiggle' in key.lower()}
                bones.append(dict(name=bone.name,parent=bone.parent.name if bone.parent else None,
                                  length=bone.bone.length,connected=bone.bone.use_connect,physics_properties=props))
            rigs.append(dict(name=obj.name,bones=bones,object_physics_properties={key:plain(obj[key]) for key in obj.keys() if 'wiggle' in key.lower() or 'jiggle' in key.lower()}))
        for ps in obj.particle_systems:
            particles.append(dict(object=obj.name,name=ps.name,type=ps.settings.type,count=ps.settings.count,
                                  hair_length=ps.settings.hair_length,use_hair_dynamics=ps.use_hair_dynamics))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    row=dict(file=str(path),sha256=before,scene=scene.name,fps=scene.render.fps,fps_base=scene.render.fps_base,
             frame_range=[scene.frame_start,scene.frame_end],object_types=dict(collections.Counter(o.type for o in bpy.data.objects)),
             objects=objects,armatures=rigs,particle_systems=particles,node_groups=[g.name for g in bpy.data.node_groups],
             embedded_text_names=[t.name for t in bpy.data.texts],scripts_disabled=True,new_simulation=False,new_render=False,source_unchanged=True)
    rows.append(row)
    (ROOT/'blend_inspection.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('REFERENCE_INSPECTED',json.dumps(dict(file=path.name,object_types=row['object_types'],rigs=len(rigs),particle_systems=len(particles),scripts_disabled=True),ensure_ascii=False),flush=True)
