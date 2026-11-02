"""An object anchor must preserve rotating/translating subframe replay on reload."""
import json, sys
from pathlib import Path
import bpy, numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addon'))
from animation_contact_tools.hair_position_cache import bind_position_cache
from animation_contact_tools.surface import coords
bpy.ops.wm.read_factory_settings(use_empty=True)
data = bpy.data.meshes.new('CacheMesh')
data.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
mesh = bpy.data.objects.new('CacheMesh', data)
bpy.context.scene.collection.objects.link(mesh)
anchor = bpy.data.objects.new('MovingAnchor', None)
bpy.context.scene.collection.objects.link(anchor)
for frame, location, angle in [(1, (2, -1, .4), 0), (2, (3, 1, .6), 1.2)]:
    anchor.location = location
    anchor.rotation_euler.z = angle
    anchor.keyframe_insert('location', frame=frame)
    anchor.keyframe_insert('rotation_euler', frame=frame)
local = np.array([[[.2, .1, 0]], [[.4, .1, 0]]])
matrices = []
positions = []
for k, frame in enumerate((1, 2)):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    matrix = np.array(anchor.matrix_world)
    matrices.append(matrix)
    positions.append(local[k] @ matrix[:3, :3].T + matrix[:3, 3])
out = ROOT / 'outputs/object_anchor_cache_contract'
out.mkdir(parents=True, exist_ok=True)
for invalid in (np.zeros((0,1,3)),np.full((2,1,3),np.nan)):
    try:bind_position_cache(mesh,[0],invalid,out/'invalid.pc2')
    except ValueError:pass
    else:raise AssertionError('Invalid motion was accepted')
assert not (out/'invalid.pc2').exists()
metadata = bind_position_cache(mesh, [0], positions, out / 'object.pc2',
                               anchor_object=anchor, anchor_matrices=matrices)
error = 0.
def check():
    global error
    for frame in (1, 1.125, 1.5, 1.875, 2):
        bpy.context.scene.frame_set(int(frame), subframe=frame % 1)
        bpy.context.view_layer.update()
        matrix = np.array(bpy.data.objects['MovingAnchor'].matrix_world)
        point = local[0] * (2-frame) + local[1] * (frame-1)
        expected = point @ matrix[:3, :3].T + matrix[:3, 3]
        actual = coords(bpy.data.objects['CacheMesh'])
        error = max(error, float(np.max(np.abs(actual[:1]-expected))))
        np.testing.assert_array_equal(actual[1:], [[1, 0, 0], [0, 1, 0]])
    assert error < 1e-6, error
check()
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'ObjectAnchor.blend'))
bpy.ops.wm.open_mainfile(filepath=str(out / 'ObjectAnchor.blend'), load_ui=False, use_scripts=False)
check()
result = dict(status='OBJECT_ANCHOR_SUBFRAME_RELOAD_PASS', error_m=error, metadata=metadata)
(out / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf8')
print('OBJECT_ANCHOR_CACHE', json.dumps(result), flush=True)
