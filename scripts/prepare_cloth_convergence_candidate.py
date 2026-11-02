"""Clone the legal initial full scene; change only stock Cloth quality steps."""
import argparse,json,sys,shutil
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--out',required=True)
p.add_argument('--quality',type=int,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);baseline=Path(a.baseline);out=Path(a.out)
out.mkdir(parents=True,exist_ok=True);assert not (out/'configuration.json').exists(),'Use a fresh directory'
config=json.loads((baseline/'configuration.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=config['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;proxy=bpy.data.objects['HairProxy_全头共享几何体积']
cloth=next(md for md in proxy.modifiers if md.type=='CLOTH');assert not cloth.point_cache.is_baked
assert not cloth.point_cache.use_external,'Do not reuse an explicit external physics cache'
old_quality=cloth.settings.quality;cloth.settings.quality=a.quality
s.frame_set(1);bpy.context.view_layer.update()
display=bpy.data.objects[s['HairDisplayObject']];order=np.argsort([x.value for x in display.data.attributes['SourceVertexID'].data])
actual=coords(display)[order];expected=np.load(baseline/'initial_display_audit/hair_world_1.npy')
error=float(np.max(np.abs(actual-expected)));assert error<5e-6,('Initial geometry changed',error)
path=out/'完整角色_原生Cloth子步收敛_未烘焙.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
for name in ['clump_proxy_rest.npz','clump_assets.json','geometric_topology.json']:
    shutil.copy2(baseline/name,out/name)
config.update(blend=str(path),cloth_quality=cloth.settings.quality,
    convergence_baseline=str(baseline),controlled_change={'cloth.quality':{'before':old_quality,'after':cloth.settings.quality}},
    baseline_initial_display_coordinate_error_m=error,mesh_regularization_used=False,
    source_static_mesh_quality='Original legal rest cage retained for a timestep-only convergence comparison',
    frames=[1,s.frame_end],physics_baked=False,acceptance='NOT_ACCEPTED')
(out/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(status='CONVERGENCE_CANDIDATE_READY',blend=str(path),
    controlled_change=config['controlled_change'],initial_error_m=error),ensure_ascii=False),flush=True)
