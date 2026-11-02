"""Group automatically detected root conflicts into bounded, protected windows."""
import argparse,json,math
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--scan',required=True);p.add_argument('--out',required=True);a=p.parse_args();src=Path(a.input);manifest=json.loads((src/'export_complete.json').read_text('utf8'));profile=json.loads(Path(manifest['rig_profile']).read_text('utf8'));scan=json.loads(Path(a.scan).read_text('utf8'));step=manifest['sample_step'];protected=profile.get('protected_windows',[]);groups=[];blocked=[]
for row in sorted(scan['failures'],key=lambda r:r['frame']):
 f=row['frame']
 if any(w['start']<=f<=w['end'] for w in protected):blocked.append(row);continue
 if groups and f-groups[-1][-1]<=12:groups[-1].append(f)
 else:groups.append([f])
jobs=[]
for i,group in enumerate(groups):
 first=max(manifest['frames'][0],math.floor(group[0]-6));last=min(manifest['frames'][1],group[-1]+6)
 for w in protected:
  if first<w['start']<=last:last=w['start']-step
  if first<=w['end']<last:first=w['end']+step
 if any(first<=w['end'] and last>=w['start'] for w in protected):raise RuntimeError('Split conflict groups around protected windows before solving')
 jobs.append(dict(index=i,first=first,last=last,contact_samples=len(group),arguments=['--input',str(src),'--scan',a.scan,'--window-start',str(first),'--window-end',str(last),'--step',str(step)],source_override_policy='Use the previous accepted window candidate; original Actions remain intact; re-export/re-scan after all routes and joint-cache rebuilds'))
r=dict(status='CONTACT_WINDOW_JOBS_READY' if not blocked else 'PROTECTED_ROOT_CONFLICT_REQUIRES_INITIAL_GEOMETRY_REPAIR',frames=manifest['frames'],jobs=jobs,blocked_protected_samples=blocked,protected_windows=protected,manually_keyed_frames=False);Path(a.out).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(r,ensure_ascii=False),flush=True)
