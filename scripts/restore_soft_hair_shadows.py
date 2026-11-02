import argparse,sys,json
from pathlib import Path
import bpy
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);bpy.ops.wm.open_mainfile(filepath=a.blend,load_ui=False,use_scripts=False);mat=bpy.data.materials['Hair'];tree=mat.node_tree;mix=tree.nodes['PortraitHairSoftShadow'];ray=tree.nodes['PortraitHairRayType'];node=tree.nodes.get('SoftPhysicalHairShadow') or tree.nodes.new('ShaderNodeMath');node.name='SoftPhysicalHairShadow';node.operation='MULTIPLY';node.inputs[1].default_value=.65
for link in list(mix.inputs[0].links):tree.links.remove(link)
tree.links.new(ray.outputs['Is Shadow Ray'],node.inputs[0]);tree.links.new(node.outputs[0],mix.inputs[0]);bpy.ops.wm.save_as_mainfile(filepath=a.blend,compress=True,relative_remap=False);print('SOFT_HAIR_SHADOW_RESTORED_35_PERCENT',flush=True)
