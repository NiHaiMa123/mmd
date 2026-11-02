"""Import and simplify a static shared geometric cage; native binding only."""
import json
from pathlib import Path
import bpy, bmesh, numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree

def construct(base, scene, anchor, points, ids, hard, asset, checkpoint):
    z = np.load(asset/'geometric_volume.npz')
    asset_report=json.loads((asset/'volume_asset.json').read_text('utf8'))
    if 'mesh_quality_regularization' in asset_report:
        assert asset_report['mesh_quality_regularization']['quality_gate_pass'],'Rejected static mesh-quality candidate must not enter dynamics'
    clean=bool(asset_report.get('manifold_cleanup'))
    inp = np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
    meta = json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
    assert np.array_equal(ids,z['source_vertex_ids'])
    data = bpy.data.meshes.new('SharedGeometricHairVolume')
    data.from_pydata(z['vertices'].tolist(),[],z['triangles'].tolist()); data.update()
    proxy = bpy.data.objects.new('HairProxy_全头共享几何体积',data)
    scene.collection.objects.link(proxy);proxy.parent=anchor
    proxy.matrix_parent_inverse=Matrix.Identity(4);proxy.matrix_basis=Matrix.Identity(4)
    bpy.ops.object.select_all(action='DESELECT');proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
    before=len(data.vertices)
    # Native planar dissolve first retains the volume boundary; conservative
    # collapse then limits solver size. The resulting surface is audited anew.
    if not clean:
        dissolve=proxy.modifiers.new('Native_PlanarDissolve','DECIMATE');dissolve.decimate_type='DISSOLVE';dissolve.angle_limit=.015
        bpy.ops.object.modifier_apply(modifier=dissolve.name)
    if not clean and len(proxy.data.vertices)>12000:
        dec=proxy.modifiers.new('Native_QuadricSimplification','DECIMATE');dec.ratio=12000/len(proxy.data.vertices);dec.use_collapse_triangulate=True
        bpy.ops.object.modifier_apply(modifier=dec.name)
    if not clean:
        bm=bmesh.new();bm.from_mesh(proxy.data);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(proxy.data);bm.free()
    vertices=np.array([v.co[:] for v in proxy.data.vertices]);triangles=np.array([f.vertices[:] for f in proxy.data.polygons],np.int32)
    roots=KDTree(int(hard.sum()))
    for j,v in enumerate(points[hard]):roots.insert(v,j)
    roots.balance()
    root_distance=np.array([roots.find(v)[2] for v in vertices])
    pins=root_distance<.008
    assert pins.sum()>=3, 'No original head attachment represented'
    parent=np.arange(len(vertices))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for e in proxy.data.edges:parent[find(e.vertices[0])]=find(e.vertices[1])
    component_ids=np.array([find(i) for i in range(len(vertices))])
    components=[dict(vertices=int((component_ids==c).sum()),rooted=bool(np.any(pins[component_ids==c]))) for c in np.unique(component_ids)]
    tree=BVHTree.FromPolygons(vertices.tolist(),triangles.tolist(),all_triangles=True)
    labels=inp['chain_labels'];reports=[]
    coverage=np.load(asset/'source_cage_coverage.npz') if clean else None
    if clean:assert np.array_equal(ids,coverage['source_vertex_ids'])
    distances=np.array([tree.find_nearest(Vector(v))[3] for v in points])
    for ci,record in enumerate(meta['chains']):
        d=distances[labels==ci]
        reports.append(dict(name=record['name'],render_vertices=len(d),shared_geometric_target=True,
            nearest_surface_p95_m=float(np.quantile(d,.95)),nearest_surface_max_m=float(d.max()),
            root_pin_max_distance_to_authored_root_set_m=float(root_distance[pins].max())))
        if clean:
            sel=labels==ci;outside=~coverage['inside'][sel];outside_d=coverage['distances'][sel][outside]
            reports[-1].update(coverage_metric='Enclosed volume points plus bounded outside surface offset',
                inside_cage_vertices=int((~outside).sum()),outside_cage_vertices=int(outside.sum()),
                outside_surface_distance_max_m=float(outside_d.max()) if len(outside_d) else 0.,
                coverage_pass=bool(not len(outside_d) or outside_d.max()<=.008))
    pointlabels=KDTree(len(points))
    for i,v in enumerate(points):pointlabels.insert(v,i)
    pointlabels.balance()
    # IDs below are provenance only, never physical splits or collision masks.
    clumps=np.array([max(0,int(labels[pointlabels.find(v)[1]])) for v in vertices])
    np.savez_compressed(checkpoint/'clump_proxy_rest.npz',vertices=vertices,triangles=triangles,pins=pins,
        clump_ids=clumps,source_vertex_ids=ids,source_clump_labels=labels,component_ids=component_ids)
    (checkpoint/'geometric_topology.json').write_text(json.dumps(dict(raw_vertices=before,
        vertices=len(vertices),triangles=len(triangles),components=components,pins=int(pins.sum()),
        deleted_components=0,all_27_groups_tracked=True,physical_clump_splits=False,
        manifold_clean_asset=clean,post_import_simplification=not clean),indent=2),'utf8')
    return proxy,pins,reports,[proxy]*27,labels,components
