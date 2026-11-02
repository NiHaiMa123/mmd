"""Read-only actual render-surface checks for a plugin-baked scene."""
import argparse,json,sys,time,collections
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,crosses
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True)
p.add_argument('--frames',default='1,69,175,242,245,256,280,310,321,326,331,336,345,360,375,450')
p.add_argument('--first',type=float);p.add_argument('--last',type=float);p.add_argument('--step',type=float,default=1)
p.add_argument('--containment',action='store_true')
p.add_argument('--require-baked-proxy',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架'];s=bpy.context.scene
if a.require_baked_proxy:
    proxy=bpy.data.objects['HairProxy_全头共享几何体积']
    cloth=next(md for md in proxy.modifiers if md.type=='CLOTH')
    assert cloth.point_cache.is_baked,'Read-only audit requires a frozen native cache'
split_hair=bpy.data.objects.get(s.get('HairDisplayObject','完整头发_原生Cloth_实际发片'))
def evaluated_with_source_ids(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());data=ev.to_mesh()
    ar=np.empty(len(data.vertices)*3,np.float32);data.vertices.foreach_get('co',ar);ar=ar.reshape(-1,3)
    world=np.array(ev.matrix_world);ar=ar@world[:3,:3].T+world[:3,3]
    sourceids=np.empty(len(data.vertices),np.int32);data.attributes['SourceVertexID'].data.foreach_get('value',sourceids)
    data.calc_loop_triangles();triangles=np.array([sourceids[list(t.vertices)] for t in data.loop_triangles],np.int32)
    classes=np.array([data.attributes['SurfaceClass'].data[t.polygon_index].value for t in data.loop_triangles])
    ev.to_mesh_clear();return ar,sourceids,triangles,classes
def actual_coords():
    if split_hair is None:return coords(m)
    bodyco,bodyids,_,_=evaluated_with_source_ids(m);hc,hi,_,_=evaluated_with_source_ids(split_hair)
    result=np.full((len(m.data.vertices),3),np.nan,dtype=float);result[bodyids]=bodyco;result[hi]=hc
    return result
base=ROOT.parent/'work/headswap_xl_codex';export=base/'fullhair_repro_20261030/input_body_aware'
skin_ids=np.load(export/'skin_ids.npy');expected=np.load(export/'body.npy',mmap_mode='r')
ids=np.load(export/'hair_ids.npy');edges=np.load(export/'hair_edges.npy')
z=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');hard=z['same_true_hard_root_mask']
m.data.calc_loop_triangles();tri=np.array([t.vertices[:] for t in m.data.loop_triangles],np.int32)
attr=m.data.attributes['SurfaceClass'];classes=np.array([attr.data[t.polygon_index].value for t in m.data.loop_triangles])
hair=tri[classes==3];skin=tri[np.isin(classes,[1,2])]
if split_hair is not None:
    _,bodyids,bodytris,bodyclasses=evaluated_with_source_ids(m)
    _,hairids,hairtris,hairclasses=evaluated_with_source_ids(split_hair)
    assert set(skin_ids).issubset(set(bodyids)),'Mask removed visible skin vertices'
    assert len(hairtris[hairclasses==3])==len(hair),'Rendered hair triangles missing'
    assert len(bodytris[np.isin(bodyclasses,[1,2])])==len(skin),'Rendered skin triangles missing'
    hair=hairtris[hairclasses==3];skin=bodytris[np.isin(bodyclasses,[1,2])]
gn={g.index:g.name for g in m.vertex_groups}
dominant=[]
for vi in range(len(m.data.vertices)):
    weights=[g for g in m.data.vertices[vi].groups if gn[g.group] in arm.pose.bones]
    dominant.append(gn[max(weights,key=lambda g:g.weight).group] if weights else 'unweighted')
s.frame_set(1);bpy.context.view_layer.update();x0=actual_coords()[ids];head0=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);inv0=np.linalg.inv(head0)
localroot=x0[hard]@inv0[:3,:3].T+inv0[:3,3]
initial_local=x0@inv0[:3,:3].T+inv0[:3,3]
if a.containment:
    from animation_contact_tools.closed_collider_field import ClosedColliderField
    closed_faces=np.load(export/'body_faces.npy')
    parent=np.arange(len(ids))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=int(parent[i])
        return i
    for aa,bb in edges:parent[find(int(aa))]=find(int(bb))
    representatives=sorted({find(i) for i in range(len(ids))})
