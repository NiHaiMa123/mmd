"""Read-only static initial proxy mesh contact audit; no physics evaluation."""
import sys,json,time,argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.surface import crosses
parser=argparse.ArgumentParser();parser.add_argument('--candidate');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
base=ROOT.parent/'work/headswap_xl_codex';p=Path(args.candidate) if args.candidate else base/'standard_proxy_20261031/clumps07';out=p/('rest_audit' if args.candidate else 'bottleneck_analysis');out.mkdir(exist_ok=True)
z=np.load(p/'clump_proxy_rest.npz');source=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');head=source['head_matrix'];x=z['vertices']@head[:3,:3].T+head[:3,3];tri=z['triangles'];pins=z['pins'].astype(bool);clumps=z['clump_ids'];config=json.loads((p/'configuration.json').read_text('utf8'))
exp=base/'fullhair_repro_20261030/input_body_aware';body=np.load(exp/'body.npy',mmap_mode='r')[0];bf=np.load(exp/'body_faces.npy')[np.load(exp/'real_body_faces.npy').astype(bool)]
pv=[Vector(v) for v in x];bv=[Vector(v) for v in body];pt=BVHTree.FromPolygons(x.tolist(),tri.tolist(),all_triangles=True);bt=BVHTree.FromPolygons(body.tolist(),bf.tolist(),all_triangles=True)
start=time.monotonic();b_candidates=pt.overlap(bt);bodyhits=[];byclump={}
distances=np.array([bt.find_nearest(v)[3] for v in pv]);print('INITIAL_PROXY_BODY_GAP',float(distances.min()),flush=True)
margin=config.get('cloth_collision_distance_m',.003)+config.get('body_collision_outer_m',.003)
for i,j in b_candidates:
    if crosses([pv[k] for k in tri[i]],[bv[k] for k in bf[j]]):
        ci=int(clumps[tri[i,0]]);key=config['clumps'][ci]['name'];byclump[key]=byclump.get(key,0)+1;bodyhits.append((i,j))
report=dict(analysis='Static geometry only; cached initial proxy transformed to the prepared source head pose',proxy_body_candidate_pairs=len(b_candidates),proxy_body_crossing_pairs=len(bodyhits),proxy_body_crossings_with_all_pinned_triangle=sum(bool(np.all(pins[tri[i]])) for i,j in bodyhits),proxy_body_crossings_with_no_pinned_triangle=sum(bool(not np.any(pins[tri[i]])) for i,j in bodyhits),body_crossings_by_clump=byclump,proxy_bbox_world=[x.min(0).tolist(),x.max(0).tolist()],body_bbox_world=[body.min(0).tolist(),body.max(0).tolist()],proxy_vertex_unsigned_skin_distance_min_m=float(distances.min()),proxy_free_vertices_within_6mm_body_collision_envelope=int(((distances<.006)&~pins).sum()),proxy_pinned_vertices_within_6mm_body_collision_envelope=int(((distances<.006)&pins).sum()),elapsed_s=time.monotonic()-start)
report.update(configured_combined_body_margin_m=margin,free_vertices_inside_configured_body_margin=int(((distances<margin)&~pins).sum()),pinned_vertices_inside_configured_body_margin=int(((distances<margin)&pins).sum()))
movable_faces=tri[~np.all(pins[tri],axis=1)]
face_samples=np.concatenate([x[movable_faces].mean(1),
    (x[movable_faces[:,0]]+x[movable_faces[:,1]])*.5,
    (x[movable_faces[:,1]]+x[movable_faces[:,2]])*.5,
    (x[movable_faces[:,2]]+x[movable_faces[:,0]])*.5])
sample_distances=np.array([bt.find_nearest(Vector(v))[3] for v in face_samples])
report.update(moving_face_skin_distance_samples=len(face_samples),
    moving_face_sample_skin_distance_min_m=float(sample_distances.min()),
    moving_face_samples_inside_body_margin=int((sample_distances<margin).sum()))
(out/'initial_contact_progress.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('INITIAL_PROXY_BODY',json.dumps(report,ensure_ascii=False),flush=True)
self_candidates=pt.overlap(pt);same=between=pinned=processed=0;counts={};witness=[];complete=True
for i,j in self_candidates:
    if i>=j:continue
    ta,tb=tri[i],tri[j]
    if set(ta)&set(tb):continue
    processed+=1
    if crosses([pv[k] for k in ta],[pv[k] for k in tb]):
        ca,cb=int(clumps[ta[0]]),int(clumps[tb[0]])
        if ca==cb:same+=1
        else:between+=1
        if np.all(pins[ta]) or np.all(pins[tb]):pinned+=1
        key=' / '.join(sorted([config['clumps'][ca]['name'],config['clumps'][cb]['name']]));counts[key]=counts.get(key,0)+1
        if len(witness)<20:witness.append(dict(proxy_triangles=[int(i),int(j)],clumps=[ca,cb]))
    if same+between>=10000 or time.monotonic()-start>90:complete=False;break
report.update(proxy_self_candidate_pairs_including_symmetric=len(self_candidates),self_pairs_tested=processed,same_clump_crossing_pairs=same,between_clump_crossing_pairs=between,contacts_with_fully_pinned_triangle=pinned,self_audit_complete=complete,counts_are_lower_bounds=not complete,worst_self_pairs=sorted(counts.items(),key=lambda pair:pair[1],reverse=True)[:20],witnesses=witness,elapsed_s=time.monotonic()-start)
# Separate diagnostic for nonlocal vertex/face proximity within the stock
# solver's configured self margin; immediate one-ring neighborhoods excluded.
if config.get('manifold_clean_asset'):
    rings=[{i} for i in range(len(x))]
    for face in tri:
        for i in face:rings[i].update(map(int,face))
    radius=config['self_collision_distance_m'];near=[]
    for i,v in enumerate(pv):
        for co,normal,fi,distance in pt.find_nearest_range(v,radius):
            if not rings[i].intersection(map(int,tri[fi])):
                near.append((i,int(fi),float(distance)))
    report.update(nonlocal_self_vertex_face_search_radius_m=radius,
        nonlocal_self_vertex_face_pairs_inside_margin=len(near),
        nonlocal_self_vertex_face_witnesses=near[:20],
        self_proximity_exclusion='Faces incident on the vertex or its immediate edge neighbors')
    edge_array=np.sort(np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]),axis=1)
    _,counts=np.unique(edge_array,axis=0,return_counts=True)
    report.update(boundary_edges=int((counts==1).sum()),nonmanifold_edges=int((counts>2).sum()))
report['elapsed_s']=time.monotonic()-start
(out/'initial_contact_analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('INITIAL_PROXY_CONTACTS',json.dumps(report,ensure_ascii=False),flush=True)
