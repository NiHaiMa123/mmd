"""Initial physical-guide geometry preflight, no solver or mesh changes.

All 27 guide centerlines are checked. Closed skin is used only for inside
classification; actual visible skin triangles are used for segment crossings.
The first point is declared a kinematic root, never silently discarded.
This zero-radius test cannot certify finite-width hair collision coverage.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np,bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--prototype',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.prototype)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'完整角色_27分束骨链_待接原生物理.blend'),load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
base=ROOT.parent/'work/headswap_xl_codex';meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
exp=base/'fullhair_repro_20261030/input_body_aware';body=np.load(exp/'body.npy',mmap_mode='r')[0]
bf=np.load(exp/'body_faces.npy');real=bf[np.load(exp/'real_body_faces.npy').astype(bool)]
bt=BVHTree.FromPolygons(body.tolist(),real.tolist(),all_triangles=True)
closed=BVHTree.FromPolygons(body.tolist(),bf.tolist(),all_triangles=True)
# Closed-field inside classification uses the same established surface module
# as the complete displayed-hair audit, with the real animated skin topology.
from animation_contact_tools.closed_collider_field import ClosedColliderField
field=ClosedColliderField(body,bf)
rows=[];witness=[]
for chain in meta['chains']:
    points=coords(bpy.data.objects['Guide_'+chain['name']]);distance,_=field(points)
    crossings=[]
    for i in range(len(points)-1):
        start=Vector(points[i]);delta=Vector(points[i+1]-points[i]);length=delta.length
        if length<1e-8:continue
        direction=delta.normalized();co,normal,fi,d=bt.ray_cast(start,direction,length)
        if co is not None and d is not None and d<=length:
            crossings.append(dict(segment=i,skin_triangle=int(fi),position=list(co),
                involves_declared_kinematic_root=i==0))
    unsigned=np.array([bt.find_nearest(Vector(v))[3] for v in points])
    inside=np.flatnonzero(distance<-.0001)
    row=dict(name=chain['name'],points=len(points),declared_kinematic_root_points=[0],
        inside_skin_points=inside.tolist(),free_points_inside_skin=[int(i) for i in inside if i>0],
        minimum_free_point_signed_skin_distance_m=float(distance[1:].min()),
        minimum_free_point_actual_skin_distance_m=float(unsigned[1:].min()),
        centerline_skin_crossing_segments=len(crossings),free_centerline_crossing_segments=sum(not r['involves_declared_kinematic_root'] for r in crossings))
    rows.append(row)
    for hit in crossings:witness.append(dict(chain=chain['name'],**hit))
report=dict(status='GUIDE_CENTERLINES_REQUIRE_INITIAL_REPAIR' if any(r['free_points_inside_skin'] or r['free_centerline_crossing_segments'] for r in rows) else 'GUIDE_CENTERLINE_CHECK_COMPLETE_NOT_FINITE_WIDTH_ACCEPTED',
    all_27_chains_checked=len(rows)==27,guide_points=sum(r['points'] for r in rows),
    free_points_inside_skin=sum(len(r['free_points_inside_skin']) for r in rows),
    declared_roots_inside_skin=sum(0 in r['inside_skin_points'] for r in rows),
    centerline_skin_crossing_segments=sum(r['centerline_skin_crossing_segments'] for r in rows),
    free_centerline_crossing_segments=sum(r['free_centerline_crossing_segments'] for r in rows),
    rows=rows,witnesses=witness,new_physics_frames=0,
    scope='All centerline points and first ray hit per segment versus actual skin; closed-skin point containment. No radius, full crossing-count, self-collision or continuous-time proof.',
    display_hair_collision_claim='Separate complete displayed-hair initial audit required; guide failure does not imply displayed hair is initially intersecting',
    shutdown_forbidden=True)
(out/'guide_initial_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in report.items() if k not in ['rows','witnesses']},ensure_ascii=False),flush=True)
