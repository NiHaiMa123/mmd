"""Asset preparation only: structured ribbon cages and native per-clump targets.

No motion solver, collision correction or animation filtering is implemented.
The fitted grid is a one-time retopology of each authored bone-weight clump.
"""
import json
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

def construct(base,scene,anchor,points,ids,hard,checkpoint=None,regular_open=False):
    inp=base/'standard_proxy_20261031/inspection';z=np.load(inp/'inputs.npz');meta=json.loads((inp/'inputs.json').read_text('utf8'))
    assert np.array_equal(ids,z['ids']);labels=z['chain_labels'];weight=z['chain_weights'].sum(axis=1)
    verts=[];faces=[];pins=[];clump_ids=[];reports=[]
    for ci,record in enumerate(meta['chains']):
        selected=np.flatnonzero(labels==ci);cloud=np.asarray(points[selected],float);center=cloud.mean(0)
        _,_,axes=np.linalg.svd(cloud-center,full_matrices=False)
        root_ids=selected[weight[selected]<=np.quantile(weight[selected],.12)]
        root=points[root_ids].mean(0)
        if np.dot(axes[0],center-root)<0:axes[0]*=-1
        # Right-handed local coordinates make every ribbon consistently oriented.
        axes[2]=np.cross(axes[0],axes[1]);pc=(cloud-center)@axes.T
        lo,hi=pc[:,0].min(),pc[:,0].max();length=hi-lo
        spacing=.012 if regular_open else (.004 if record['name'].startswith('Sidetail') else .005)
        rows=max(8 if regular_open else 12,int(np.ceil(length/spacing))+1);columns=5 if regular_open else (17 if record['name'].startswith('Sidetail') else 9);grid=[]
        axial_samples=np.linspace(lo,hi,rows)
        if regular_open:
            root_axis=((cloud[weight[selected]<.2]-center)@axes.T)[:,0]
            extra=np.clip(np.array([root_axis.min(),root_axis.mean(),root_axis.max()])[:,None]+np.array([-.003,0,.003])[None,:],lo,hi).ravel()
            ordered=np.sort(np.r_[axial_samples,extra]);axial_samples=[float(ordered[0])]
            for v in ordered[1:]:
                if v-axial_samples[-1]>=.0008:axial_samples.append(float(v))
            axial_samples=np.array(axial_samples);rows=len(axial_samples)
        for t in axial_samples:
            nearby=np.argsort(np.abs(pc[:,0]-t))[:max(4,int(len(cloud)/rows*2))]
            slab=pc[nearby];left,right=slab[:,1].min()-.0015,slab[:,1].max()+.0015
            for u in np.linspace(left,right,columns):
                distance=(pc[:,0]-t)**2+(pc[:,1]-u)**2
                nearest=np.argsort(distance)[:4];weights=1/np.maximum(distance[nearest],1e-7)
                v=np.average(pc[nearest,2],weights=weights)
                grid.append(center+np.array([t,u,v])@axes)
        n=len(grid);localfaces=[]
        for r in range(rows-1):
            for c in range(columns-1):
                j=r*columns+c;localfaces.extend([(j,j+1,j+columns+1),(j,j+columns+1,j+columns)])
        # Stock Solidify closes the cage. Its original grid remains continuous;
        # there is no voxel conversion, disconnected-piece deletion or reweld.
        data=bpy.data.meshes.new('ClumpGrid_'+record['name']);data.from_pydata(grid,[],localfaces);data.update()
        obj=bpy.data.objects.new('ClumpGrid_'+record['name'],data);scene.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        # Native nearest-surface projection is used only to fit the static
        # simulation asset to this clump's original render triangles. It is
        # not an animation collision-correction layer.
        if not regular_open:
            triangles=z['faces'];clump_faces=triangles[np.any(labels[triangles]==ci,axis=1)]
            fitdata=bpy.data.meshes.new('ClumpFitSource_'+str(ci));fitdata.from_pydata(points.tolist(),[],clump_faces.tolist());fitdata.update()
            fitobj=bpy.data.objects.new('ClumpFitSource_'+str(ci),fitdata);scene.collection.objects.link(fitobj)
            fitgroup=obj.vertex_groups.new(name='StaticRetopologyFit');fitgroup.add(list(range(len(data.vertices))),.9,'REPLACE')
            fit=obj.modifiers.new('Native_InitialRetopologyFit','SHRINKWRAP');fit.target=fitobj;fit.wrap_method='NEAREST_SURFACEPOINT';fit.wrap_mode='ON_SURFACE';fit.offset=0.;fit.vertex_group=fitgroup.name
            bpy.ops.object.modifier_apply(modifier=fit.name);bpy.data.objects.remove(fitobj,do_unlink=True);data=obj.data
        # Pin from the authored mixed head weights, rather than guessing that
        # the first PCA row coincides with the actual root patch.
        tree_source=KDTree(len(selected))
        for j,v in enumerate(cloud):tree_source.insert(v,j)
        tree_source.balance()
        rootgroup=obj.vertex_groups.new(name='ProxyRoot');root_indices=[]
        authored_roots=cloud[weight[selected]<.2];root_selection_tree=KDTree(len(authored_roots))
        for j,v in enumerate(authored_roots):root_selection_tree.insert(v,j)
        root_selection_tree.balance()
        for vertex in data.vertices:
            _,source_local,distance=tree_source.find(vertex.co);sourcej=selected[source_local]
            if regular_open:
                if root_selection_tree.find(vertex.co)[2]<.014:root_indices.append(vertex.index)
            elif weight[sourcej]<.2 and distance<.008:root_indices.append(vertex.index)
        assert len(root_indices)>=3,('Root patch not represented',record['name'],len(root_indices))
        rootgroup.add(root_indices,1.,'REPLACE')
        if not regular_open:
            solid=obj.modifiers.new('Native_Solidify_RibbonCage','SOLIDIFY');solid.thickness=.002;solid.offset=0.;solid.use_even_offset=False
            bpy.ops.object.modifier_apply(modifier=solid.name)
        bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
        offset=len(verts);p=[v.co[:] for v in obj.data.vertices];fs=[tuple(poly.vertices) for poly in obj.data.polygons]
        root_index=obj.vertex_groups['ProxyRoot'].index;pinlocal=[any(g.group==root_index and g.weight>.99 for g in v.groups) for v in obj.data.vertices]
        assert len(p)==(n if regular_open else 2*n),('Unexpected proxy grid size',record['name'],len(p),n)
        # Verify connectivity with vertex indices from actual mesh edges.
        parent=list(range(len(p)))
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for e in obj.data.edges:parent[find(e.vertices[0])]=find(e.vertices[1])
        components=len({find(i) for i in range(len(p))});assert components==1,('Disconnected cage',record['name'],components)
        tree=BVHTree.FromPolygons(p,fs,all_triangles=True)
        distances=np.array([tree.find_nearest(Vector(v))[3] for v in cloud])
        root_distance=float(np.linalg.norm(np.asarray(p)[np.array(pinlocal)]-root,axis=1).min())
        root_tree=KDTree(int((weight[selected]<.2).sum()))
        for j,co in enumerate(cloud[weight[selected]<.2]):root_tree.insert(co,j)
        root_tree.balance();root_anchor_distance=max(root_tree.find(Vector(co))[2] for co in np.asarray(p)[np.array(pinlocal)])
        reports.append(dict(name=record['name'],render_vertices=len(selected),rows=rows,columns=columns,vertices=len(p),faces=len(fs),components=components,pins=int(sum(pinlocal)),nearest_surface_p95_m=float(np.quantile(distances,.95)),nearest_surface_max_m=float(distances.max()),root_row_distance_to_authored_root_cluster_m=root_distance,root_pin_max_distance_to_authored_root_set_m=float(root_anchor_distance),regular_open_ribbon=regular_open))
        verts.extend(p);faces.extend([tuple(offset+v for v in f) for f in fs]);pins.extend(pinlocal);clump_ids.extend([ci]*len(p))
        bpy.data.objects.remove(obj,do_unlink=True)
    data=bpy.data.meshes.new('27Clumps_ContinuousCages');data.from_pydata(verts,[],faces);data.update()
    attr=data.attributes.new('ProxyClumpID','INT','POINT');attr.data.foreach_set('value',np.array(clump_ids,np.int32))
    proxy=bpy.data.objects.new('HairProxy_27束连续笼体',data);scene.collection.objects.link(proxy);proxy.parent=anchor;proxy.matrix_parent_inverse=Matrix.Identity(4);proxy.matrix_basis=Matrix.Identity(4)
    if checkpoint:
        (checkpoint/'clump_assets.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),'utf8')
        np.savez_compressed(checkpoint/'clump_proxy_rest.npz',vertices=np.array(verts),triangles=np.array(faces),pins=np.array(pins),clump_ids=np.array(clump_ids),source_vertex_ids=ids,source_clump_labels=labels)
    targets=[]
    for ci,record in enumerate(meta['chains']):
        target=bpy.data.objects.new('HairProxy_绑定目标_'+record['name'],bpy.data.meshes.new('ClumpTarget_'+str(ci)));scene.collection.objects.link(target);target.parent=anchor;target.matrix_parent_inverse=Matrix.Identity(4);target.matrix_basis=Matrix.Identity(4)
        group=bpy.data.node_groups.new('Native_ExtractClump_'+str(ci),'GeometryNodeTree');group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
        output=group.nodes.new('NodeGroupOutput');info=group.nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=proxy
        attribute=group.nodes.new('GeometryNodeInputNamedAttribute');attribute.data_type='INT';attribute.inputs['Name'].default_value='ProxyClumpID'
        compare=group.nodes.new('FunctionNodeCompare');compare.data_type='INT';compare.operation='NOT_EQUAL';compare.inputs['B'].default_value=ci
        delete=group.nodes.new('GeometryNodeDeleteGeometry');delete.domain='POINT'
        group.links.new(info.outputs['Geometry'],delete.inputs['Geometry']);group.links.new(attribute.outputs['Attribute'],compare.inputs['A']);group.links.new(compare.outputs['Result'],delete.inputs['Selection']);group.links.new(delete.outputs['Geometry'],output.inputs['Geometry'])
        md=target.modifiers.new('仅提取本发束的原生物理结果','NODES');md.node_group=group;target.hide_render=True;target.display_type='WIRE';targets.append(target)
        bpy.context.view_layer.update();evaluated=target.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        try:
            assert len(mesh.vertices)==reports[ci]['vertices'],('Wrong clump extracted',ci,len(mesh.vertices),reports[ci]['vertices'])
            values=np.array([v.value for v in mesh.attributes['ProxyClumpID'].data]);assert np.all(values==ci),('Cross-clump binding target',ci)
        finally:evaluated.to_mesh_clear()
    return proxy,np.array(pins),reports,targets,labels
