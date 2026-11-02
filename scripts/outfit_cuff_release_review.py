"""Run packaged cuff generation and two comparable continuous-physics reviews.

Can run as a detached local process; progress and errors remain on disk.
No private asset paths are embedded in this script.
"""
import argparse
import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous-release', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--blender', required=True)
    parser.add_argument('--reuse-baseline-report')
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    def status(stage, **extra):
        (out / 'review_status.json').write_text(
            json.dumps({'stage': stage, **extra}, indent=2), encoding='utf-8')

    def run(stage, argv):
        status(stage)
        with (out / (stage + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)

    try:
        previous = read(args.previous_release)
        profile = read(previous['inspect']['profile'])
        request = read(Path(previous['fit']['job_dir']) / 'request.json')
        if not args.resume:
            run('packaged_e2e', [sys.executable, str(ROOT / 'tests/outfit_release_e2e.py'),
                '--blender', args.blender, '--source', profile['source']['path'],
                '--target', profile['target']['path'], '--motion', request['motion'],
                '--output', str(out), '--ground-motion', '--cuff-physics'])
        current = read(out / 'release_e2e.json')['fit']
        assert current['ok'] and current['version']=='0.9.0' and not current['accepted']
        blender = [args.blender, '-b', '--factory-startup', '--python-exit-code', '1', '--python']
        if not args.resume or not read(out/'arm_shape_review.json')['passed']:
            run('arm_shape', [*blender, str(ROOT / 'scripts/outfit_arm_shape_review.py'), '--',
                '--job', current['job_dir'], '--out', str(out / 'arm_shape_review.json')])
        if not args.resume or not read(out/'mesh_review.json')['passed']:
            run('mesh_review',[*blender,str(ROOT/'scripts/outfit_cuff_mesh_review.py'),'--',
                '--job',current['job_dir'],'--previous-job',previous['fit']['job_dir'],
                '--out',str(out/'mesh_review.json'),'--allow-hand-domain-fix'])
        for stage, job, render in [('cuff_full_physics', current['job_dir'], True),
                                    ('baseline_full_physics', previous['fit']['job_dir'], False)]:
            if stage=='baseline_full_physics' and args.reuse_baseline_report:
                source=Path(args.reuse_baseline_report).resolve()
                baseline=read(source)
                assert baseline['physics'] and baseline['physics_subset'] is None
                assert [r['frame'] for r in baseline['motion']]==[61,121,226,256]
                (out/stage).mkdir(exist_ok=True)
                shutil.copyfile(source,out/stage/'report.json')
                status(stage,reused_report=str(source))
                continue
            run(stage, [*blender, str(ROOT / 'scripts/outfit_sleeve_contact_review.py'), '--',
                '--job', job, '--out', str(out / stage), '--frames', '61', '121', '226', '256',
                '--physics', *([] if render else ['--no-render'])])
        status('complete', job_dir=current['job_dir'], accepted=False)
    except Exception:
        status('failed', error=traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
