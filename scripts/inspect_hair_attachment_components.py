import bpy,json,collections,numpy as np
from pathlib import Path
p=Path(r'E:\project\mmd\work\headswap_xl_codex');rows=json.loads((p/'standard_cloth_20261031/unanchored_components.json').read_text('utf8'))
bpy.ops.wm.open_mainfile(filepath=str(p/'jiggle_physics_20261031/candidate10/完整角色_Jiggle配置_未烘焙.blend'),use_scripts=False,load_ui=False)
m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架'];gn={g.index:g.name for g in m.vertex_groups}
z=np.load(p/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz')
np.save(p/'standard_cloth_20261031/hair_basis.npy',np.array([v.co[:] for v in m.data.shape_keys.key_blocks[0].data])[z['ids']])
for row in rows:
    counts=collections.Counter()
    for i in row['ids']:
        for g in m.data.vertices[i].groups:
            if gn[g.group] in arm.pose.bones:counts[gn[g.group]]+=g.weight
    row['weights']=dict(counts.most_common());print('ATTACHMENT',len(row['ids']),row['bbox'],row['weights'],flush=True)
(p/'standard_cloth_20261031/unanchored_components.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
