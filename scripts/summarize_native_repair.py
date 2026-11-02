"""Summarize sampled checks without equating skin coverage to full physics."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fit', required=True)
    fit = Path(parser.parse_args().fit).resolve()

    def read(name):
        return json.loads((fit / name).read_text(encoding='utf-8'))

    coverage = {}
    for region, filename in [('hips', 'visible_hip_coverage.json'),
                             ('sleeve_lining', 'visible_sleeve_lining_coverage.json')]:
        rows = read('review/' + filename)
        assert set(rows) == {'neutral', '1', '121', '256', '3401'}
        coverage[region] = {}
        for frame, views in rows.items():
            assert {v['azimuth'] for v in views} == set(range(0, 360, 30))
            samples = sum(v['tested_skin_samples'] for v in views)
            assert samples > 0, 'Empty coverage check'
            coverage[region][frame] = {
                'tested_rays': samples,
                'visible_skin_leaks': sum(v['visible_skin_leaks'] for v in views),
            }

    shoe_report = read('shoe_preservation/report.json')
    assert Path(shoe_report['source']).resolve() == fit / 'work.blend'
    shoes = {k: v['crossing_pairs'] for k, v in shoe_report['sides'].items()}
    assert set(shoes) == {f'{f}_{s}' for f in (1, 121, 256, 3401) for s in ('L', 'R')}
    physics = read('physics_review/report.json')
    contacts = {k: v['sleeves_crossing_pairs'] for k, v in physics['frames'].items()}
    repair = read('repair_report.json')
    protected = repair['protected_body_head_shoes']
    delivery = read('delivery.json')
    report = {
        'artifact': str(fit / 'Keqing_Stockings_Sleeves.blend'),
        'status': 'sampled coverage and shoes checked; outer sleeve motion needs further work',
        'skin_coverage': coverage,
        'shoe_crossing_pairs': shoes,
        'sleeve_native_physics_crossing_pairs': contacts,
        'physics_scope': physics['scope'],
        'body_head_shoe_meshes_unchanged': all(protected.values()),
        'protected_mesh_count': len(protected),
        'preserved_foot_stocking_vertices': repair['stockings']['foot_overrides'],
        'missing_used_images': delivery['missing_images'],
        'visible_helpers': delivery['visible_helpers'],
        'limits': [
            'Sampled body regions and poses only; not all VMD frames.',
            'Outer decorative sleeve intersections remain in some bent-arm poses.',
            'Opaque stylized hosiery; not physically translucent fibers.',
            'Blender procedural repair; PMX export has not been validated.',
        ],
    }
    report['sampled_coverage_and_shoes_pass'] = (
        all(v['visible_skin_leaks'] == 0 for rows in coverage.values() for v in rows.values())
        and all(v == 0 for v in shoes.values())
        and all(protected.values())
        and not delivery['missing_images'] and not delivery['visible_helpers']
    )
    (fit / 'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'sampled_pass': report['sampled_coverage_and_shoes_pass'],
                      'outer_sleeve_contacts': contacts}))


if __name__ == '__main__':
    main()
