"""PC2 quarter-frame playback must respect its sampling interval."""
import json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.hair_position_cache import bind_position_cache
from animation_contact_tools.surface import coords
bpy.ops.wm.read_factory_settings(use_empty=True);data=bpy.data.meshes.new('CacheFixture');data.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)]);mesh=bpy.data.objects.new('CacheFixture',data);bpy.context.scene.collection.objects.link(mesh);out=ROOT/'outputs/subframe_cache_contract';out.mkdir(parents=True,exist_ok=True)
metadata=bind_position_cache(mesh,[0],np.array([[[0.,0,0]],[[.2,0,0]],[[0.,0,0]]]),out/'quarter.pc2',first=1,sample_step=.25)
error=0.
for frame,expected in [(1,0),(1.125,.1),(1.25,.2),(1.375,.1),(1.5,0)]:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();co=coords(mesh);error=max(error,abs(co[0,0]-expected));np.testing.assert_array_equal(co[1:],[[1,0,0],[0,1,0]])
assert error<1e-6,error
bpy.ops.wm.save_as_mainfile(filepath=str(out/'SubframeCache.blend'));bpy.ops.wm.open_mainfile(filepath=str(out/'SubframeCache.blend'),load_ui=False,use_scripts=False);mesh=bpy.data.objects['CacheFixture']
for frame,expected in [(1.125,.1),(1.25,.2),(1.375,.1)]:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();error=max(error,abs(coords(mesh)[0,0]-expected))
assert error<1e-6,error
result={'status':'QUARTER_FRAME_PC2_PLAYBACK_AND_UNSELECTED_VERTICES_PASS','error_m':float(error),'reload_pass':True,'metadata':metadata};(out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('SUBFRAME_CACHE',json.dumps(result),flush=True)
