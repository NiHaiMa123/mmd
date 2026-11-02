"""Bake a local LBS/DQ blend without changing weights, rest mesh or bone motion.

This is a sampled joint-skinning corrective, not a contact solver. The caller
must independently audit the resulting mesh and motion at denser subframes.
"""
import bpy
import numpy as np
from .surface import coords
from .hair_position_cache import bind_position_cache


def bake_local_volume_skin(mesh, arm, ids, mask, anchor_bone, path, *,
                           first, last, step=.0625, blend=.75, fade=1.,
                           namespace='JointVolume'):
    ids=np.asarray(ids,dtype=int);mask=np.asarray(mask,dtype=float)
    if mask.shape!=ids.shape or not len(ids) or not np.all(np.isfinite(mask)) or np.any((mask<0)|(mask>1)):
        raise ValueError('Finite per-vertex blend weights in [0,1] required')
    if len(np.unique(ids))!=len(ids) or np.any(ids<0) or np.any(ids>=len(mesh.data.vertices)):
        raise ValueError('Unique valid source vertices required')
    if not all(np.isfinite(x) for x in (first,last,step,blend,fade)) or not first<last or step<=0 or fade<=0 or not 0<=blend<=1:
        raise ValueError('Invalid blend, fade or sample range')
    count=round((last-first)/step)
    if abs(first+count*step-last)>1e-7:raise ValueError('Cache step must divide the window')
    modifiers=[m for m in mesh.modifiers if m.type=='ARMATURE' and m.show_viewport]
    if len(modifiers)!=1 or modifiers[0].object!=arm:raise ValueError('One active source armature modifier required')
    modifier=modifiers[0]
    if modifier.use_deform_preserve_volume:raise ValueError('Source must use linear blend skinning')
    if anchor_bone not in arm.pose.bones:raise ValueError('Missing joint anchor')
    scene=bpy.context.scene;old_frame=scene.frame_current;old_subframe=scene.frame_subframe
    positions=[];anchors=[];maximum=0.
    try:
        for frame in np.linspace(first,last,count+1):
            scene.frame_set(int(frame),subframe=float(frame%1));bpy.context.view_layer.update();linear=coords(mesh)[ids]
            modifier.use_deform_preserve_volume=True;bpy.context.view_layer.update();dual=coords(mesh)[ids]
            modifier.use_deform_preserve_volume=False;bpy.context.view_layer.update()
            t=np.clip(min(frame-first,last-frame)/fade,0,1);t=t*t*(3-2*t)
            delta=t*blend*mask[:,None]*(dual-linear);maximum=max(maximum,float(np.linalg.norm(delta,axis=1).max()))
            positions.append(linear+delta);anchors.append(np.array(arm.matrix_world@arm.pose.bones[anchor_bone].matrix))
    finally:
        modifier.use_deform_preserve_volume=False;scene.frame_set(old_frame,subframe=old_subframe);bpy.context.view_layer.update()
    cache=bind_position_cache(mesh,ids,np.asarray(positions),path,first=first,
        sample_step=step,anchor_armature=arm,anchor_bone=anchor_bone,
        anchor_matrices=np.asarray(anchors),namespace=namespace)
    mesh.modifiers[-1].name='Local joint volume / measured range'
    return dict(cache=cache,vertices=len(ids),blend=blend,fade_frames=fade,
        maximum_skin_displacement_m=maximum,bone_motion_changed=False,
        source_weights_changed=False,source_rest_geometry_changed=False,
        requires_independent_subframe_audit=True)
