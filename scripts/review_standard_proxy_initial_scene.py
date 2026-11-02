"""Independent initial full-display audit, then normal full-character render.

No simulation advance beyond frame 1. Keep the native audit and rendering tools
as separate processes so initial appearance does not depend on an edited GUI.
"""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);a=p.parse_args()
candidate=Path(a.candidate);root=Path(__file__).resolve().parents[1]
config=json.loads((candidate/'configuration.json').read_text('utf8'))
source=config['blend'];blender=r'D:\software\blender\5.2.1\blender.exe'
def run(script,*args):
    subprocess.run([blender,'--background','--factory-startup','--python',str(root/'scripts'/script),'--',*args],
        check=True,cwd=root,creationflags=subprocess.CREATE_NO_WINDOW)
if not (candidate/'rest_audit/initial_contact_analysis.json').exists():
    run('analyze_clump_initial_contacts.py','--candidate',str(candidate))
if not (candidate/'native_rest_padding_audit.json').exists():
    run('audit_native_cloth_rest_padding.py','--candidate',str(candidate))
if not (candidate/'proxy_skin_rest_padding_audit.json').exists():
    run('audit_proxy_skin_rest_padding.py','--candidate',str(candidate))
native_padding=json.loads((candidate/'native_rest_padding_audit.json').read_text('utf8'))
skin_padding=json.loads((candidate/'proxy_skin_rest_padding_audit.json').read_text('utf8'))
rest=json.loads((candidate/'rest_audit/initial_contact_analysis.json').read_text('utf8'))
rest_pass=(rest['self_audit_complete'] and not rest['counts_are_lower_bounds']
    and rest['proxy_body_crossing_pairs']==0 and rest['same_clump_crossing_pairs']==0
    and rest['between_clump_crossing_pairs']==0
    and rest['free_vertices_inside_configured_body_margin']==0
    and rest['moving_face_samples_inside_body_margin']==0
    and rest['nonlocal_self_vertex_face_pairs_inside_margin']==0
    and rest['boundary_edges']==0 and rest['nonmanifold_edges']==0)
run('audit_jiggle_hair_candidate.py','--source',source,'--out',str(candidate/'initial_display_audit'),'--frames','1','--containment')
r=json.loads((candidate/'initial_display_audit/surface_audit.json').read_text('utf8'));row=r['rows'][0]
display_pass=(row['crossings']==0 and row['inside_component_samples']==0 and row['root_error_m']<.0001
    and row['body_error_m']<5e-6 and row['edge_ratio_p01']>.85 and row['edge_ratio_p99']<1.15 and row['edge_ratio_max']<1.5
    )
padding_pass=native_padding['complete'] and native_padding['padding_overlap_pairs']==0
coverage_pass=(len(config['clumps'])==27 and not config['clumps_with_coverage_failure']
    and not config['root_attachment_review_failures'])
skin_padding_pass=skin_padding['complete'] and skin_padding['padding_overlap_pairs']==0
passed=display_pass and rest_pass and padding_pass and skin_padding_pass and coverage_pass
record=dict(status='INITIAL_CANDIDATE_PASS' if passed else 'STOPPED_ON_ACTUAL_INITIAL_CONTACT_FAILURE',
    actual_display_initial_pass=display_pass,initial_candidate_pass=passed,
    proxy_initial_contact_pass=rest_pass,all_27_coverage_and_roots_pass=coverage_pass,
    source=source,audit=row,physics_advanced=False,
    proxy_body_crossing_pairs=rest['proxy_body_crossing_pairs'],
    proxy_skin_padding_pairs=skin_padding['padding_overlap_pairs'],
    proxy_face_samples_inside_body_margin=rest['moving_face_samples_inside_body_margin'],
    native_initial_padding_pairs=native_padding['padding_overlap_pairs'])
(candidate/'initial_review.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
run('render_full_hair_showcase.py','--source',source,'--out',str(candidate/'initial_normal1080'),
    '--frames','1','--samples','32','--percentage','100','--device','GPU')
record['normal_image']=str(candidate/'initial_normal1080/f0001.png')
(candidate/'initial_review.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(record,ensure_ascii=False),flush=True)
sys.exit(0 if passed else 2)
