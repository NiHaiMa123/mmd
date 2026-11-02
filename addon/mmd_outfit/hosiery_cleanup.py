"""Remove the spurious gusset branch and internal anatomy from hosiery only."""
from collections import defaultdict


def clean(body, stockings):
    mesh=body.data
    skin=[f for f in mesh.polygons if mesh.materials[f.material_index].mmd_material.name_j=='Body']
    vertex_faces=defaultdict(list)
    for f in skin:
        for i in f.vertices:vertex_faces[i].append(f.index)
    remaining={f.index for f in skin};internal=[]
    while remaining:
        stack=[remaining.pop()];faces=[];ids=set()
        while stack:
            fi=stack.pop();faces.append(fi)
            for i in mesh.polygons[fi].vertices:
                ids.add(i)
                for j in vertex_faces[i]:
                    if j in remaining:remaining.remove(j);stack.append(j)
        points=[mesh.vertices[i].co for i in ids]
        if max(abs(p.x) for p in points)<.025 and min(p.z for p in points)>.85 and max(p.z for p in points)<.95:
            internal.extend(faces)
    mask=mesh.attributes['OutfitNylonFaces'];changed=[]
    for fi in internal:
        if mask.data[fi].value:changed.append(fi)
        mask.data[fi].value=False
    removed=0
    for mod in stockings.modifiers:
        if mod.type!='NODES' or not mod.node_group:continue
        tree=mod.node_group
        starts=[n for n in tree.nodes if n.bl_idname=='GeometryNodeInputNamedAttribute' and n.inputs['Name'].default_value=='OutfitGussetFaces']
        seen=set();todo=list(starts)
        while todo:
            node=todo.pop()
            if node in seen:continue
            seen.add(node)
            for socket in node.outputs:
                for link in list(socket.links):
                    if link.to_node.bl_idname=='GeometryNodeJoinGeometry':tree.links.remove(link);removed+=1
                    else:todo.append(link.to_node)
    mesh.update();body.update_tag(refresh={'DATA'});stockings.update_tag(refresh={'DATA'})
    return {'disconnected_gusset_branches':removed,'internal_faces_excluded_from_nylon':len(changed),
            'excluded_body_face_ids':changed,'body_faces_deleted':0,'feet_modified':False}
