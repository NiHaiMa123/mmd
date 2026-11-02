"""Portable official PPF runtime check: interacting cloth layers + collider."""
import os,sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];native=ROOT/'tools/ppf/native'
sys.path.insert(0,str(native));dll=os.add_dll_directory(str(native/'bin'))
from frontend import App
out=ROOT/'outputs/cynical_cloth15/contact_motion/ppf_runtime';out.mkdir(parents=True,exist_ok=True)
App.get_data_dirpath=staticmethod(lambda:str(out))
app=App.create('two_layers',cache_dir=str(out/'cache'))
V,F=app.mesh.square(res=12,ex=[1,0,0],ey=[0,1,0]);app.asset.add.tri('sheet',V*.4,F)
V,F=app.mesh.icosphere(r=.13,subdiv_count=2);app.asset.add.tri('sphere',V,F)
scene=app.scene.create()
for z in (.12,.135):
    sheet=scene.add('sheet').at(0,0,z);sheet.pin(sheet.grab([0,1,0]));sheet.param.set('strain-limit',.08)
scene.add('sphere').at(0,0,-.1).pin().move_by([0,0,.12],0,1)
fixed=scene.build();session=app.session.create(fixed);session.param.set('dt',.005).set('frames',30).set('fps',30).set('gravity',[0,0,-9.8]);session=session.build();start=time.time();session.start(blocking=True)
report=dict(finished=session.finished(),seconds=time.time()-start,output=session.output.path,scene='two interacting cloth layers with a prescribed moving sphere; runtime test only, not the outfit')
(out/'runtime.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('PPF_RUNTIME',report,flush=True)
