"""Independent reload, protected data, foot tracks and half-frame QA."""
import sys,json,argparse,hashlib,math
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,contacts,compact
p=argparse.ArgumentParser();p.add_argument('--fit',default='sequence_v5/temporal');p.add_argument('--step',type=float,default=.5);p.add_argument('--baseline');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=ROOT/'outputs/cynical_cloth15/contact_motion'/a.fit;engine('import_export').ensure_mmd_tools();baseline=json.loads(Path(a.baseline).read_text(encoding='utf-8')) if a.baseline else None
def geometry(obj):
    h=hashlib.sha256();co=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',co);h.update(co.tobytes())
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',co);h.update(co.tobytes())
    return h.hexdigest()
def action_digest(action):
    h=hashlib.sha256()
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    h.update(str((fc.data_path,fc.array_index)).encode());h.update(str([(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in fc.keyframe_points]).encode())
    return h.hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);base={o.name:geometry(o) for o in engine('import_export').model_meshes()};source_digest=action_digest(bpy.data.objects['达妮娅_arm'].animation_data.action)
bpy.ops.wm.open_mainfile(filepath=str(folder/'ContactMotion.blend'),load_ui=False,use_scripts=False);arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];scene=bpy.context.scene;corrected=arm.animation_data.action;original=bpy.data.actions['シニカルナイトプラン_bone'];actual={name:geometry(bpy.data.objects[name]) for name in base};assert base==actual,'Original mesh or morph coordinates changed';assert action_digest(original)==source_digest,'Preserved original action changed'
for o in bpy.data.objects:
    if o.type=='MESH' and o!=body:o.hide_viewport=True
regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);report=dict(protected_meshes_and_morphs=len(base),original_action_preserved=True,scope='arms, gloves, torso, skin head, opposing legs; excludes same-hand fingers, hair, decorations; sampled QA is not CCD',intersection_segment_tolerance_m=.00002,sample_step_frames=a.step,frames={},foot_max_matrix_difference=0.)
frames=np.arange(47,496+a.step*.1,a.step);feet={}
for label,action in [('before',original),('after',corrected)]:
    arm.animation_data.action=action;rows={}
    for n,f in enumerate(frames):
        scene.frame_set(int(f),subframe=float(f%1));bpy.context.view_layer.update();key=f'{f:g}';row=baseline['frames']['before'][key] if baseline and label=='before' else compact(contacts(body,arm,regions,.002,True));rows[key]=row
        matrices=np.array([np.asarray(arm.pose.bones[b].matrix) for b in ('足首D.L','足首D.R','足ＩＫ.L','足ＩＫ.R') if b in arm.pose.bones])
        if label=='before':feet[key]=matrices
        else:report['foot_max_matrix_difference']=max(report['foot_max_matrix_difference'],float(np.max(np.abs(feet[key]-matrices))))
        if n%100==0:print('CONTACT_DENSE_QA',label,key,row['triangle_crossings'],flush=True)
    report['frames'][label]=rows;report[label]=dict(samples=len(rows),crossing_samples=sum(r['triangle_crossings']>0 for r in rows.values()),crossing_pairs=sum(r['triangle_crossings'] for r in rows.values()),worst_pairs=max(r['triangle_crossings'] for r in rows.values()))
    (folder/'dense_contact_qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert report['foot_max_matrix_difference']<1e-6,'Foot/root contact track changed'
print('CONTACT_QA_SUMMARY',json.dumps({k:v for k,v in report.items() if k!='frames'}),flush=True)
