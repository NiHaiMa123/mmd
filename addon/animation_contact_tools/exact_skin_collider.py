"""Preserve skin triangles and close only boundary loops in the REST pose.

This collider adapter retains a source-vertex map instead of resampling skin by
voxels. It is not a general repair for nonmanifold or self-intersecting models.
"""
import bpy,bmesh,numpy as np
from .surface import coords


def build_exact_skin_topology(mesh,arm,profile,weld_distance=1e-6,triangulate=False,include_face_sources=False):
    if profile.get('units_to_m',1.)!=1.:raise ValueError('Exact skin adapter requires metre world coordinates')
    previous=arm.data.pose_position;bm=bmesh.new();motion_modifiers=[(m,m.show_viewport) for m in mesh.modifiers if m.type=='NODES' and m.node_group and m.node_group.name.startswith('HairContact_MeasuredMotion')]
    try:
        for modifier,enabled in motion_modifiers:modifier.show_viewport=False
        arm.data.pose_position='REST';bpy.context.view_layer.update();co=coords(mesh);mesh.data.calc_loop_triangles();attr=mesh.data.attributes[profile['surface_attribute']];triangles=[tuple(t.vertices) for t in mesh.data.loop_triangles if attr.data[t.polygon_index].value in profile['body_classes']+profile['head_classes']];ids=sorted({i for f in triangles for i in f});layer=bm.verts.layers.int.new('SourceVertex');vertices={}
        for i in ids:v=bm.verts.new(co[i]);v[layer]=i;vertices[i]=v
        duplicate=0
        source_layer=bm.faces.layers.int.new('OriginalSkinTriangle')
        for source_index,f in enumerate(triangles):
            try:
                face=bm.faces.new([vertices[i] for i in f]);face[source_layer]=source_index+1
            except ValueError:duplicate+=1
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=weld_distance);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=weld_distance*.1);boundary=[e for e in bm.edges if e.is_boundary];caps=bmesh.ops.holes_fill(bm,edges=boundary,sides=0)['faces'] if boundary else [];bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges)
        if bad:raise ValueError(f'Source skin closure is nonmanifold ({bad} edges); adapt the model explicitly')
        for cap in caps:cap[source_layer]=-1
        if triangulate:bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bm.verts.ensure_lookup_table();bm.verts.index_update();source_ids=np.array([v[layer] for v in bm.verts],dtype=np.int32);faces=[tuple(v.index for v in f.verts) for f in bm.faces]
        metadata={'method':'REST skin triangles + micron seam weld + boundary loop caps','source_triangles':len(triangles),'closed_faces':len(faces),'source_skin_vertices':len(ids),'closed_vertices':len(source_ids),'cap_faces':len(caps),'duplicate_input_faces':duplicate,'nonmanifold_edges':bad,'weld_distance_m':weld_distance,'source_changed':False,'caps_are_approximation':True}
        if include_face_sources:
            metadata['face_source_triangle']=[int(f[source_layer])-1 if f[source_layer]>0 else -1 for f in bm.faces]
            metadata['closure_face_mask']=[f[source_layer]<=0 for f in bm.faces]
        return source_ids,faces,metadata
    finally:
        bm.free();arm.data.pose_position=previous
        for modifier,enabled in motion_modifiers:modifier.show_viewport=enabled
        bpy.context.view_layer.update()
