from pathlib import Path
import sys
import json
from collections import Counter
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
d = engine("dressing")
for obj in engine("import_export").model_meshes():
    names = d.dominant_bones(obj)
    ids = [v.index for v in obj.data.vertices if v.co.z < .10 and v.co.x > 0]
    counts = Counter(names[i] for i in ids)
    print(obj.name, counts, flush=True)
    for group in counts:
        points = [obj.data.vertices[i].co for i in ids if names[i] == group]
        print(group, [round(min(p[k] for p in points), 4) for k in range(3)],
              [round(max(p[k] for p in points), 4) for k in range(3)], flush=True)
