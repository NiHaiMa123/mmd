"""Length-preserving two-bone IK for an explicitly chosen contact detour.

The geometric route is configurable and must be verified against final skin
and re-simulated hair. Neither bone translations nor scales are repair DOFs.
"""
import numpy as np
import bpy
from mathutils import Vector,Matrix,Quaternion


def smooth_detour(frame,start,end):
    if frame<=start or frame>=end:return 0.
    return float(np.sin(np.pi*(frame-start)/(end-start))**4)


def clamp_reachable_goal(shoulder,lengths,target_world,margin=1e-5):
    shoulder=np.asarray(shoulder,dtype=float);target=np.asarray(target_world,dtype=float);direction=target-shoulder;distance=float(np.linalg.norm(direction));a,b=map(float,lengths)
    if distance<1e-8:raise ValueError('IK goal coincides with arm root')
    if min(a,b)<=margin or not np.all(np.isfinite(target)):raise ValueError('Invalid arm lengths or target')
    reachable=max(abs(a-b)+margin,min(a+b-margin,distance));return shoulder+direction*(reachable/distance),abs(distance-reachable)


def apply_two_bone_goal(arm,chain,target_world,preserve_wrist=1.,swivel=0.):
    upper,elbow,wrist=[arm.pose.bones[n] for n in chain];mw=arm.matrix_world;inv=mw.inverted();s=mw@upper.head;e=mw@elbow.head;w=mw@wrist.head;target=Vector(target_world);a=(e-s).length;b=(w-e).length;oldq=(mw@wrist.matrix).to_quaternion();local={bone.name:(bone.location.copy(),bone.scale.copy()) for bone in (upper,elbow,wrist)}
    direction=target-s;distance=direction.length
    if distance<1e-8:raise ValueError('IK goal coincides with arm root')
    u=direction/distance;reachable=max(abs(a-b)+1e-5,min(a+b-1e-5,distance));along=(a*a+reachable*reachable-b*b)/(2*reachable);height=np.sqrt(max(a*a-along*along,0));pole=e-s-u*(e-s).dot(u)
    if pole.length<1e-7:raise ValueError('Source elbow plane is singular; supply a pole adapter')
    pole.normalize();pole=Quaternion(u,float(swivel))@pole;wanted_elbow=s+u*along+pole*height;clamped_target=s+u*reachable
    def rotate(bone,pivot,current,wanted):
        if current.length<1e-8 or wanted.length<1e-8:raise ValueError('Zero-length arm segment')
        q=current.rotation_difference(wanted);world=mw@bone.matrix;world=Matrix.Translation(pivot)@q.to_matrix().to_4x4()@Matrix.Translation(-pivot)@world;bone.matrix=inv@world;bone.location=local[bone.name][0];bone.scale=local[bone.name][1];arm.update_tag();bpy.context.view_layer.update()
    rotate(upper,s,e-s,wanted_elbow-s);e=mw@elbow.head;w=mw@wrist.head;rotate(elbow,e,w-e,clamped_target-e)
    world=mw@wrist.matrix;follow=world.to_quaternion();orientation=follow.slerp(oldq,float(preserve_wrist));world=orientation.to_matrix().to_4x4();world.translation=mw@wrist.head;wrist.matrix=inv@world;wrist.location=local[wrist.name][0];wrist.scale=local[wrist.name][1];arm.update_tag();bpy.context.view_layer.update()
    location_error=max((bone.location-local[bone.name][0]).length for bone in (upper,elbow,wrist));scale_error=max((bone.scale-local[bone.name][1]).length for bone in (upper,elbow,wrist));endpoint_error=((mw@wrist.head)-target).length
    return {'endpoint_error_m':endpoint_error,'goal_clamp_m':abs(distance-reachable),'local_translation_error':location_error,'local_scale_error':scale_error}
