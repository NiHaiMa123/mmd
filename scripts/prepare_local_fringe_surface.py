"""Prepare one native Surface Deform fringe and 26 unchanged bone-driven locks."""
import argparse
import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np

repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(repo / 'addon'), str(repo / 'scripts')]
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from local_fringe_surface_binding import configure

p = argparse.ArgumentParser()
p.add_argument('--prepared', required=True)
p.add_argument('--accepted-cache-check', required=True)
p.add_argument('--out', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
assert not (out / 'setup.json').exists()
checked = json.loads((Path(a.accepted_cache_check) / 'result.json').read_text('utf-8-sig'))
assert checked['status'] == 'LOCAL_FRINGE_SURFACE_EXISTING_CACHE_WITHIN_5CM'
assert len(checked['samples']) == 233 and checked['stop'] is None
prepared = json.loads((Path(a.prepared) / 'setup.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=prepared['blend'], load_ui=False, use_scripts=False)
s = bpy.context.scene
actor = bpy.data.objects['东雪莲x达妮娅_素体']
s.frame_set(1)
bpy.context.view_layer.update()
initial = coords(actor)
mapping = configure(actor)
assert np.abs(coords(actor) - initial).max() < .0001
surface = actor.modifiers[mapping['modifier']]
controls = []
for frame in [1, 151, 226, 331, 376, 450]:
    s.frame_set(frame)
    bpy.context.view_layer.update()
    actual = coords(actor)
    surface.show_viewport = False
    bpy.context.view_layer.update()
    reference = coords(actor)
    surface.show_viewport = True
    bpy.context.view_layer.update()
    error = float(np.abs(actual - reference).max())
    assert error < .0001, ('Unsimulated rigid head transfer mismatch', frame, error)
    controls.append(dict(frame=frame, rigid_head_transfer_error_m=error))
cache = out / 'cache'
cache.mkdir(exist_ok=True)
for ob in bpy.data.objects:
    for md in ob.modifiers:
        if md.type == 'MESH_CACHE':
            src = Path(bpy.path.abspath(md.filepath))
            assert not src.name.startswith('ClassicHair_'), 'Cannot resume solver from display PC2'
            dst = cache / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
            md.filepath = str(dst)
s.frame_set(1)
s.frame_end = 450
blend = out / '完整角色_左刘海表面绑定_其余发骨跟踪_未物理.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
prepared.update(status='FULL_HEAD_LOCAL_FRINGE_SURFACE_READY', blend=str(blend),
                source_prepared=prepared['blend'], local_surface_mapping=mapping,
                display_transfer=mapping['method'], surface_deform_active=True,
                cache_mapping_check=checked['blend'], rigid_head_controls=controls,
                original_weights_edited=False, new_physics_started=False)
(out / 'setup.json').write_text(json.dumps(prepared, ensure_ascii=False, indent=2), 'utf8')
print(json.dumps(dict(stage='LOCAL_FRINGE_SURFACE_PREPARED', blend=str(blend),
                      controls=controls), ensure_ascii=False), flush=True)
