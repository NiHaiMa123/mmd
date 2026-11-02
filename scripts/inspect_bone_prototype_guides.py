"""Read-only source-tail versus prototype-tail check before physical guides."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--prototype',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.prototype)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'完整角色_27分束原始蒙皮_未启用物理.blend'),use_scripts=False,load_ui=False)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
src=bpy.data.objects['东雪莲x达妮娅_骨架'];rig=bpy.data.objects[s['HairPrototypeRig']]
C=rig.matrix_world.inverted()@src.matrix_world
chains=json.loads((ROOT.parent/'work/headswap_xl_codex/standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))['chains']
rows=[]
for chain in chains:
    for parent,child in zip(chain['bones'][:-1],chain['bones'][1:]):
        a,b=src.pose.bones[parent],src.pose.bones[child];pa,pb=rig.data.bones[parent],rig.data.bones[child]
        rows.append(dict(parent=parent,child=child,source_tail_to_child_gap_m=((C@a.tail)-(C@b.head)).length,
            prototype_tail_to_child_gap_m=(pa.tail_local-pb.head_local).length,
            source_to_prototype_head_error_m=((C@a.head)-pa.head_local).length,
            source_to_prototype_tail_error_m=((C@a.tail)-pa.tail_local).length,
            source_length_m=((C@a.tail)-(C@a.head)).length,prototype_length_m=pa.length))
report=dict(rows=rows,source_tail_max_gap_m=max(r['source_tail_to_child_gap_m'] for r in rows),
    prototype_tail_max_gap_m=max(r['prototype_tail_to_child_gap_m'] for r in rows),
    source_to_prototype_tail_error_max_m=max(r['source_to_prototype_tail_error_m'] for r in rows),
    matrix_scale=list(C.to_scale()),physics_computed=False)
(out/'source_guide_rest_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False),flush=True)