restlen=z['source_edge_lengths'];valid=restlen>.0005
frames=np.arange(a.first,a.last+a.step*.1,a.step).tolist() if a.first is not None else list(map(float,a.frames.split(',')))
rows=[];started=time.monotonic()
for f in frames:
    s.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();co=actual_coords();v=[Vector(x) for x in co]
    ht=BVHTree.FromPolygons(co.tolist(),hair.tolist(),all_triangles=True);bt=BVHTree.FromPolygons(co.tolist(),skin.tolist(),all_triangles=True)
    hits=[];bybone=collections.Counter();bybody=collections.Counter()
    for hi,bi in ht.overlap(bt):
        hf=hair[hi];bf=skin[bi]
        if set(hf).intersection(bf):continue
        if crosses([v[i] for i in hf],[v[i] for i in bf]):
            bybone.update([dominant[int(i)] for i in hf])
            bybody.update([dominant[int(i)] for i in bf])
            hits.append(dict(hair_triangle=int(hi),skin_triangle=int(bi),hair_vertices=hf.tolist(),skin_vertices=bf.tolist(),point=co[hf].mean(0).tolist()))
    x=co[ids];head=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix)
    rootexpected=localroot@head[:3,:3].T+head[:3,3]
    ratio=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1)[valid]/restlen[valid]
    k=int(round((f-1)*8));body_error=float(np.abs(co[skin_ids]-expected[k]).max())
    invhead=np.linalg.inv(head);headlocal=x@invhead[:3,:3].T+invhead[:3,3]
    movement=np.linalg.norm(headlocal-initial_local,axis=1)
    inside=minimum=None
    if a.containment:
        field=ClosedColliderField(co[skin_ids],closed_faces);dist,_=field(x[representatives]);inside=int((dist<-.0001).sum());minimum=float(dist.min())
    row=dict(frame=float(f),crossings=len(hits),witnesses=hits[:80],dominant_collision_bones=dict(bybone.most_common()),skin_collision_bones=dict(bybody.most_common()),body_error_m=body_error,
             root_error_m=float(np.linalg.norm(x[hard]-rootexpected,axis=1).max()),
             edge_ratio_min=float(ratio.min()),edge_ratio_max=float(ratio.max()),
             edge_ratio_p01=float(np.quantile(ratio,.01)),edge_ratio_p99=float(np.quantile(ratio,.99)),
             head_local_motion_p95_m=float(np.quantile(movement,.95)),head_local_motion_max_m=float(movement.max()),
             inside_component_samples=inside,minimum_component_distance_m=minimum)
    rows.append(row);print('JIGGLE_SURFACE_AUDIT',f,len(hits),body_error,row['edge_ratio_max'],flush=True)
    if len(frames)<30:np.save(out/f'hair_world_{f:g}.npy',x)
    progress=out/'progress.tmp.json';progress.write_text(json.dumps(dict(frame=f,samples=len(rows),total=len(frames),crossing_samples_so_far=sum(r['crossings']>0 for r in rows),last_crossings=len(hits),elapsed_s=time.monotonic()-started)),'utf8');progress.replace(out/'progress.json')
report=dict(source=a.source,rows=rows,samples=len(rows),hair_triangles=len(hair),skin_triangles=len(skin),
            separate_actual_hair_mesh=split_hair.name if split_hair else None,
            samples_with_crossings=sum(r['crossings']>0 for r in rows),max_crossings=max(r['crossings'] for r in rows),
            max_body_error_m=max(r['body_error_m'] for r in rows),
            containment_mode='one witness per connected hair component using closed skin proxy' if a.containment else 'not checked',
            scope='Actual final evaluated hair versus raw skin triangle intersections; optional component containment; no self-collision/CCD proof',
            elapsed_s=time.monotonic()-started)
(out/'surface_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print('JIGGLE_AUDIT_COMPLETE',json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)
