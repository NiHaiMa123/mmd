"""Attach an existing PC2 file without loading its whole animation into RAM."""
import struct
from pathlib import Path
import bpy,numpy as np
from .native_hair_surface import new_tree,named,integer_compare

def bind_streamed_cache(mesh,ids,path,*,first=1,anchor_armature,anchor_bone,namespace):
 path=Path(path).resolve();ids=np.asarray(ids,dtype=np.int32)
 with path.open('rb') as f:
  magic,version,count,start,step,samples=struct.unpack('<12siiffi',f.read(32));initial=np.frombuffer(f.read(count*12),dtype='<f4').reshape(count,3).copy()
 assert magic==b'POINTCACHE2\0' and version==1 and count==len(ids) and len(set(ids))==count
 assert path.stat().st_size==32+samples*count*12 and samples>0 and step>0
 assert anchor_bone in anchor_armature.pose.bones
 name='HairContact_MeasuredIndex_'+namespace
 if name in mesh.data.attributes:raise ValueError('Use a new namespace')
 for attr in mesh.data.attributes:
  if attr.name.startswith('HairContact_MeasuredIndex') and attr.domain=='POINT' and attr.data_type=='INT':
   values=np.empty(len(mesh.data.vertices),dtype=np.int32);attr.data.foreach_get('value',values)
   if np.any(values[ids]>=0):raise ValueError('Remove superseded bindings in the new working copy before attaching the complete head')
 data=bpy.data.meshes.new('FullHair_PhysicsPoints');data.from_pydata(initial.tolist(),[],[]);carrier=bpy.data.objects.new('FullHair_PhysicsPoints',data);bpy.context.scene.collection.objects.link(carrier);carrier.hide_render=True;carrier.hide_set(True)
 c=carrier.constraints.new('COPY_TRANSFORMS');c.target=anchor_armature;c.subtarget=anchor_bone;c.target_space='WORLD';c.owner_space='WORLD'
 mod=carrier.modifiers.new('Continuous full-head physics cache','MESH_CACHE');mod.cache_format='PC2';mod.filepath=str(path);mod.play_mode='CUSTOM';mod.time_mode='FRAME';mod.deform_mode='OVERWRITE';mod.interpolation='LINEAR';driver=mod.driver_add('eval_frame').driver;driver.expression=f'(frame - {float(first):.17g}) / {float(step):.17g}'
 attr=mesh.data.attributes.new(name,'INT','POINT');indices=np.full(len(mesh.data.vertices),-1,dtype=np.int32);indices[ids]=np.arange(count,dtype=np.int32);attr.data.foreach_set('value',indices)
 tree,inp,out=new_tree('FullHair_ContinuousPhysics');links=tree.links;info=tree.nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=carrier;sample=tree.nodes.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT';links.new(info.outputs['Geometry'],sample.inputs['Geometry']);position=tree.nodes.new('GeometryNodeInputPosition');links.new(position.outputs['Position'],sample.inputs['Value']);index=named(tree,name,'INT');links.new(index,sample.inputs['Index']);selected=integer_compare(tree,links,index,'GREATER_EQUAL',0);clock=tree.nodes.new('GeometryNodeInputSceneTime');last=first+(samples-1)*step
 for operation,value in [('GREATER_EQUAL',first),('LESS_EQUAL',last)]:
  test=tree.nodes.new('FunctionNodeCompare');test.data_type='FLOAT';test.operation=operation;test.inputs[1].default_value=value;links.new(clock.outputs['Frame'],test.inputs[0]);both=tree.nodes.new('FunctionNodeBooleanMath');both.operation='AND';links.new(selected,both.inputs[0]);links.new(test.outputs[0],both.inputs[1]);selected=both.outputs[0]
 setpos=tree.nodes.new('GeometryNodeSetPosition');links.new(inp.outputs['Geometry'],setpos.inputs['Geometry']);links.new(selected,setpos.inputs['Selection']);links.new(sample.outputs['Value'],setpos.inputs['Position']);links.new(setpos.outputs['Geometry'],out.inputs['Geometry']);modifier=mesh.modifiers.new('Full head / continuous bundle physics and body contact','NODES');modifier.node_group=tree
 return dict(carrier=carrier.name,selection_attribute=name,cache=str(path),first=first,last=last,step=float(step),samples=samples,anchor_bone=anchor_bone)
