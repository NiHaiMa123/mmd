"""Check native Cloth Dynamics pin motion before using it on the character."""
import bpy,sys,json,numpy as np
from pathlib import Path
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from animation_contact_tools.native_hair_surface import asset_path,new_tree,named,group
from animation_contact_tools.surface import coords
out=repo.parent/'work/headswap_xl_codex/side_surface_20261101/pin_motion_probe';out.mkdir(exist_ok=True,parents=True);rows=[]
for zero_mass in [False,True]:
 bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene;s.render.fps=30;s.frame_end=4
 mesh=bpy.data.meshes.new('PinMotionProbe');mesh.from_pydata([(x,0,1-z) for z in [0,.02,.04,.06] for x in [-.01,.01]],[],[(2*j,2*j+1,2*j+3,2*j+2) for j in range(3)]);ob=bpy.data.objects.new('PinMotionProbe',mesh);s.collection.objects.link(ob)
 pin=mesh.attributes.new('HairRootPin','FLOAT','POINT');pin.data.foreach_set('value',[1,1,0,0,0,0,0,0])
 with bpy.data.libraries.load(str(asset_path()),link=False) as (src,dst):dst.node_groups=['Cloth Dynamics (Experimental)']
 tree,inp,output=new_tree('PinMotionProbe');links=tree.links;move=tree.nodes.new('GeometryNodeTransform');links.new(inp.outputs['Geometry'],move.inputs['Geometry'])
 for f,x in [(1,0),(2,.02),(3,.03),(4,.03)]:move.inputs['Translation'].default_value=(x,0,0);move.inputs['Translation'].keyframe_insert('default_value',frame=f)
 cloth=group(tree,dst.node_groups[0]);links.new(move.outputs['Geometry'],cloth.inputs['Geometry']);links.new(named(tree,'HairRootPin'),cloth.inputs['Pin Group']);cloth.inputs['Stretchiness'].default_value=0.;cloth.inputs['Bendiness'].default_value=.025;cloth.inputs['Substeps'].default_value=20;cloth.inputs['Constraint Steps'].default_value=60
 cloth.inputs['Mass'].default_value=.01;next(x for x in cloth.inputs if x.name=='Gravity' and x.type=='BOOLEAN').default_value=False
 if zero_mass:
  inv=tree.nodes.new('ShaderNodeMath');inv.operation='SUBTRACT';inv.inputs[0].default_value=1.;links.new(named(tree,'HairRootPin'),inv.inputs[1]);scale=tree.nodes.new('ShaderNodeMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=.01;links.new(inv.outputs[0],scale.inputs[0]);links.new(scale.outputs[0],cloth.inputs['Mass'])
 links.new(cloth.outputs['Geometry'],output.inputs['Geometry']);md=ob.modifiers.new('NativeCloth','NODES');md.node_group=tree
 errors=[]
 for f,x in [(1,0),(2,.02),(3,.03),(4,.03)]:
  s.frame_set(f);bpy.context.view_layer.update();c=coords(ob);errors.append(float(np.max(np.linalg.norm(c[:2]-np.array([[-.01+x,0,1],[.01+x,0,1]]),axis=1))))
 rows.append(dict(zero_mass_pins=zero_mass,pin_errors_m=errors,maximum_pin_error_m=max(errors)))
choice=min(rows,key=lambda r:r['maximum_pin_error_m']);assert choice['maximum_pin_error_m']<.0001,rows
(out/'result.json').write_text(json.dumps(dict(status='NATIVE_CLOTH_PIN_MOTION_VERIFIED',tests=rows,selected_zero_mass_pins=choice['zero_mass_pins'],character_physics_started=False),indent=2),'utf8');print(json.dumps(rows),flush=True)
