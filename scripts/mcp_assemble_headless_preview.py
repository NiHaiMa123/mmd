"""Assemble the normal whole-character scene using the live Blender MCP."""
import bpy,json,sys,traceback
from pathlib import Path
ROOT=Path(r'E:\project\mmd\mmd_repo');OUT=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/headless_bullet/REVIEW_RAW'
def assemble():
 try:
  pub=json.loads((OUT/'cache_publication.json').read_text('utf8'));manifest=json.loads((Path(pub['input'])/'export_complete.json').read_text('utf8'));source=manifest['source_blend']
  assert not any(s.get('HeadlessNormalReview',False) for s in bpy.data.scenes),'Review assembly already exists'
  with bpy.data.libraries.load(source,link=False) as (f,t):t.scenes=[f.scenes[0]]
  scene=t.scenes[0];scene['HeadlessNormalReview']=True;bpy.context.window.scene=scene
  script=(ROOT/'scripts/assemble_full_hair_showcase.py').read_text('utf8')
  script=script.replace("bpy.ops.wm.open_mainfile(filepath=manifest['source_blend'],load_ui=False,use_scripts=False)","None")
  oldargv=sys.argv;sys.argv=['blender','--','--out',str(OUT)]
  try:exec(compile(script,str(ROOT/'scripts/assemble_full_hair_showcase.py'),'exec'),{'__file__':str(ROOT/'scripts/assemble_full_hair_showcase.py'),'__name__':'__main__'})
  finally:sys.argv=oldargv
  report=dict(stage='NORMAL_CHARACTER_ASSEMBLED',scene=scene.name,blend=str(OUT/'完整角色_整头连续物理_15秒.blend'))
 except BaseException as exc:report=dict(stage='FAILED',error=repr(exc),traceback=traceback.format_exc())
 (OUT/'mcp_assembly_status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
 return None
bpy.app.timers.register(assemble,first_interval=.1);print('Normal complete character assembly queued through MCP')
