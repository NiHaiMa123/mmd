"""Sampled Cartesian detour planning + analytic two-bone IK.

Explicit root envelope and final-skin body checks choose paths. The resulting
motion still needs subframe validation, visual review and hair re-simulation.
"""
import json
from pathlib import Path
import numpy as np
import bpy
from .surface import coords,audit_frame
from .root_envelope_feedback import capsule_features
from .two_bone_contact_path import apply_two_bone_goal


def interpolate_waypoints(waypoints,frame,mode='pchip'):
    times=np.array([w['frame'] for w in waypoints],dtype=float);values=np.array([w['offset']+[w['swivel']] for w in waypoints],dtype=float)
    if frame<=times[0]:return values[0].copy()
    if frame>=times[-1]:return values[-1].copy()
    i=int(np.searchsorted(times,frame)-1);h=np.diff(times);d=np.diff(values,axis=0)/h[:,None];u=(frame-times[i])/h[i]
    if mode=='linear':return values[i]*(1-u)+values[i+1]*u
    slopes=np.zeros_like(values)
    for j in range(1,len(times)-1):
        same=d[j-1]*d[j]>0;w1=2*h[j]+h[j-1];w2=h[j]+2*h[j-1]
        slopes[j,same]=(w1+w2)/(w1/d[j-1,same]+w2/d[j,same])
    return (2*u**3-3*u*u+1)*values[i]+(u**3-2*u*u+u)*h[i]*slopes[i]+(-2*u**3+3*u*u)*values[i+1]+(u**3-u*u)*h[i]*slopes[i+1]


def select_arm_route(layers,frames,max_correction_speed=None,prioritize_offset=False):
    """Minimize peak offset speed, then path cost, over feasible sampled nodes.

    Speed measures correction offsets, not total hand speed. No edge collision
    test is implied: interpolate, check subframes, then re-simulate the hair.
    An explicit speed ceiling is never relaxed when it makes a route impossible.
    """
    if len(layers)!=len(frames) or not layers or any(not layer for layer in layers):
        raise ValueError('Provide one nonempty candidate layer per frame')
    times=np.asarray(frames,dtype=float)
    if not np.all(np.isfinite(times)) or np.any(np.diff(times)<=0):
        raise ValueError('Frames must be finite and strictly increasing')
    if max_correction_speed is not None and (not np.isfinite(max_correction_speed) or max_correction_speed<0):
        raise ValueError('Correction speed ceiling must be finite and nonnegative')
    if prioritize_offset:
        peak=np.asarray([np.linalg.norm(n['offset']) for n in layers[0]],dtype=float)
        for i in range(1,len(layers)):
            current=[];dt=times[i]-times[i-1]
            for node in layers[i]:
                radius=np.linalg.norm(node['offset']);choices=[max(p,radius) if max_correction_speed is None or np.linalg.norm(np.asarray(node['offset'])-previous['offset'])<=max_correction_speed*dt+1e-12 else float('inf') for p,previous in zip(peak,layers[i-1])];current.append(min(choices))
            peak=np.asarray(current)
        bound=float(min(peak))
        if not np.isfinite(bound):raise RuntimeError('No route satisfies the explicit correction speed ceiling')
        filtered=[[n for n in layer if np.linalg.norm(n['offset'])<=bound+1e-10] for layer in layers];result=select_arm_route(filtered,frames,max_correction_speed,False);result['min_possible_peak_offset_m']=bound;result['objective']='minimum peak offset, then minimum peak correction speed, then cost';return result
    speeds=[];peak=np.zeros(len(layers[0]))
    for i in range(1,len(layers)):
        d=np.linalg.norm(np.asarray([n['offset'] for n in layers[i]])[:,None,:]-np.asarray([n['offset'] for n in layers[i-1]])[None,:,:],axis=2)/(times[i]-times[i-1])
        if not np.all(np.isfinite(d)):raise ValueError('Offsets must be finite')
        speeds.append(d);peak=np.min(np.maximum(d,peak[None,:]),axis=1)
    bound=float(min(peak))
    if max_correction_speed is not None and bound>max_correction_speed+1e-12:
        raise RuntimeError(f'No sampled route below correction speed ceiling {max_correction_speed}; minimum is {bound}')
    costs=np.asarray([n['cost'] for n in layers[0]],dtype=float);parents=[]
    for i,d in enumerate(speeds,1):
        current=[];parent=[]
        for k,node in enumerate(layers[i]):
            choices=[costs[j]+4*d[k,j]**2+.0005*(node['swivel']-previous['swivel'])**2+node['cost'] if d[k,j]<=bound+1e-8 else float('inf') for j,previous in enumerate(layers[i-1])]
            j=int(np.argmin(choices));parent.append(j);current.append(choices[j])
        parents.append(parent);costs=np.asarray(current)
    index=int(np.argmin(costs));chosen=[index]
    for parent in reversed(parents):index=parent[index];chosen.append(index)
    chosen.reverse()
    return {'waypoints':[dict(frame=frame,**layer[index]) for frame,layer,index in zip(frames,layers,chosen)],
            'min_possible_peak_correction_step_m_per_frame':bound,
            'correction_speed_ceiling_m_per_frame':max_correction_speed,
            'edges_collision_validated':False}


