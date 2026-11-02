"""Explicit, stable-topology selection and guide mapping for one hair bundle."""
import numpy as np


def resolve_bundle(mesh,arm,parts,config):
    if config.get('schema')!=1:raise ValueError('Unsupported hair bundle profile schema')
    ids=np.asarray(config['vertex_ids'],dtype=int)
    if len(ids)==0 or len(np.unique(ids))!=len(ids) or ids.min()<0 or ids.max()>=len(mesh.data.vertices):raise ValueError('Bundle vertex map is invalid')
    if config.get('source_vertex_count',len(mesh.data.vertices))!=len(mesh.data.vertices):raise ValueError('Bundle source topology changed')
    names=config['guide_bones'];anchor=config['anchor_bone']
    if len(names)<2 or any(n not in arm.pose.bones for n in names) or anchor not in arm.pose.bones:raise ValueError('Bundle guide or anchor bones are missing')
    for a,b in zip(names,names[1:]):
        if a not in {p.name for p in arm.data.bones[b].parent_recursive}:raise ValueError('Guide bones do not follow one descendant chain')
    selected=set(ids.tolist());faces=[];polys=[];partial=[]
    for region in ('hair_root','hair_mobile'):
        for face,poly in zip(parts['faces'][region],parts['source_faces'][region]):
            count=sum(i in selected for i in face)
            if count==3:faces.append(face);polys.append(poly)
            elif count:partial.append(poly)
    if not faces:raise ValueError('Bundle selection contains no hair triangles')
    if partial and not config.get('allow_cut_boundary',False):raise ValueError('Selection cuts hair triangles; configure a seam-aware adapter explicitly')
    if {i for f in faces for i in f}!=selected:raise ValueError('Bundle contains vertices outside its selected triangles')
    subset={k:dict(v) if isinstance(v,dict) else v for k,v in parts.items()}
    for key in ('faces','ids','source_faces','samples','closed'):
        for region in ('hair_root','hair_mobile'):subset[key].pop(region,None)
    subset['faces']['hair_mobile']=faces;subset['source_faces']['hair_mobile']=polys;subset['ids']['hair_mobile']=ids.tolist();subset['samples']['hair_mobile']=ids[::8].tolist();subset['closed']['hair_mobile']=False
    rootmask=None
    if 'root_vertex_ids' in config:
        rootids=np.asarray(config['root_vertex_ids'],dtype=int)
        if not len(rootids) or len(np.unique(rootids))!=len(rootids) or not set(rootids.tolist())<=selected:raise ValueError('Explicit root selection must be a unique nonempty subset of the bundle')
        rootmask=np.isin(ids,rootids)
    return {'ids':ids,'faces':faces,'polygons':polys,'parts':subset,'guide_bones':[arm.pose.bones[n] for n in names],'anchor_bone':anchor,'root_pin_mask':rootmask,'partial_boundary_polygons':sorted(set(partial))}
