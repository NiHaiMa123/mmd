"""Inspect actual selected-surface topology before native cloth setup."""
import json,sys
from pathlib import Path
from collections import Counter
import bpy,bmesh,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions
from animation_contact_tools.hair_bundle_profile import resolve_bundle
base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle';config=json.loads((base/'bundle_L_rig_roots.json').read_text('utf8'));profile=json.loads(Path(config['source_profile']).read_text('utf8'));source=base/'left_arm_feedback_rig_roots/baked/Body_With_Attachment_Detour.blend';out=base.parent/'surface_proxy_20261029';out.mkdir(exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];bundle=resolve_bundle(mesh,arm,regions(mesh,arm,profile),config);ids=bundle['ids'];lookup={int(v):i for i,v in enumerate(ids)};initial=np.load(base/'left_rig_root_native/initial_projection.npz');points=initial['coordinates'];faces=[[lookup[i] for i in f] for f in bundle['faces']];bm=bmesh.new();vs=[bm.verts.new(p) for p in points]
for f in faces:
 try:bm.faces.new([vs[i] for i in f])
 except ValueError:pass
def stats(bm):return {'vertices':len(bm.verts),'edges':len(bm.edges),'faces':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'edges_above_two_faces':sum(len(e.link_faces)>2 for e in bm.edges),'loose_edges':sum(not e.link_faces for e in bm.edges)}
before=stats(bm);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-8);after=stats(bm);data=bpy.data.meshes.new('InspectionSurface');bm.to_mesh(data);bm.free();obj=bpy.data.objects.new('InspectionSurface',data);bpy.context.scene.collection.objects.link(obj);cloth=obj.modifiers.new('RNA inspect','CLOTH');settings={}
for name in ('quality','mass','air_damping','tension_stiffness','compression_stiffness','shear_stiffness','bending_stiffness','bending_model','pin_stiffness','use_internal_springs','internal_spring_max_length','internal_spring_max_diversion','internal_tension_stiffness','internal_compression_stiffness','use_pressure','uniform_pressure_force','use_pressure_volume','target_volume','vertex_group_mass','use_dynamic_mesh'):
 prop=cloth.settings.bl_rna.properties.get(name)
 if prop:settings[name]={'default':getattr(cloth.settings,name),'description':prop.description,'min':getattr(prop,'hard_min',None),'max':getattr(prop,'hard_max',None)}
report={'source':str(source),'bundle':str(base/'bundle_L_rig_roots.json'),'topology_before':before,'topology_after_micron_weld':after,'dimensions_m':np.ptp(points,axis=0).tolist(),'settings':settings};(out/'inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('SURFACE_PROXY_INSPECTION',json.dumps(report,ensure_ascii=False),flush=True)
