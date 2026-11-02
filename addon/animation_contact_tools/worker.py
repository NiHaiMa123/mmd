"""Portable background entry point; no dependency on this project's paths."""
import sys,json,argparse,traceback
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from animation_contact_tools.surface import regions,audit_frame,intervals
from animation_contact_tools.track import solve_track
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True);p.add_argument('--mode',choices=['audit','solve','hair-experiment'],required=True);p.add_argument('--first',type=int,default=1);p.add_argument('--last',type=int,default=450);p.add_argument('--step',type=int,default=5);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
def status(state,**kwargs):(out/'job_status.json').write_text(json.dumps({'state':state,**kwargs},ensure_ascii=False),encoding='utf8')
try:
    status('running',mode=a.mode)
    profile=json.loads(Path(a.profile).read_text('utf8'))
    import addon_utils
    for module in ('bl_ext.blender_org.mmd_tools','mmd_tools'):
        try:
            addon_utils.enable(module,default_set=False,persistent=False)
            if hasattr(bpy.types.Object,'mmd_type'):break
        except Exception:pass
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.source).resolve()),load_ui=False,use_scripts=False)
    mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile)
    if a.mode=='audit':
        rows=[]
        for f in range(a.first,a.last+1,a.step):
            bpy.context.scene.frame_set(f);bpy.context.view_layer.update();rows.append(audit_frame(mesh,arm,profile,parts))
        (out/'surface_audit.json').write_text(json.dumps({'frames':rows,'intervals':intervals(rows),'closed_regions':parts['closed'],'unmapped_body_triangles':parts['missing_body_mapping'],'discrete_not_ccd':True},ensure_ascii=False,indent=2),encoding='utf8')
        status('complete',result=str(out/'surface_audit.json'))
    elif a.mode=='hair-experiment':
        from animation_contact_tools.hair_track import solve_hair_track
        result=solve_hair_track(mesh,arm,profile,out,first=a.first,last=a.last,step=a.step)
        status('complete',acceptance='HAIR_UNRESOLVED_EXPERIMENT',result=str(out/'HairContact_LayerCandidate_NotAccepted.blend'),hair_solved=False,ccd_guarantee=False)
    else:
        result=solve_track(mesh,arm,profile,parts,out,first=a.first,last=a.last)
        from animation_contact_tools.adaptive import refine_layer
        refined=refine_layer(mesh,arm,profile,parts,bpy.data.actions[result['original_action']],bpy.data.actions[result['correction_action']],first=a.first,last=a.last,step=profile.get('verification_step',.25),limit_degrees=profile.get('rotation_limit_degrees',25))
        (out/'adaptive_report.json').write_text(json.dumps(refined,ensure_ascii=False,indent=2),encoding='utf8');target=out/'ContactCorrected_Candidate.blend'
        bpy.context.scene.frame_set(a.first);bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(target),compress=True)
        status('complete',acceptance=refined['status'],result=str(target),checked_pairs=profile['pairs'],protected_windows=profile.get('protected_windows',[]),hair_solved=False,ccd_guarantee=False)
except Exception as e:
    status('failed',error=str(e));traceback.print_exc();raise
