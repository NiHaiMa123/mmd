"""Conservative, texture-aware garment faces for contact diagnostics only.

Drop a face only when the entire expanded UV bounding rectangle has zero
base alpha in the standard MMD shader. Geometry and materials stay untouched.
Unsupported shader layouts, UV morphs and uncertain cases remain candidates.
"""
from collections import Counter
import importlib
import math
import sys
import numpy as np


def repeat_segments(low, high, size):
    count = high-low+1
    if count >= size:
        return [(0,size)]
    start = low % size
    stop = start+count
    return [(start,stop)] if stop <= size else [(start,size),(0,stop-size)]


def rectangle_is_zero(alpha, points):
    height,width = alpha.shape
    xs,ys = [p[0] for p in points],[p[1] for p in points]
    if not all(math.isfinite(v) for v in [*xs,*ys]):
        return False
    # Include bilinear neighbours and both UV boundary endpoints.
    xr = repeat_segments(math.floor(min(xs)*width-.5),math.ceil(max(xs)*width+.5),width)
    yr = repeat_segments(math.floor(min(ys)*height-.5),math.ceil(max(ys)*height+.5),height)
    return all(np.isfinite(alpha[y0:y1,x0:x1]).all() and not np.any(alpha[y0:y1,x0:x1]>1e-8)
               for x0,x1 in xr for y0,y1 in yr)


def visible_garment_faces(obj, face_ids):
    root = obj
    while root is not None and getattr(root,'mmd_type','NONE')!='ROOT':
        root = root.parent
    uv = next((layer for layer in obj.data.uv_layers if layer.active_render), None)
    report = {'method':'provably zero base alpha over expanded UV rectangles',
              'raw_faces':len(face_ids),'transparent_faces':0,'by_material':{},'unsupported':{}}
    if uv is None:
        report['unsupported']['mesh']='no render UV; all faces retained'
        return list(face_ids),report
    moving_uv=set()
    uv_morphs=[m for m in root.mmd_root.uv_morphs if m.uv_index==0] if root else []
    if uv_morphs:
        from .import_export import MMD_TOOLS_MODULES
        package=next((name for name in MMD_TOOLS_MODULES if name in sys.modules),None)
        if package is None:
            report['unsupported']['mesh']='UV morph reader unavailable; all faces retained'
            return list(face_ids),report
        reader=importlib.import_module(package+'.core.morph').FnMorph
        for morph in uv_morphs:
            moving_uv.update(i for i,delta in reader.get_uv_morph_offset_map(obj,morph).items()
                             if abs(delta[0])>1e-8 or abs(delta[1])>1e-8)
    report['uv_morph_vertices_retained']=len(moving_uv)
    cache,hidden = {},Counter()
    def alpha_for(material):
        if material is None or not material.use_nodes:
            return None,'non-node material'
        nodes=material.node_tree.nodes
        base,shader=nodes.get('mmd_base_tex'),nodes.get('mmd_shader')
        if base is None or base.type!='TEX_IMAGE' or shader is None or shader.node_tree is None or not shader.node_tree.name.startswith('MMDShaderDev'):
            return None,'unsupported shader'
        socket=shader.inputs.get('Base Alpha')
        if socket is None or len(socket.links)!=1 or socket.links[0].from_node!=base or socket.links[0].from_socket.name!='Alpha':
            return None,'custom base-alpha link'
        image=base.image
        if image is None or not image.has_data or image.channels!=4 or image.alpha_mode=='NONE' or image.source not in {'FILE','GENERATED'}:
            return None,'unsupported image'
        if base.extension!='REPEAT' or base.projection!='FLAT':
            return None,'unsupported texture mapping'
        vector=base.inputs.get('Vector')
        if vector is None or len(vector.links)!=1 or vector.links[0].from_node.name!='mmd_tex_uv' or vector.links[0].from_socket.name!='Base UV':
            return None,'custom texture coordinates'
        uv_group=vector.links[0].from_node.node_tree
        output=next((n for n in uv_group.nodes if n.type=='GROUP_OUTPUT' and n.is_active_output),None) if uv_group else None
        uv_socket=output.inputs.get('Base UV') if output else None
        if (uv_socket is None or len(uv_socket.links)!=1
                or uv_socket.links[0].from_node.type!='TEX_COORD'
                or uv_socket.links[0].from_socket.name!='UV'):
            return None,'custom UV group'
        if base.interpolation not in {'Linear','Closest'}:
            return None,'unsupported texture interpolation'
        width,height=image.size
        if width<=0 or height<=0:
            return None,'empty image'
        pixels=np.empty(width*height*4,dtype=np.float32)
        image.pixels.foreach_get(pixels)
        alpha=pixels.reshape(height,width,4)[:,:,3].copy()
        return (None if np.all(alpha>1e-8) else alpha),None
    kept=[]
    for fi in face_ids:
        face=obj.data.polygons[fi]
        if any(i in moving_uv for i in face.vertices):
            kept.append(fi)
            continue
        material=obj.data.materials[face.material_index] if face.material_index<len(obj.data.materials) else None
        if material not in cache:
            cache[material]=alpha_for(material)
            if cache[material][1]:
                report['unsupported'][material.name if material else '<none>']=cache[material][1]
        alpha,_=cache[material]
        if alpha is not None and rectangle_is_zero(alpha,[uv.data[i].uv for i in face.loop_indices]):
            hidden[material.name]+=1
        else:
            kept.append(fi)
    report['transparent_faces']=sum(hidden.values())
    report['by_material']=dict(hidden)
    report['visible_candidate_faces']=len(kept)
    return kept,report
