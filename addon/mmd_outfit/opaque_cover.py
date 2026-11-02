"""Back up only skin faces copied one-for-one into an opaque tight garment.

This is a dressed export, not a garment transparency/undressing switch.
Unknown alpha inputs or changing UVs never justify removing skin.
"""
import importlib
import sys
import numpy as np


def opaque_faces(patch, engine):
    from collections import Counter
    uv=next((layer for layer in patch.data.uv_layers if layer.active_render),None)
    report={'method':'entire expanded UV rectangle opaque in standard MMD alpha inputs',
            'candidate_faces':len(patch.data.polygons),'unsupported':{},'by_material':{}}
    if uv is None:
        report['unsupported']['mesh']='no render UV'
        return [],report
    rectangle_is_zero=engine('visibility').rectangle_is_zero
    cache={}
    def material_alpha(material):
        if not material or not material.use_nodes or material.animation_data or material.node_tree.animation_data:
            return None,'missing, non-node or animated material'
        nodes=material.node_tree.nodes
        shader,base=nodes.get('mmd_shader'),nodes.get('mmd_base_tex')
        if shader is None or shader.node_tree is None or not shader.node_tree.name.startswith('MMDShaderDev'):
            return None,'unsupported shader'
        scalar=shader.inputs.get('Alpha')
        if scalar is None or scalar.is_linked or not np.isfinite(scalar.default_value) or scalar.default_value<1-1e-8:
            return None,'non-opaque or custom material alpha'
        def image_alpha(node):
            image=node.image if node and node.type=='TEX_IMAGE' else None
            if image is None or image.source not in {'FILE','GENERATED'}:
                return None
            # Importers may leave toon/sphere images unloaded until rendering.
            # Reading pixels loads them without requiring a preview first.
            size=len(image.pixels)
            w,h=image.size
            if not w or not h or size!=w*h*4:
                return None
            pixels=np.empty(size,dtype=np.float32)
            try:
                image.pixels.foreach_get(pixels)
            except (RuntimeError,ValueError):
                return None
            return np.ones((h,w),dtype=np.float32) if image.alpha_mode=='NONE' else pixels.reshape(h,w,4)[:,:,3].copy()
        for name in ('Toon Alpha','Sphere Alpha'):
            socket=shader.inputs.get(name)
            if socket is None:
                return None,'missing alpha input'
            if not socket.is_linked:
                if not np.isfinite(socket.default_value) or socket.default_value<1-1e-8:
                    return None,'non-opaque '+name
            else:
                if len(socket.links)!=1 or socket.links[0].from_socket.name!='Alpha':
                    return None,'custom '+name
                values=image_alpha(socket.links[0].from_node)
                if values is None or not np.isfinite(values).all() or np.any(values<1-1e-8):
                    return None,'uncertain '+name
        socket=shader.inputs.get('Base Alpha')
        if socket is None or len(socket.links)!=1 or socket.links[0].from_node!=base or socket.links[0].from_socket.name!='Alpha':
            return None,'custom base alpha'
        if base.extension!='REPEAT' or base.projection!='FLAT' or base.interpolation not in {'Linear','Closest'}:
            return None,'unsupported texture mapping'
        vector=base.inputs.get('Vector')
        if vector is None or len(vector.links)!=1 or vector.links[0].from_node.name!='mmd_tex_uv' or vector.links[0].from_socket.name!='Base UV':
            return None,'custom UV mapping'
        group=vector.links[0].from_node.node_tree
        output=next((n for n in group.nodes if n.type=='GROUP_OUTPUT' and n.is_active_output),None) if group else None
        coord=output.inputs.get('Base UV') if output else None
        if coord is None or len(coord.links)!=1 or coord.links[0].from_node.type!='TEX_COORD' or coord.links[0].from_socket.name!='UV':
            return None,'custom UV group'
        alpha=image_alpha(base)
        return (alpha,None) if alpha is not None else (None,'unreadable base image')
    covered=[]; counts=Counter()
    for face in patch.data.polygons:
        material=patch.data.materials[face.material_index]
        if material not in cache:
            cache[material]=material_alpha(material)
            if cache[material][1]:
                report['unsupported'][material.name]=cache[material][1]
        alpha,_=cache[material]
        if alpha is not None and rectangle_is_zero(1-alpha,[uv.data[i].uv for i in face.loop_indices]):
            covered.append(face.index); counts[material.name]+=1
    report['opaque_faces']=len(covered)
    report['by_material']=dict(counts)
    return covered,report


def back_up_covered_skin(body, patch, target_faces, copy_subset, region, engine):
    """Use face correspondence made by copy_subset, never proximity culling."""
    from .preserved_shoe import replace_mesh
    import bpy
    covered,report=opaque_faces(patch,engine)
    root=engine('import_export').mmd_root(body)
    moving=set()
    if root and root.mmd_root.uv_morphs:
        package=next((p for p in engine('import_export').MMD_TOOLS_MODULES if p in sys.modules),None)
        if not package:
            raise ValueError('Cannot verify target UV morph coverage')
        reader=importlib.import_module(package+'.core.morph').FnMorph
        for morph in root.mmd_root.uv_morphs:
            if morph.uv_index==0:
                moving.update(i for i,d in reader.get_uv_morph_offset_map(body,morph).items() if abs(d[0])+abs(d[1])>1e-8)
    removed=[target_faces[i] for i in covered if not any(v in moving for v in body.data.polygons[target_faces[i]].vertices)]
    report['uv_morph_faces_retained']=len(covered)-len(removed)
    report.update(masked_skin_faces=len(removed),unmasked_skin_faces=len(target_faces)-len(removed),
                  mode='opaque_cover_backup',scope='dressed export; no automatic garment removal or alpha fade')
    if not removed:
        report['backup_object']=None
        return report
    backup,ids=copy_subset(body,removed,'OpaqueGlove_SkinBackup' if region=='hands' else 'OpaqueCover_SkinBackup')
    backup['mmd_garment']=False; backup['outfit_backup']=True
    backup['original_vertex_ids']=ids
    backup['original_face_ids']=removed
    backup['cover_material']=patch.data.materials[patch.data.polygons[0].material_index].name
    backup.parent=None
    backup.hide_render=True; backup.hide_set(True)
    removed_set=set(removed)
    retained,_=copy_subset(body,[f.index for f in body.data.polygons if f.index not in removed_set],'RetainedCoveredBody')
    replace_mesh(body,retained)
    report['backup_object']=backup.name
    report['backup_vertices']=len(backup.data.vertices)
    report['backup_shape_keys']=len(backup.data.shape_keys.key_blocks) if backup.data.shape_keys else 0
    return report
