"""Rebind the existing normal showcase to a new, separately saved candidate."""
import bpy,json,shutil,traceback
from pathlib import Path
P=Path(r'E:\project\mmd\work\headswap_xl_codex\native_mmd_bridge_20261030\headless_bullet');OUT=Path(json.loads((P/'next_candidate.json').read_text('utf8'))['delivery'])
def update():
 try:
  scene=next(s for s in bpy.data.scenes if s.get('HeadlessNormalReview',False));bpy.context.window.scene=scene
  pub=json.loads((OUT/'cache_publication.json').read_text('utf8'))
  for obj in scene.objects:
   for mod in obj.modifiers:
    if mod.type!='MESH_CACHE':continue
    old=Path(bpy.path.abspath(mod.filepath));assert old.exists(),str(old)
    new=OUT/'cache'/old.name
    if old.name=='full_head.pc2':assert new.exists()
    elif not new.exists():shutil.copy2(old,new)
    mod.filepath=str(new)
  scene['FullHairCachePublication']=str(OUT/'cache_publication.json');scene['FullHairAlgorithmFingerprint']=pub['fingerprint'];scene.frame_set(1)
  for obj in scene.objects:
   for mod in obj.modifiers:
    if mod.type=='MESH_CACHE':mod.filepath='//cache/'+Path(mod.filepath).name
  scene['FullHairCachePublication']='//cache_publication.json'
  bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'完整角色_整头连续物理_15秒.blend'),compress=True,relative_remap=False)
  report=dict(stage='NORMAL_CHARACTER_ASSEMBLED',scene=scene.name,blend=str(OUT/'完整角色_整头连续物理_15秒.blend'))
 except BaseException as exc:report=dict(stage='FAILED',error=repr(exc),traceback=traceback.format_exc())
 (OUT/'mcp_assembly_status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
 return None
bpy.app.timers.register(update,first_interval=.1);print('Normal candidate cache update queued via MCP')
