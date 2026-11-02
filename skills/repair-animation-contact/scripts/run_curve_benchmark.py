"""Run the bundled native hair benchmark without a model or repository."""
import argparse,json,subprocess,sys,zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--blender',required=True);p.add_argument('--out',required=True);p.add_argument('--control',action='store_true');a=p.parse_args();out=Path(a.out).resolve()
    if out.exists() and any(out.iterdir()):p.error('Choose a fresh output directory')
    out.mkdir(parents=True,exist_ok=True);runtime=out/'plugin_runtime';runtime.mkdir()
    archive=Path(__file__).resolve().parents[1]/'assets/animation_contact_tools.zip'
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not (runtime/item.filename).resolve().is_relative_to(runtime):raise ValueError('Unsafe archive entry')
        z.extractall(runtime)
    cmd=[a.blender,'-b','--factory-startup','-t','4','--python-exit-code','1','--python',str(runtime/'animation_contact_tools/curve_benchmark.py'),'--','--out',str(out),'--substeps','60','--iterations','200']
    if a.control:cmd.append('--no-collision')
    with (out/'worker.log').open('w',encoding='utf8') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:return result.returncode
    report=json.loads((out/'report.json').read_text('utf8'));passed=report['benchmark_pass'] if not a.control else report['min_segment_clearance_m']<-.02
    print(json.dumps({'benchmark_pass':passed,'control':a.control,'max_root_error_m':report['max_root_error_m'],'min_edge_ratio':report['min_edge_ratio'],'max_edge_ratio':report['max_edge_ratio'],'min_interpolated_clearance_m':report['min_interpolated_clearance_m'],'model_hair_accepted':False},ensure_ascii=False));return 0 if passed else 2

if __name__=='__main__':sys.exit(main())
