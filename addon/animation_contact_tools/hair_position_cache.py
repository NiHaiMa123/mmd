"""World-space measured hair positions -> non-destructive, indexed mesh replay."""
import struct
from pathlib import Path
import bpy,numpy as np
from .native_hair_surface import new_tree,named,integer_compare


def bind_position_cache(mesh,ids,positions,path,first=1,anchor_armature=None,anchor_bone=None,anchor_matrices=None,sample_step=1.,namespace=None,allow_overlap=False,anchor_object=None):
    ids=np.asarray(ids,dtype=int);positions=np.asarray(positions,dtype='<f4');path=Path(path).resolve()
    if positions.ndim!=3 or positions.shape[1:]!=(len(ids),3):raise ValueError('Expected frames x selected vertices x 3 world coordinates')
    if not len(positions) or not np.all(np.isfinite(positions)):raise ValueError('Nonempty finite cache positions required')
    if not np.isfinite(sample_step) or sample_step<=0:raise ValueError('Positive finite cache sampling step required')
    if len(np.unique(ids))!=len(ids) or np.any(ids<0) or np.any(ids>=len(mesh.data.vertices)):raise ValueError('Unique valid source vertex indices required')
    prefix='HairContact_MeasuredIndex';name=prefix
    if namespace is not None:
        if not namespace or len(namespace)>24 or not all(c.isascii() and (c.isalnum() or c=='_') for c in namespace):raise ValueError('Cache namespace requires 1-24 ASCII letters, digits or underscores')
        name=prefix+'_'+namespace
        if name in mesh.data.attributes:raise ValueError('Cache namespace already exists; use a fresh namespace')
    else:
        suffix=1
        while name in mesh.data.attributes:name=prefix+'_'+str(suffix);suffix+=1
    if not allow_overlap:
        for existing in mesh.data.attributes:
            if existing.name.startswith(prefix) and existing.domain=='POINT' and existing.data_type=='INT':
                mask=np.empty(len(mesh.data.vertices),dtype=np.int32);existing.data.foreach_get('value',mask)
                if np.any(mask[ids]>=0):raise ValueError('Cache selection overlaps an existing measured-hair binding; compose corrections before binding')
    if anchor_armature is not None and anchor_object is not None:raise ValueError('Choose either a bone or an object anchor')
    anchored=anchor_armature is not None or anchor_object is not None
    if anchored:
        if anchor_matrices is None or (anchor_armature is not None and anchor_bone not in anchor_armature.pose.bones):raise ValueError('Explicit anchor and sampled world matrices required')
        matrices=np.asarray(anchor_matrices,dtype=float)
        if matrices.shape!=(len(positions),4,4) or not np.all(np.isfinite(matrices)):raise ValueError('Finite anchor matrices must match every cache frame')
        inverse=np.linalg.inv(matrices);positions=(np.einsum('fij,fvj->fvi',inverse[:,:3,:3],positions)+inverse[:,None,:3,3]).astype('<f4')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('wb') as stream:
        stream.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,len(ids),0.,sample_step,len(positions)));stream.write(positions.tobytes())
    data=bpy.data.meshes.new('HairContact_MeasuredPoints');data.from_pydata(positions[0].tolist(),[],[]);carrier=bpy.data.objects.new('HairContact_MeasuredPoints',data);bpy.context.scene.collection.objects.link(carrier);carrier.hide_render=True;carrier.hide_set(True)
    if anchored:
        constraint=carrier.constraints.new('COPY_TRANSFORMS');constraint.target=anchor_object if anchor_object is not None else anchor_armature
        if anchor_object is None:constraint.subtarget=anchor_bone
        constraint.target_space='WORLD';constraint.owner_space='WORLD'
    mod=carrier.modifiers.new('Measured hair motion','MESH_CACHE');mod.cache_format='PC2';mod.filepath=str(path);mod.play_mode='SCENE';mod.time_mode='FRAME';mod.frame_start=first;mod.frame_scale=1.;mod.deform_mode='OVERWRITE';mod.interpolation='LINEAR'
    if sample_step!=1.:
        # FRAME playback indexes PC2 samples, rather than using the header step.
        # A simple frame driver avoids the modifier's scene scale/offset coupling.
        mod.play_mode='CUSTOM';driver=mod.driver_add('eval_frame').driver;driver.expression=f'(frame - {float(first):.17g}) / {float(sample_step):.17g}'
    attr=mesh.data.attributes.new(name,'INT','POINT');indices=np.full(len(mesh.data.vertices),-1,dtype=np.int32);indices[ids]=np.arange(len(ids),dtype=np.int32);attr.data.foreach_set('value',indices)
    tree,inp,out=new_tree('HairContact_MeasuredMotion');links=tree.links;info=tree.nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=carrier
    sample=tree.nodes.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT';links.new(info.outputs['Geometry'],sample.inputs['Geometry']);position=tree.nodes.new('GeometryNodeInputPosition');links.new(position.outputs['Position'],sample.inputs['Value']);index=named(tree,name,'INT');links.new(index,sample.inputs['Index'])
    selected=integer_compare(tree,links,index,'GREATER_EQUAL',0);time=tree.nodes.new('GeometryNodeInputSceneTime')
    def compare_time(operation,value):
        node=tree.nodes.new('FunctionNodeCompare');node.data_type='FLOAT';node.operation=operation;node.inputs[1].default_value=value;links.new(time.outputs['Frame'],node.inputs[0]);return node.outputs[0]
    last=first+(len(positions)-1)*sample_step;begin=compare_time('GREATER_EQUAL',first);end=compare_time('LESS_EQUAL',last)
    for test in (begin,end):
        both=tree.nodes.new('FunctionNodeBooleanMath');both.operation='AND';links.new(selected,both.inputs[0]);links.new(test,both.inputs[1]);selected=both.outputs[0]
    setpos=tree.nodes.new('GeometryNodeSetPosition');links.new(inp.outputs['Geometry'],setpos.inputs['Geometry']);links.new(selected,setpos.inputs['Selection']);links.new(sample.outputs['Value'],setpos.inputs['Position']);links.new(setpos.outputs['Geometry'],out.inputs['Geometry']);modifier=mesh.modifiers.new('Measured hair motion / experimental range','NODES');modifier.node_group=tree
    return {'cache':str(path),'carrier':carrier.name,'selection_attribute':name,'frames':[first,last],'sample_step':sample_step,'topology_changed':False,'outside_range':'original evaluated geometry','interpolation':'anchor-local positions + exact animated anchor' if anchored else 'linear world point cache; audited separately','anchor_bone':anchor_bone if anchor_armature is not None else None,'anchor_object':anchor_object.name if anchor_object is not None else None}
