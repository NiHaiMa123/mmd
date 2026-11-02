"""Check the exported PMX/FK round trip before starting native physics."""
import argparse,sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.input)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'native_physics_input.blend'),load_ui=False,use_scripts=False)
mapping=json.loads((out/'bone_name_map.json').read_text('utf8'));oldarm=next(o for o in bpy.data.objects if o.type=='ARMATURE');aw=np.array(oldarm.matrix_world);ai=np.linalg.inv(aw);rest={name:np.array(oldarm.data.bones[name].matrix_local) for name in mapping.values()};source=np.load(out/'corrected_source_pose.npy',mmap_mode='r');names=list(mapping.values());prep=json.loads((out/'preparation.json').read_text('utf8'));preroll=prep['preroll']
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.mmd_tools.import_model(filepath=str(out/'character_physics.pmx'),scale=.08)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');byname={b.mmd_bone.name_j:b for b in arm.pose.bones};bpy.context.scene.frame_set(1)
for obj in bpy.context.selected_objects:obj.select_set(False)
arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.mmd_tools.import_vmd(filepath=str(out/'corrected_fk_preroll.vmd'),scale=.08,margin=0,bone_mapper='PMX',rename_bones=False,update_scene_settings=False,create_new_action=True)
rows=[];ia=np.array(arm.matrix_world);ii=np.linalg.inv(ia)
for f in [1,100,204,240,256,300,321,331,450]:
    bpy.context.scene.frame_set(f+preroll);bpy.context.view_layer.update();pe=[];de=[]
    for j,(alias,name) in enumerate(mapping.items()):
        if alias not in byname:continue
        b=byname[alias];expected=aw@source[f-1,j];actual=ia@np.array(b.matrix)
        pe.append(float(np.linalg.norm(actual[:3,3]-expected[:3,3])))
        ed=expected@np.linalg.inv(rest[name])@ai;ad=actual@np.linalg.inv(np.array(b.bone.matrix_local))@ii
        de.append(float(np.abs(ad-ed).max()))
    rows.append(dict(source_frame=f,imported_frame=f+preroll,max_bone_head_error_m=max(pe),p95_bone_head_error_m=float(np.quantile(pe,.95)),max_deform_matrix_error=max(de)))
report=dict(status='NATIVE_FK_ROUNDTRIP_PASS' if max(r['max_bone_head_error_m'] for r in rows)<.0002 and max(r['max_deform_matrix_error'] for r in rows)<.002 else 'NATIVE_FK_ROUNDTRIP_REQUIRES_FIX',samples=rows,physics_enabled=False,preroll=preroll)
(out/'fk_roundtrip.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report,indent=2),flush=True)
assert report['status']=='NATIVE_FK_ROUNDTRIP_PASS'
