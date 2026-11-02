"""Inspect existing author data only; never save or simulate the source file."""
import bpy
import argparse
import json
import sys
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--out', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
bpy.ops.wm.open_mainfile(filepath=a.source, load_ui=False, use_scripts=False)
rig = bpy.data.objects['夏安-Rig']
action = rig.animation_data.action
curves = []
for layer in action.layers:
    for strip in layer.strips:
        for bag in getattr(strip, 'channelbags', []):
            curves.extend(bag.fcurves)
seen = set()
curves = [c for c in curves if not (c.as_pointer() in seen or seen.add(c.as_pointer()))]
hair = []
for bone in rig.pose.bones:
    if not bone.name.startswith('Hair'):
        continue
    path = bone.path_from_id()
    channels = []
    for curve in curves:
        if not curve.data_path.startswith(path + '.'):
            continue
        points = curve.keyframe_points
        vals = [float(k.co.y) for k in points]
        channels.append(dict(path=curve.data_path, index=curve.array_index,
                             keys=len(points), first=float(points[0].co.x) if points else None,
                             last=float(points[-1].co.x) if points else None,
                             value_range=[min(vals), max(vals)] if vals else []))
    hair.append(dict(bone=bone.name, constraints=[c.type for c in bone.constraints], channels=channels,
                     properties={k: repr(v) for k, v in bone.items()},
                     data_properties={k: repr(v) for k, v in bone.bone.items()}))
texts = [dict(object=o.name, text=o.data.body) for o in bpy.data.objects if o.type == 'FONT']
result = dict(source=a.source, action=action.name, hair=hair, scene_text=texts,
              rig_properties={k: repr(v) for k, v in rig.items()},
              scene_properties={k: repr(v) for k, v in bpy.context.scene.items()})
Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print('AUTHOR_HAIR_DETAILS_COMPLETE', len(hair), len(texts), flush=True)
