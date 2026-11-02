"""Run the bundled standalone Blender worker without repository imports."""
import argparse,json,subprocess,sys,zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('blender','source','profile','out'):p.add_argument('--'+name,required=True)
    p.add_argument('--mode',choices=['audit','solve','hair-experiment'],default='audit');p.add_argument('--first',type=int,default=1);p.add_argument('--last',type=int,default=450);p.add_argument('--step',type=int,default=5)
    a=p.parse_args();source=Path(a.source).resolve();profile=Path(a.profile).resolve();out=Path(a.out).resolve()
    if not source.is_file() or not profile.is_file():p.error('Source and profile must exist')
    if a.first>a.last or a.step<1:p.error('Invalid frame range or step')
    if (out/'job_status.json').exists() or (out/'worker.log').exists():p.error('Choose a fresh task output directory')
    out.mkdir(parents=True,exist_ok=True);runtime=out/'plugin_runtime';runtime.mkdir(exist_ok=False)
    archive=Path(__file__).resolve().parents[1]/'assets/animation_contact_tools.zip'
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not (runtime/item.filename).resolve().is_relative_to(runtime.resolve()):raise ValueError('Unsafe plugin archive entry')
        z.extractall(runtime)
    worker=runtime/'animation_contact_tools/worker.py'
    cmd=[a.blender,'-b','--factory-startup','--python-exit-code','1','--python',str(worker),'--','--source',str(source),'--profile',str(profile),'--out',str(out),'--mode',a.mode,'--first',str(a.first),'--last',str(a.last),'--step',str(a.step)]
    with (out/'worker.log').open('w',encoding='utf8') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    receipt=out/'job_status.json'
    if result.returncode or not receipt.exists():
        print('Worker failed; inspect',out/'worker.log');return result.returncode or 1
    status=json.loads(receipt.read_text('utf8'));print(json.dumps(status,ensure_ascii=False))
    return 2 if status.get('state')!='complete' or 'UNRESOLVED' in status.get('acceptance','') else 0

if __name__=='__main__':sys.exit(main())
