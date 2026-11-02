"""Render after real keyframe review; dense audit runs independently."""
import argparse,json,shutil,subprocess,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BLENDER=r'D:\software\blender\5.2.1\blender.exe';PY=ROOT/'tools/contact_stack/venv/Scripts/python.exe'
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--source');p.add_argument('--video-name',default='完整角色_JigglePhysics_1080p_15秒_Shikako.mp4');a=p.parse_args();out=Path(a.candidate)
source=Path(a.source) if a.source else out/'完整角色_JigglePhysics原版_15秒.blend';auditjob=None
def status(stage,**kw):
    data=dict(stage=stage,**kw);tmp=out/'delivery_status.tmp.json';tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'delivery_status.json');print(stage,kw,flush=True)
def command(script,*args):return [BLENDER,'-b','-t','6','--python',str(ROOT/'scripts'/script),'--',*map(str,args)]
def accept_audit(path):
    report=json.loads(path.read_text('utf8'));assert report['samples_with_crossings']==0,('Actual hair crossings',path,report['samples_with_crossings'])
    assert report['max_body_error_m']<2e-5
    assert all(r.get('inside_component_samples') in [None,0] for r in report['rows']),('Hair containment',path)
    return report
def check_audit():
    if (out/'audit_subframes/progress.json').exists():
        progress=json.loads((out/'audit_subframes/progress.json').read_text('utf8'))
        assert progress.get('crossing_samples_so_far',0)==0,progress
    if auditjob.poll() is not None:
        assert auditjob.returncode==0,'Dense native audit failed'
        accept_audit(out/'audit_subframes/surface_audit.json')
def render(frames):
    with (out/'full_render.log').open('a',encoding='utf8') as log:
        job=subprocess.Popen(command('render_full_hair_showcase.py','--source',source,'--out',out/'frames','--frames',','.join(map(str,frames)),'--samples','32','--percentage','100','--device','GPU'),stdout=log,stderr=subprocess.STDOUT)
        try:
            while job.poll() is None:check_audit();time.sleep(2)
            assert job.returncode==0,'Render failed'
        except BaseException:
            if job.poll() is None:job.terminate();job.wait(timeout=30)
            raise
try:
    assert json.loads((out/'agent_keyframe_review.json').read_text('utf8'))['decision']=='PASS'
    initial_audit=out/'audit450/surface_audit.json'
    if not initial_audit.exists():initial_audit=out/'audit/surface_audit.json'
    accept_audit(initial_audit)
    framesdir=out/'frames';framesdir.mkdir(exist_ok=True)
    for image in (out/'keyframes').glob('f*.png'):
        target=framesdir/image.name
        if not target.exists():shutil.copy2(image,target)
    status('DENSE_AUDIT_AND_11_SECOND_CONTINUOUS_RENDER')
    auditlog=(out/'dense_audit.log').open('w',encoding='utf8')
    auditjob=subprocess.Popen(command('audit_jiggle_hair_candidate.py','--source',source,'--out',out/'audit_subframes','--first','1','--last','450','--step','.125'),stdout=auditlog,stderr=subprocess.STDOUT)
    (out/'dense_audit_job.json').write_text(json.dumps(dict(pid=auditjob.pid)),'utf8')
    render(range(301,361))
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','30','-start_number','301','-i',str(framesdir/'f%04d.png'),'-frames:v','60','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(out/'11秒附近_原生物理连续展示.mp4')],check=True)
    status('CONTINUOUS_PREVIEW_READY_AWAITING_ACTUAL_AGENT_REVIEW')
    while not (out/'agent_continuous_review.json').exists():check_audit();time.sleep(2)
    assert json.loads((out/'agent_continuous_review.json').read_text('utf8'))['decision']=='PASS'
    status('RENDERING_ALL_450_NATIVE_1080P_FRAMES')
    render(list(range(1,301))+list(range(361,451)))
    status('WAITING_FOR_DENSE_AUDIT')
    assert auditjob.wait()==0;accept_audit(out/'audit_subframes/surface_audit.json');auditlog.close()
    status('ENCODING_AND_FULL_DECODING')
    subprocess.run([str(PY),str(ROOT/'scripts/encode_jiggle_showcase.py'),'--delivery',str(out),'--filename',a.video_name,'--music',r'E:\data\music\Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3'],check=True)
    status('COMPLETE_PLUGIN_VIDEO_AND_NATIVE_SAMPLED_CONTACT_VERIFIED')
except BaseException as exc:
    status('FAILED',error=repr(exc),traceback=traceback.format_exc());raise