def plan_arm_detour(mesh,arm,profile,parts,envelope,frames,out,max_offset=.125,clearance=.008,max_correction_speed=None,prioritize_offset=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);chain=profile['control_chains'][0];bones=[arm.pose.bones[n] for n in chain];scene=bpy.context.scene
    if profile.get('units_to_m',1.)!=1.:raise ValueError('Detour collision experiment requires metre world coordinates')
    if len(profile['control_chains'])!=1:raise ValueError('Choose one arm control chain explicitly for a contact detour')
    if any(w['start']<=max(frames) and w['end']>=min(frames) for w in profile.get('protected_windows',[])):raise ValueError('Detour phase overlaps a protected intentional-contact window')
    count=int(envelope.get('root_guide_points',4))
    if count<2 or count>len(envelope['guide']):raise ValueError('Invalid fixed-root guide span')
    moving=np.array(sorted({i for r in envelope['moving_regions'] for i in parts['ids'][r]}));hand=np.array(parts['ids'][envelope['hand_region']]);anchor=envelope['anchor_bone'];bind=np.asarray(envelope['anchor_bind_matrix']);rest=np.asarray(envelope['guide'])[:count];radii=np.asarray(envelope['radii'])[:count]
    vectors=[(a,b,c) for a in (-1,0,1) for b in (-1,0,1) for c in (-1,0,1) if a or b or c]+[(0,2,1),(0,2,-1),(0,1,2),(0,1,-2)]
    directions=np.array(vectors,dtype=float);directions/=np.linalg.norm(directions,axis=1)[:,None];distances=sorted({d for d in (.025,.05,.075,.10,max_offset) if 0<d<=max_offset});offsets=[np.zeros(3)]+[v*d for d in distances for v in directions]
    # Discard translations/scales as DOFs, including matrix-decomposition noise.
    static={b.name:(b.location.copy(),b.scale.copy()) for b in bones};layers=[];log=[]
    for frame in frames:
        for b in bones:b.location=static[b.name][0];b.scale=static[b.name][1]
        scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();source=coords(mesh);baseq=[b.rotation_quaternion.copy() for b in bones];frame_local={b.name:(b.location.copy(),b.scale.copy()) for b in bones};wrist=np.array(arm.matrix_world@bones[2].head);matrix=np.array(arm.matrix_world@arm.pose.bones[anchor].matrix);delta=matrix@np.linalg.inv(bind);g=rest@delta[:3,:3].T+delta[:3,3];candidates=[];trials=0
        for offset in (offsets if frame not in (frames[0],frames[-1]) else [np.zeros(3)]):
            # Palm orientation is preserved, so translation is a cheap rejection
            # test. Actual weighted skin and forearm are checked after IK.
            gap,_=capsule_features(source[hand]+offset,g,radii)
            if gap.min()<0:continue
            for swivel in (0.,-.35,.35):
                if frame in (frames[0],frames[-1]) and swivel:continue
                for b,q in zip(bones,baseq):b.rotation_quaternion=q;b.location=frame_local[b.name][0];b.scale=frame_local[b.name][1]
                arm.update_tag();bpy.context.view_layer.update();detail=apply_two_bone_goal(arm,chain,wrist+offset,1.,swivel);trials+=1
                if detail['endpoint_error_m']>.0001 or detail['goal_clamp_m']>.0001:continue
                rotations=[base.rotation_difference(b.rotation_quaternion).angle for base,b in zip(baseq,bones)]
                if max(rotations[:2])>np.radians(35) or rotations[2]>np.radians(70):continue
                co=coords(mesh);gap,_=capsule_features(co[moving],g,radii)
                if gap.min()<clearance:continue
                audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=3000)
                if audit['ordinary_crossings'] or audit['ordinary_contained_samples']:continue
                correction=[list(base.inverted()@b.rotation_quaternion) for base,b in zip(baseq,bones)];cost=float(offset@offset+.0003*np.sum(np.square(rotations))+.0002*swivel*swivel)
                candidates.append({'offset':offset.tolist(),'swivel':swivel,'gap_m':float(gap.min()),'rotations_degrees':np.degrees(rotations).tolist(),'correction':correction,'cost':cost})
        candidates.sort(key=lambda x:x['cost']);candidates=candidates[:96]
        log.append({'frame':frame,'trials':trials,'feasible':len(candidates)});print('ARM_PATH_LAYER',frame,trials,len(candidates),flush=True)
        if not candidates:
            (out/'planning_failure.json').write_text(json.dumps({'failed_frame':frame,'log':log},indent=2),encoding='utf8');raise RuntimeError('No feasible detour candidates at frame '+str(frame))
        layers.append(candidates)
        (out/'candidate_layers.json').write_text(json.dumps({'frames':frames[:len(layers)],'layers':layers},ensure_ascii=False),encoding='utf8')
    selection=select_arm_route(layers,frames,max_correction_speed,prioritize_offset)
    result={'status':'DISCRETE_ARM_ROUTE_REQUIRES_VALIDATION',**selection,'sample_log':log,'clearance_m':clearance,'max_offset_m':max_offset,'original_actions_edited':False,'hair_accepted':False}
    (out/'planned_route.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
