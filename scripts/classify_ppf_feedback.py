"""Distinguish contact-blocked attachment goals from ordinary following lag."""
import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import inside_votes
from mmd_outfit.contact_timeline import reference_times,reference_at_time
folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
with np.load(folder/'trajectories.npz') as archive:data={k:archive[k] for k in ('cloth','body','body_faces','pins','original_mapping')}
actual=np.load(folder/'PPFCloth.npy');mapping=data['original_mapping'];representatives=np.array([np.flatnonzero(mapping==i)[0] for i in range(len(data['pins']))]);actual=actual[:,representatives];pins=np.flatnonzero(data['pins']>.99999);rows=[];blocked=[]
manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));times=reference_times(manifest,len(data['body']));fps=float(manifest['fps'])
for frame in range(len(actual)):
    co=reference_at_time(data['body'],times,frame/fps);goals=reference_at_time(data['cloth'],times,frame/fps);tree=BVHTree.FromPolygons(co.tolist(),data['body_faces'].tolist(),all_triangles=True)
    for i in pins:
        goal=Vector(goals[i]);point=Vector(actual[frame,i]);error=(point-goal).length
        if error<.02:continue
        q,n,fi,d=tree.find_nearest(point);gq,gn,gfi,gd=tree.find_nearest(goal);inside=inside_votes(tree,goal);row=dict(frame=frame+1,vertex=int(i),error_m=error,actual_body_distance_m=d,goal_body_distance_m=gd,goal_inside_skin=inside,actual_position=list(point),goal_position=list(goal))
        rows.append(row)
        if inside and d<.004:blocked.append(row)
report=dict(threshold_m=.02,scope='contact-feasibility feedback for the simulated proxy; parity over an open skin proxy remains a heuristic',reference_timeline='interpolated at solver output times',large_attachment_errors=len(rows),contact_blocked_goals=len(blocked),blocked_frames=sorted({r['frame'] for r in blocked}),examples=sorted(rows,key=lambda r:-r['error_m'])[:20],blocked_examples=blocked[:20],motion_replan_recommended=bool(blocked))
(folder/'feedback_classification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('PPF_FEEDBACK_CLASSIFICATION',report['large_attachment_errors'],report['contact_blocked_goals'],report['blocked_frames'],flush=True)
