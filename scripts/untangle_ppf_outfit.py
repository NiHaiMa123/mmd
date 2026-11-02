"""Use the official Apache-2.0 PPF add-on's pure NumPy untangler locally."""
import sys,json,argparse,importlib.util,time
from dataclasses import asdict
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--self-only',action='store_true');p.add_argument('--soft-attachments',action='store_true');p.add_argument('--static-collider-policy',action='store_true');a=p.parse_args();source=Path(a.input).resolve();suffix='_body_soft_untangled' if a.static_collider_policy and a.soft_attachments else '_body_untangled' if a.static_collider_policy else '_soft_untangled' if a.soft_attachments else '_untangled';out=source.parent/(source.name+suffix);out.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('official_ppf_shell_untangle',ROOT/'tools/ppf/addon/core/shell_untangle.py');mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
if a.static_collider_policy:
    sys.path.insert(0,str(ROOT/'addon'));from mmd_outfit.contact_broadphase import install_static_collider_policy
    install_static_collider_policy(mod)
data=dict(np.load(source/'trajectories.npz'));pins=data['pins'];surfaces=[mod.Surface('outfit',data['cloth'][0].astype(float),data['cloth_faces'],True if a.soft_attachments else pins<.99999,.001)]
if not a.self_only:surfaces.append(mod.Surface('skin_gloves',data['body'][0].astype(float),data['body_faces'],False,.001))
def progress(stage,iteration,pairs):
    if iteration%25==0:print('OFFICIAL_PPF_UNTANGLE',stage,iteration,pairs,flush=True)
settings=mod.Settings(clearance=.0003,max_iter=700,progress=progress)
positions,report=mod.untangle(surfaces,settings);summary=asdict(report);(out/'untangle_report.json').write_text(json.dumps(summary,indent=2,default=str),encoding='utf-8')
if not report.converged or report.remaining:raise RuntimeError(f'Untangle not resolved: {report.remaining}, {report.message}')
# Only the starting fabric shape changes; attachment trajectories stay driven
# by the corrected rig. Fixed vertices must match to floating-point tolerance.
if not a.soft_attachments:assert np.max(np.abs(positions[0][pins>=.99999]-data['cloth'][0][pins>=.99999]))<1e-7
data['cloth'][0]=positions[0];np.savez_compressed(out/'trajectories.npz',**data);(out/'manifest.json').write_text((source/'manifest.json').read_text(encoding='utf-8'),encoding='utf-8');print('PPF_UNTANGLE_READY',report.remaining,report.max_move,flush=True)
