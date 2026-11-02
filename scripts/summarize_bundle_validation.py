"""Summarize collision/strain windows from measured bundle samples."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
run=Path(a.run).resolve();d=json.loads((run/'independent_validation.json').read_text('utf8'));rows=d['samples'];step=d['sample_step']
def intervals(selected):
    result=[]
    for row in selected:
        f=row['frame']
        if result and abs(f-result[-1]['last']-step)<1e-7:
            result[-1]['last']=f;result[-1]['samples']+=1
        else:result.append({'first':f,'last':f,'samples':1})
    return result
bad=[r for r in rows if r['crossings']>0];strain=[r for r in rows if r['min_mesh_edge_ratio']<.9 or r['max_mesh_edge_ratio']>1.1]
pairs={}
for r in bad:
    for item in r['pairs']:
        key='/'.join(item['pair']);entry=pairs.setdefault(key,{'failed_samples':0,'peak_crossings':0,'first':r['frame'],'last':r['frame']})
        entry['failed_samples']+=1;entry['peak_crossings']=max(entry['peak_crossings'],item['crossings']);entry['last']=r['frame']
old_window=[r for r in rows if 200<=r['frame']<=250]
result={'source':str(run),'frames':d['frames'],'sample_count':len(rows),'sample_step':step,
 'selected_bundle_samples_pass':d['selected_bundle_samples_pass'],'collision_failed_samples':len(bad),'collision_windows':intervals(bad),
 'strain_failed_samples':len(strain),'strain_windows':intervals(strain),'pairs':pairs,
 'worst_collision_samples':sorted(bad,key=lambda r:r['crossings'],reverse=True)[:12],
 'previous_window_200_250':{'samples':len(old_window),'collision_failed_samples':sum(r['crossings']>0 for r in old_window),'strain_failed_samples':sum(r['min_mesh_edge_ratio']<.9 or r['max_mesh_edge_ratio']>1.1 for r in old_window)},
 'edge_ratio':[d['min_mesh_edge_ratio'],d['max_mesh_edge_ratio']],'root_error_m':d['interpolated_root_error_peak_m'],
 'full_model_accepted':False,'ccd_proven':False}
(run/'window_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k!='worst_collision_samples'},ensure_ascii=False))
