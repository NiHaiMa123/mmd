"""Read completed output frames without pausing or relabeling a running solve."""
import argparse,json,os,shutil,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];native=ROOT/'tools/ppf/native';sys.path.insert(0,str(native));handle=os.add_dll_directory(str(native/'bin'))
from frontend import _rust,_cbor_bridge_ as cbor
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--last-output-frame',type=int);p.add_argument('--first-output-frame',type=int,default=0);a=p.parse_args();src=Path(a.input);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists():raise ValueError('Use a new prefix capture directory')
manifest=json.loads((src/'manifest.json').read_text('utf8'));status=json.loads((src/'solve_status.json').read_text('utf8'));path=status['output'];latest=_rust.read_latest_vertex(path)
if latest is None:raise ValueError('No completed solver output')
last=int(latest[1]) if a.last_output_frame is None else min(int(latest[1]),a.last_output_frame)
if last<1:raise ValueError('At least one completed output interval required')
if not 0<=a.first_output_frame<last:raise ValueError('Requested completed interval is empty or invalid')
with np.load(src/'trajectories.npz') as z:initial=z['cloth'][0]
mapping=cbor.loads_vertex_map((Path(path).parent/'map.pickle').read_bytes());ids=np.asarray(mapping['cloth'],dtype=int)
if len(ids)!=len(initial):raise ValueError('Physical volume map changed')
first=_rust.read_vertex_bin(path,0);mapping_error=float(np.max(np.abs(first[ids]-initial)))
if mapping_error>1e-6:raise ValueError('Native output vertex order differs from the input; resolve its explicit map')
positions=[]
for f in range(a.first_output_frame,last+1):
 raw=_rust.read_vertex_bin(path,f)
 if raw is None:raise ValueError(f'Missing completed output {f}')
 positions.append(raw[ids])
np.save(out/'PPFVolume.npy',np.array(positions,dtype='<f4'));shutil.copyfile(src/'volume_binding.npz',out/'volume_binding.npz');start=manifest['source_frames'][0];manifest['source_frames']=[start+a.first_output_frame/status['output_fps']*manifest['fps'],start+last/status['output_fps']*manifest['fps']];manifest['prefix_capture']=dict(source_run=str(src),first_output_frame=a.first_output_frame,last_output_frame=last,source_mapping_error_m=mapping_error,full_run_finished=False);(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');status.update(status='COMPLETED_OUTPUT_PREFIX_ONLY',frames=last-a.first_output_frame,full_run_finished=False);(out/'solve_status.json').write_text(json.dumps(status,indent=2),encoding='utf8');print('PPF_PREFIX_CAPTURED',json.dumps(manifest['prefix_capture']),flush=True)
