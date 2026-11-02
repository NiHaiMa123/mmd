import sys,json,argparse,time
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import mmd_profile,regions,audit_frame,intervals
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--profile');p.add_argument('--frames',nargs='*',type=int);p.add_argument('--step',type=int,default=15);p.add_argument('--body-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.source).resolve()),load_ui=False,use_scripts=False)
if a.profile:
 profile=json.loads(Path(a.profile).read_text('utf8'));mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']]
else:
 meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.attributes.get('SurfaceClass') and any(m.type=='ARMATURE' and m.object for m in o.modifiers)]
 if len(meshes)!=1:raise ValueError('Specify --profile when the scene does not have exactly one classified rigged mesh')
 mesh=meshes[0];arm=next(m.object for m in mesh.modifiers if m.type=='ARMATURE' and m.object);profile=mmd_profile(mesh,arm)
(out/'rig_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8')
parts=regions(mesh,arm,profile);report={'source':a.source,'method':'evaluated mesh BVH broadphase + strict triangle crossing; discrete samples, not CCD or containment proof',
 'regions':{r:{'triangles':len(fs),'vertices':len(parts['ids'][r])} for r,fs in parts['faces'].items()},
 'excluded_surface_triangles':parts['excluded_surface_triangles'],'unmapped_body_triangles':parts['missing_body_mapping'],'frames':[],'status':'AUDITING'}
start=time.monotonic()
for frame in a.frames or list(range(1,451,a.step))+[450]:
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();row=audit_frame(mesh,arm,profile,parts,hair=not a.body_only);report['frames'].append(row)
 print('SURFACE_AUDIT',frame,row['ordinary_crossings'],row['deferred_crossings'],flush=True)
 report['intervals']=intervals(report['frames']);(out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
report['status']='DISCRETE_SURFACE_AUDIT_COMPLETE';report['seconds']=time.monotonic()-start
rigids=[o for o in bpy.context.scene.objects if getattr(o,'mmd_type','')=='RIGID_BODY'];report['rigid_bodies']={'count':len(rigids),'types':{str(t):sum(str(o.mmd_rigid.type)==str(t) for o in rigids) for t in (0,1,2)}}
report['hair_deform_bones']=sorted({mesh.vertex_groups[g.group].name for i in parts['ids'].get('hair_mobile',[]) for g in mesh.data.vertices[i].groups if g.weight>.02})
(out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('TRANSFERABLE_AUDIT_COMPLETE',report['seconds'],flush=True)
