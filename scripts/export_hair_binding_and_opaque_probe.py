import argparse,sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(exist_ok=True,parents=True);src=Path(a.delivery);pub=json.loads((src/'cache_publication.json').read_text('utf8'));ids=np.load(Path(pub['input'])/'hair_ids.npy');engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(src/'完整角色_整头连续物理_15秒.blend'),load_ui=False,use_scripts=False);m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架'];s=bpy.context.scene;s.frame_set(1);names=[g.name for g in m.vertex_groups];w=np.zeros((len(ids),len(names)),dtype=np.float32)
for row,i in enumerate(ids):
 for g in m.data.vertices[i].groups:w[row,g.group]=g.weight
active=np.asarray([i for i in np.flatnonzero(w.sum(0)>0) if names[i] in arm.pose.bones]);groups=[names[i] for i in active];np.savez_compressed(out/'hair_binding.npz',weights=w[:,active],names=np.asarray(groups),parents=np.asarray([arm.data.bones[name].parent.name if arm.data.bones[name].parent else '' for name in groups]),bone_matrices=np.asarray([arm.matrix_world@arm.pose.bones[name].matrix for name in groups]));metadata=dict(groups=groups,parents={b.name:b.parent.name if b.parent else None for b in arm.data.bones},head='頭');(out/'hair_binding.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=16;s.cycles.use_denoising=True;s.frame_set(326);s.render.filepath=str(out/'fresh_normal_326.png');bpy.ops.render.render(write_still=True)
mat=bpy.data.materials['Body'];mat.node_tree.nodes.clear();em=mat.node_tree.nodes.new('ShaderNodeEmission');em.inputs['Color'].default_value=(.55,.55,.55,1);op=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(em.outputs[0],op.inputs['Surface']);s.render.filepath=str(out/'opaque_body_326.png');bpy.ops.render.render(write_still=True);print('BINDING_AND_OPAQUE_PROBE_DONE',flush=True)
