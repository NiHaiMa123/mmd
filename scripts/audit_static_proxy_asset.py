"""Independent geometry-only native audit before binding a static asset."""
import argparse,json,sys,runpy
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--asset',required=True);p.add_argument('--reference',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.asset);reference=Path(a.reference)
c=json.loads((reference/'configuration.json').read_text('utf8'))
fields=['clumps','cloth_collision_distance_m','body_collision_outer_m','self_collision_distance_m','simulation_scale','manifold_clean_asset']
config={k:c[k] for k in fields};config.update(static_asset_only=True,reference_configuration=str(reference/'configuration.json'))
(out/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf8')
scripts=Path(__file__).resolve().parent
def run(name):
    sys.argv=['blender','--','--candidate',str(out)]
    runpy.run_path(str(scripts/name),run_name='__main__')
run('analyze_clump_initial_contacts.py')
rest=json.loads((out/'rest_audit/initial_contact_analysis.json').read_text('utf8'))
record=dict(physics_started=False,render_hair_bound=False,
    proxy_body_crossing_pairs=rest['proxy_body_crossing_pairs'],
    proxy_self_crossing_pairs=rest['same_clump_crossing_pairs']+rest['between_clump_crossing_pairs'])
if record['proxy_body_crossing_pairs'] or record['proxy_self_crossing_pairs']:
    record['status']='STOPPED_ACTUAL_INITIAL_PROXY_INTERSECTION'
else:
    run('audit_native_cloth_rest_padding.py')
    padding=json.loads((out/'native_rest_padding_audit.json').read_text('utf8'))
    record['native_initial_padding_pairs']=padding['padding_overlap_pairs']
    if padding['complete'] and padding['padding_overlap_pairs']==0:
        run('audit_proxy_skin_rest_padding.py')
        skin=json.loads((out/'proxy_skin_rest_padding_audit.json').read_text('utf8'))
        record['proxy_skin_padding_pairs']=skin['padding_overlap_pairs']
        passed=(skin['complete'] and skin['padding_overlap_pairs']==0 and rest['self_audit_complete']
            and not rest['counts_are_lower_bounds'] and rest['boundary_edges']==0 and rest['nonmanifold_edges']==0
            and rest['moving_face_samples_inside_body_margin']==0
            and rest['nonlocal_self_vertex_face_pairs_inside_margin']==0
            and rest['free_vertices_inside_configured_body_margin']==0)
        record['status']='STATIC_PROXY_CONTACT_PASS' if passed else 'STATIC_PROXY_PADDING_REQUIRES_MODELING'
    else:record['status']='STATIC_SELF_PADDING_REQUIRES_MODELING'
(out/'static_review.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(record,ensure_ascii=False),flush=True)
