"""Run isolated coupling comparisons and fail closed on crashes/timeouts."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'outputs/contact_stack/hinge_cloth'));p.add_argument('--steps',type=int,default=90);p.add_argument('--layers',type=int,default=1);p.add_argument('--pin-top',action='store_true');p.add_argument('--axis-fix',action='store_true');p.add_argument('--sync-reference',action='store_true');p.add_argument('--native-feedback',action='store_true');p.add_argument('--coupling',choices=('two_way_soft_constraint','external_articulation'),default='two_way_soft_constraint');p.add_argument('--margin',type=float,default=.001);p.add_argument('--timeout',type=int,default=900);p.add_argument('--modes',nargs='+',choices=('free','one_way','two_way'),default=['free','one_way','two_way']);a=p.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
report={'status':'RUNNING','scope':'Controlled backend experiment, not full MMD acceptance','cases':[]};path=out/'matrix_run.json'
path.write_text(json.dumps(report,indent=2),encoding='utf-8')
for mode in a.modes:
    log=out/(mode+'.log');command=[sys.executable,'-u',str(ROOT/'scripts/probe_genesis_ipc.py'),'--mode',mode,'--steps',str(a.steps),'--layers',str(a.layers),'--coupling',a.coupling,'--margin',str(a.margin),'--output',str(out)]
    if a.pin_top:command.append('--pin-top')
    if a.axis_fix:command.append('--axis-fix')
    if a.sync_reference:command.append('--sync-reference')
    if a.native_feedback:command.append('--native-feedback')
    begin=time.perf_counter();row={'mode':mode,'log':str(log),'command':command};report['cases'].append(row)
    try:
        with log.open('w',encoding='utf-8') as handle:
            proc=subprocess.run(command,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT,timeout=a.timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        row['returncode']=proc.returncode
        case_report=out/mode/'report.json'
        row['case_status']=json.loads(case_report.read_text(encoding='utf-8'))['status'] if case_report.is_file() else 'MISSING_REPORT'
        row['ok']=proc.returncode==0 and row['case_status']=='NUMERICAL_RUN_COMPLETE_REQUIRES_CONTACT_AUDIT'
    except subprocess.TimeoutExpired:row.update(ok=False,case_status='TIMED_OUT')
    finally:
        row['seconds']=time.perf_counter()-begin
        path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('CONTACT_MATRIX_CASE',mode,row['case_status'],row['ok'],flush=True)
    if not row['ok']:
        report['status']='FAILED';path.write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(1)
report['status']='NUMERICAL_CASES_COMPLETE_REQUIRES_AUDIT';path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(report['status'],flush=True)
