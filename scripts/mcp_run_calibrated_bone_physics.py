"""Continuously record the original PMX bone-chain physics through Blender MCP."""
import bpy,json,sys,time,traceback
from pathlib import Path
import numpy as np
ROOT=Path(r'E:\project\mmd\mmd_repo');JOB=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/calibrated_proxy_chain'
KEY='MMD_CALIBRATED_NATIVE_CHAIN_20261030';state=bpy.app.driver_namespace[KEY]
assert state['stage']=='READY_FOR_CONTINUOUS_PHYSICS',state
sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.surface import coords
scene=bpy.data.scenes[state['scene']];arm=bpy.data.objects[state['armature']];mesh=bpy.data.objects[state['mesh']]
data=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware';initial=np.load(data/'hair_initial.npy');reference=np.load(data/'hair_original.npy');edges=np.load(data/'hair_edges.npy');hard=np.load(data/'hard_roots.npy');mapped=np.load(JOB/'native_vertex_map.npy');anchors=np.load(data/'anchors.npy',mmap_mode='r')[:,-1]
native0=np.load(JOB/'native_head_initial.npy');native0[:3,3]*=.08;native0inv=np.linalg.inv(native0);source0inv=np.linalg.inv(anchors[0]);restlength=np.linalg.norm(reference[edges[:,0]]-reference[edges[:,1]],axis=1);valid=restlength>.0005
scene.rigidbody_world.enabled=False;scene.frame_set(1);bpy.context.view_layer.update();native_initial=coords(mesh)[mapped]*.08;error=float(np.linalg.norm(native_initial-initial,axis=1).max());assert error<.0003,('Physics build changed initial binding',error)
delta=initial-native_initial
assert not (JOB/'raw_positions.npy').exists(),'Existing record cannot be silently overwritten'
positions=np.lib.format.open_memmap(JOB/'raw_positions.npy',mode='w+',dtype='<f4',shape=(450,len(initial),3))
names=[b.name for b in arm.pose.bones if not b.is_mmd_shadow_bone];poses=np.lib.format.open_memmap(JOB/'bone_poses.npy',mode='w+',dtype='<f4',shape=(480,len(names),4,4));(JOB/'bone_names.json').write_text(json.dumps(names,ensure_ascii=False),'utf8')
rows=[];current=0;started=time.monotonic()
def status(stage,**extra):
    state.update(stage=stage,**extra);tmp=JOB/'status.tmp.json';tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf8');tmp.replace(JOB/'status.json')
def tick():
    global current
    try:
        assert bpy.context.scene==scene,'Active scene changed; stopping to protect user work'
        assert scene.rigidbody_world.enabled,'Physics was disabled'
        current+=1;scene.frame_set(current);bpy.context.view_layer.update()
        poses[current-1]=np.asarray([np.array(arm.pose.bones[n].matrix) for n in names])
        if current>30:
            f=current-30;k=(f-1)*8;native=np.array(arm.matrix_world@arm.pose.bones[state['head_bone']].matrix);native[:3,3]*=.08
            sr=anchors[k]@source0inv;nr=native@native0inv;correction=sr@np.linalg.inv(nr);x=coords(mesh)[mapped]*.08;x=x@correction[:3,:3].T+correction[:3,3]+delta@sr[:3,:3].T
            expected=initial@sr[:3,:3].T+sr[:3,3];rooterr=float(np.linalg.norm(x[hard]-expected[hard],axis=1).max());x[hard]=expected[hard];positions[f-1]=x.astype(np.float32)
            ratio=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1)[valid]/restlength[valid];row=dict(frame=f,native_frame=current,min_edge_ratio=float(ratio.min()),max_edge_ratio=float(ratio.max()),root_error_before_numerical_replay_m=rooterr)
            rows.append(row)
            if f%15==0:
                positions.flush();poses.flush();status('SIMULATING_ORIGINAL_BONE_PHYSICS',**row,elapsed_s=time.monotonic()-started);(JOB/'progress.json').write_text(json.dumps(rows,indent=2),'utf8')
            if ratio.max()>2 or ratio.min()<.5:raise RuntimeError(f'Original bone physics still distorts the displayed hair: {row}')
        if current>=480:
            positions.flush();poses.flush();(JOB/'progress.json').write_text(json.dumps(rows,indent=2),'utf8');status('PHYSICAL_BONE_RECORD_COMPLETE_REQUIRES_DISPLAY_CONTACT_AND_VISUAL_REVIEW',frames=450,elapsed_s=time.monotonic()-started)
            bpy.ops.wm.save_as_mainfile(filepath=str(JOB/'original_bone_physics_recorded.blend'),compress=True)
            return None
        return .01
    except BaseException as exc:
        positions.flush();poses.flush();(JOB/'progress.json').write_text(json.dumps(rows,indent=2),'utf8');status('FAILED',native_frame=current,error=repr(exc),traceback=traceback.format_exc());return None
scene.rigidbody_world.enabled=True
assert scene.rigidbody_world.enabled
status('SIMULATING_ORIGINAL_BONE_PHYSICS',physics_world_enabled=True,native_frame=0,frame=0,initial_bind_error_m=error);bpy.app.timers.register(tick,first_interval=.1)
print(json.dumps(dict(started=True,frames=480,preroll=30,body_motion_source='validated corrected FK',status=str(JOB/'status.json'))))
