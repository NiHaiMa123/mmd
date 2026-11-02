"""Disjoint hair caches must compose, including after reload."""
import json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.hair_position_cache import bind_position_cache
from animation_contact_tools.surface import coords
bpy.ops.wm.read_factory_settings(use_empty=True);data=bpy.data.meshes.new('TwoBundles');data.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)]);mesh=bpy.data.objects.new('TwoBundles',data);bpy.context.scene.collection.objects.link(mesh);out=ROOT/'outputs/multiple_cache_contract';out.mkdir(parents=True,exist_ok=True)
one=bind_position_cache(mesh,[0],np.array([[[0.,0,0]],[[.2,0,0]],[[0.,0,0]]]),out/'one.pc2',first=1,sample_step=.25)
two=bind_position_cache(mesh,[1],np.array([[[1.,0,0]],[[1.,.3,0]],[[1.,0,0]]]),out/'two.pc2',first=1,sample_step=.25)
assert one['selection_attribute']!=two['selection_attribute']
try:bind_position_cache(mesh,[0],np.zeros((2,1,3)),out/'overlap.pc2')
except ValueError:pass
else:raise AssertionError('Overlapping binding overwrote an existing bundle')
assert not (out/'overlap.pc2').exists()
def check():
 for frame,x,y in [(1.125,.1,.15),(1.25,.2,.3),(1.375,.1,.15)]:
  bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();actual=coords(bpy.data.objects['TwoBundles']);np.testing.assert_allclose(actual,[[x,0,0],[1,y,0],[0,1,0]],atol=1e-6)
check();bpy.ops.wm.save_as_mainfile(filepath=str(out/'TwoBundles.blend'));bpy.ops.wm.open_mainfile(filepath=str(out/'TwoBundles.blend'),load_ui=False,use_scripts=False);check()
r={'status':'DISJOINT_CACHES_RELOAD_AND_OVERLAP_GUARD_PASS','selection_attributes':[one['selection_attribute'],two['selection_attribute']],'existing_bundle_preserved':True};(out/'report.json').write_text(json.dumps(r,indent=2),encoding='utf8');print('MULTI_CACHE_CONTRACT',json.dumps(r),flush=True)
