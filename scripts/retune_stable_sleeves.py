"""Mass-normalized sleeve solver variant, preserving the old skirt cache."""
import sys,json,shutil,argparse
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--out',default='outputs/cynical_cloth15/sleeve_light');p.add_argument('--mass',type=float,default=.001);p.add_argument('--quality',type=int,default=32);p.add_argument('--air',type=float,default=.5);p.add_argument('--stiffness',type=float,default=400);p.add_argument('--no-skirt',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);engine('import_export').ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/sleeve_fixed';out=(ROOT/a.out).resolve();out.mkdir(parents=True,exist_ok=True)
shutil.copytree(ROOT/'outputs/cynical_cloth15/chest_hd/blendcache_Cynical_Cloth_15s',out/'blendcache_Cynical_Cloth_15s',dirs_exist_ok=True)
for name in ('setup.json','simulation_report.json','cloth_setup.json','CREDITS.txt','chest_repair.json','torso_template.json','chest_geometry_audit.json','sleeve_repair_setup.json'):shutil.copyfile(source/name,out/name)
bpy.ops.wm.open_mainfile(filepath=str(source/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;obj=bpy.data.objects['StableSleeveSimulationSurface'];sim=next(m for m in obj.modifiers if m.type=='CLOTH');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True)
with bpy.context.temp_override(scene=scene,object=obj,active_object=obj,point_cache=sim.point_cache):bpy.ops.ptcache.free_bake()
sim.settings.mass=a.mass;sim.settings.air_damping=a.air;sim.settings.quality=a.quality;sim.settings.tension_stiffness=a.stiffness;sim.settings.compression_stiffness=a.stiffness;sim.settings.shear_stiffness=a.stiffness*.6
if a.no_skirt:
 collider=bpy.data.objects['CachedSkirtSleeveCollider']
 if sim.collision_settings.collection.objects.get(collider.name):sim.collision_settings.collection.objects.unlink(collider)
report=json.loads((out/'sleeve_repair_setup.json').read_text(encoding='utf-8'));report.update({'quality':a.quality,'vertex_mass_kg':a.mass,'total_particle_mass_kg':a.mass*len(obj.data.vertices),'air_damping':a.air,'stiffness':a.stiffness,'cached_skirt_collision':not a.no_skirt});(out/'sleeve_repair_setup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True);print('SLEEVE_MASS_NORMALIZED',a.mass,sim.point_cache.is_baked,flush=True)
