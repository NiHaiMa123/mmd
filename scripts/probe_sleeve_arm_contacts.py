import sys,json
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();fit=ROOT/'outputs/stockings_sleeves/v16';bpy.ops.wm.open_mainfile(filepath=str(fit/'work.blend'),load_ui=False,use_scripts=False);arm=bpy.data.objects['达妮娅_arm'];arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.mmd_tools.import_vmd(filepath=str(ROOT/'outputs/keqing_head/proportions_v2/mmd/grounded.vmd'),scale=.08,rename_bones=True,margin=0,log_level='ERROR');bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
rows=json.loads((fit/'physics_review/report.json').read_text(encoding='utf-8'))['frames']['1']['sleeves_crossings'];result={}
for side in ('L','R'):
    a,e,w=[arm.matrix_world@arm.pose.bones[p+'.'+side].head for p in ('腕','ひじ','手首')]
    data={'upper':list(a),'elbow':list(e),'wrist':list(w),'anchors':{p:list(bpy.data.objects['OutfitCollider_'+p+'.'+side].matrix_world.translation) for p in ('ひじ','手首')},'contacts':[]}
    for r in rows[::max(1,len(rows)//8)]:
        point=Vector(r['center']);details={}
        for name,head,tail in [('upper',a,e),('forearm',e,w)]:
            axis=tail-head;t=(point-head).dot(axis)/axis.length_squared;center=head+axis*max(0,min(1,t));details[name]={'t':t,'distance':(point-center).length}
        data['contacts'].append(details)
    result[side]=data
print('SLEEVE_CONTACT_BONES',json.dumps(result),flush=True)
