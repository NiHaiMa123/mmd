"""Adaptive subframe repair of an existing additive correction layer."""
import numpy as np
import bpy
from mathutils import Quaternion
from .surface import audit_frame
from .projector import FrameProjector
from .track import fcurves

def refine_layer(mesh,arm,profile,parts,original,delta,first=1,last=450,step=.5,passes=3,limit_degrees=25):
    if not 0<step<=1:raise ValueError('Refinement step must be in (0,1] frames')
    solver=FrameProjector(mesh,arm,profile,parts,profile['control_chains'],limit_degrees=limit_degrees)
    ad=arm.animation_data;allbones=[arm.pose.bones[n] for chain in profile['control_chains'] for n in chain];history=[]
    def evaluate(frame):bpy.context.scene.frame_set(int(frame),subframe=float(frame%1));bpy.context.view_layer.update()
    def read_seed(frame):
        lookup={(c.data_path,c.array_index):c for c in fcurves(delta)};values=[]
        for b in solver.bones:
            path=b.path_from_id('rotation_quaternion');q=Quaternion([lookup[(path,i)].evaluate(frame) for i in range(4)])
            q.normalize()
            if q.w<0:q.negate()
            values.extend(q.to_exponential_map())
        return np.array(values)
    for iteration in range(passes):
        ad.action=None;ad.use_nla=True;bad=[]
        for frame in np.arange(first,last+step*.25,step):
            evaluate(float(frame));r=audit_frame(mesh,arm,profile,parts,hair=False,cap=2000)
            if r['ordinary_crossings'] or r.get('ordinary_contained_samples',0):bad.append(float(frame))
        print('CONTACT_REFINE_SCAN',iteration,'bad_samples',len(bad),flush=True)
        if not bad:break
        for frame in bad:
            seed=read_seed(frame);ad.use_nla=False;ad.action=original;evaluate(frame);solver.capture();base=[b.rotation_quaternion.copy() for b in allbones]
            best_x,best=solver.solve(initial=seed,preferred=seed,iterations=35)
            if best.get('remaining_crossings',0):
                x,other=solver.solve(preferred=seed,iterations=35)
                if other.get('remaining_crossings',10**8)<best.get('remaining_crossings',10**8):best_x,best=x,other
            if best.get('remaining_crossings',0):
                # Deterministic bounded local escape; every candidate still needs
                # the independent actual-skin audit, not just a distance score.
                rng=np.random.default_rng(int(round(frame*1000)))
                for _ in range(profile.get('local_restart_count',4)):
                    x,other=solver.solve(initial=best_x+rng.normal(0,np.radians(4),solver.n),preferred=seed,iterations=35)
                    if other.get('remaining_crossings',10**8)<best.get('remaining_crossings',10**8):best_x,best=x,other
                    if not best.get('remaining_crossings',0):break
            solver.apply(best_x);qd=[]
            for b,q0 in zip(allbones,base):
                q=q0.inverted()@b.rotation_quaternion
                if q.w<0:q.negate()
                qd.append(q)
            ad.action=delta
            for b,q in zip(allbones,qd):b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
            for c in fcurves(delta):
                for key in c.keyframe_points:key.interpolation='LINEAR'
            history.append({'pass':iteration,'frame':frame,'status':best['status'],'remaining':best.get('remaining_crossings',0),'max_delta_deg':best.get('max_control_delta_deg',0)})
            if len(history)%25==0:print('CONTACT_REFINE_PROGRESS',iteration,frame,'samples_repaired',len(history),'remaining_here',best.get('remaining_crossings',0),flush=True)
            ad.action=None;ad.use_nla=True
    remaining=[];ad.action=None;ad.use_nla=True
    for frame in np.arange(first,last+step*.25,step):
        evaluate(float(frame));r=audit_frame(mesh,arm,profile,parts,hair=False,cap=2000)
        if r['ordinary_crossings'] or r.get('ordinary_contained_samples',0):remaining.append({'frame':float(frame),'crossings':r['ordinary_crossings'],'contained':r.get('ordinary_contained_samples',0)})
    return {'status':'ADAPTIVE_DISCRETE_BODY_PASS' if not remaining else 'ADAPTIVE_BODY_UNRESOLVED','step_frames':step,
      'samples':len(np.arange(first,last+step*.25,step)),'remaining':remaining,'history':history,'ccd_guarantee':False}
