"""Geometry helpers for head transfer with an explicit, connected neck bridge.

Clipping carries vertex provenance into UVs, skin weights and all shape keys.
The caller must choose the head materials, neck height and rigid head transform.
"""
from collections import defaultdict
import math
import bpy
from mathutils import Vector,Matrix


def material_name(material):return material.mmd_material.name_j or material.name


def clipped_subset(obj,face_ids,name,transform=None,clip_material=None,plane_z=None,above=False):
    transform=Matrix.Identity(4) if transform is None else transform
    old=obj.data;points=[transform@v.co for v in old.vertices]
    vertex_map={};provenance=[];vertices=[];faces=[];uv_faces=[];material_ids=[];materials=[]
    uv=old.uv_layers.active
    def add(prov):
        key=tuple((i,round(w,10)) for i,w in sorted(prov))
        if key not in vertex_map:
            vertex_map[key]=len(vertices);provenance.append(prov)
            vertices.append(sum((points[i]*w for i,w in prov),Vector()))
        return vertex_map[key]
    for fi in face_ids:
        f=old.polygons[fi];material=old.materials[f.material_index]
        polygon=[([(old.loops[li].vertex_index,1.)],{layer.name:layer.data[li].uv.copy() for layer in old.uv_layers}) for li in f.loop_indices]
        if material_name(material)==clip_material:
            result=[]
            for k,current in enumerate(polygon):
                previous=polygon[k-1]
                a,b=(sum((points[i].z*w for i,w in p[0]))-plane_z for p in (previous,current))
                keep_a=a>=-1e-8 if above else a<=1e-8;keep_b=b>=-1e-8 if above else b<=1e-8
                if keep_a!=keep_b:
                    t=a/(a-b);weights=defaultdict(float)
                    for i,w in previous[0]:weights[i]+=w*(1-t)
                    for i,w in current[0]:weights[i]+=w*t
                    result.append((list(weights.items()),{name:value.lerp(current[1][name],t) for name,value in previous[1].items()}))
                if keep_b:result.append(current)
            polygon=result
        if len(polygon)<3:continue
        indices=[add(p[0]) for p in polygon]
        if len(set(indices))<3:continue
        if material not in materials:materials.append(material)
        faces.append(indices);uv_faces.append([p[1] for p in polygon]);material_ids.append(materials.index(material))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    result=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(result)
    for material in materials:mesh.materials.append(material)
    layers={layer.name:mesh.uv_layers.new(name=layer.name) for layer in old.uv_layers}
    if not layers:layers['UVMap']=mesh.uv_layers.new(name='UVMap')
    if uv:mesh.uv_layers.active_index=old.uv_layers.active_index
    for f,mi,values in zip(mesh.polygons,material_ids,uv_faces):
        f.material_index=mi;f.use_smooth=True
        for li,value in zip(f.loop_indices,values):
            for layer_name,layer in layers.items():layer.data[li].uv=value.get(layer_name,Vector((0,0)))
    group_names={g.index:g.name for g in obj.vertex_groups};buckets=defaultdict(list)
    for new,prov in enumerate(provenance):
        weights=defaultdict(float)
        for old_id,t in prov:
            for g in old.vertices[old_id].groups:weights[group_names[g.group]]+=g.weight*t
        for group,weight in weights.items():
            if weight>1e-8:buckets[(group,round(weight,7))].append(new)
    for (group,weight),indices in buckets.items():(result.vertex_groups.get(group) or result.vertex_groups.new(name=group)).add(indices,weight,'REPLACE')
    if old.shape_keys:
        copied={}
        for key in old.shape_keys.key_blocks:
            new=result.shape_key_add(name=key.name,from_mix=False);copied[key.name]=new
            coords=[sum((transform@key.data[i].co*w for i,w in prov),Vector()) for prov in provenance]
            new.data.foreach_set('co',[c for p in coords for c in p]);new.slider_min=key.slider_min;new.slider_max=key.slider_max
            new.value=key.value
        for key in old.shape_keys.key_blocks:copied[key.name].relative_key=copied[key.relative_key.name]
    return result,provenance


def opening(obj,z,tolerance=2e-6):
    edges=defaultdict(list)
    for f in obj.data.polygons:
        for j,i in enumerate(f.vertices):
            k=f.vertices[(j+1)%len(f.vertices)]
            key=tuple(sorted((tuple(round(c,6) for c in obj.data.vertices[i].co),tuple(round(c,6) for c in obj.data.vertices[k].co))))
            edges[key].append((i,k))
    boundary=[rows[0] for rows in edges.values() if len(rows)==1 and all(abs(obj.data.vertices[i].co.z-z)<tolerance for i in rows[0])]
    ids=sorted({i for e in boundary for i in e})
    if len(ids)<8:raise ValueError('No reliable neck opening on '+obj.name)
    center=sum((obj.data.vertices[i].co for i in ids),Vector())/len(ids)
    # Coordinate duplicates from a UV seam share a geometric boundary node.
    unique={tuple(round(c,6) for c in obj.data.vertices[i].co):i for i in ids}
    ids=sorted(unique.values(),key=lambda i:math.atan2(obj.data.vertices[i].co.y-center.y,obj.data.vertices[i].co.x-center.x))
    return ids,center


def adapt_neck(head,ring,target_center,target_radius,fade_height=.035):
    center=sum((head.data.vertices[i].co for i in ring),Vector())/len(ring)
    radius=Vector((max(abs(head.data.vertices[i].co.x-center.x) for i in ring),max(abs(head.data.vertices[i].co.y-center.y) for i in ring),1))
    z=center.z;max_move=0.
    for i,v in enumerate(head.data.vertices):
        p=v.co.copy();s=min(1.,max(0.,(z+fade_height-p.z)/fade_height));s=s*s*(3-2*s)
        # The face chin is in front of the neck and retains its original shape.
        radial=((p.x-center.x)/max(radius.x,1e-6))**2+((p.y-center.y)/max(radius.y,1e-6))**2
        if radial>2.5:s*=max(0.,(4-radial)/1.5)
        if not s:continue
        q=Vector((target_center.x+(p.x-center.x)*target_radius.x/radius.x,target_center.y+(p.y-center.y)*target_radius.y/radius.y,p.z))
        delta=(q-p)*s;v.co+=delta;max_move=max(max_move,delta.length)
        if head.data.shape_keys:
            for key in head.data.shape_keys.key_blocks:key.data[i].co+=delta
    head.data.update();return max_move


def connect_necks(body,head,body_ring,head_ring,name):
    """Combine both meshes; new neck faces reference existing boundary vertices."""
    objects=[body,head];offset=len(body.data.vertices);points=[v.co.copy() for obj in objects for v in obj.data.vertices]
    materials=[];faces=[];uvs=[];material_ids=[]
    for obj,base in ((body,0),(head,offset)):
        for f in obj.data.polygons:
            mat=obj.data.materials[f.material_index]
            if mat not in materials:materials.append(mat)
            faces.append([i+base for i in f.vertices]);uvs.append([{layer.name:layer.data[i].uv.copy() for layer in obj.data.uv_layers} for i in f.loop_indices]);material_ids.append(materials.index(mat))
    center=sum((body.data.vertices[i].co for i in body_ring),Vector())/len(body_ring)
    # Match rings by polar angle, using a zipper that consumes each edge once.
    angle=lambda p:(math.atan2(p.y-center.y,p.x-center.x)+2*math.pi)%(2*math.pi)
    low=sorted(body_ring,key=lambda i:angle(points[i]));high=sorted([i+offset for i in head_ring],key=lambda i:angle(points[i]))
    low_a=[angle(points[i]) for i in low]+[angle(points[low[0]])+2*math.pi]
    high_a=[angle(points[i]) for i in high]+[angle(points[high[0]])+2*math.pi]
    low.append(low[0]);high.append(high[0]);i=j=0;bridge=[]
    while i<len(low)-1 or j<len(high)-1:
        if j==len(high)-1 or (i<len(low)-1 and low_a[i+1]<high_a[j+1]):
            bridge.append([low[i],low[i+1],high[j]]);i+=1
        else:bridge.append([low[i],high[j+1],high[j]]);j+=1
    skin=next(m for m in head.data.materials if material_name(m)=='肌');material=materials.index(skin)
    # Use a genuine neck texel from the source, rather than body UVs on a head map.
    neck_uv={}
    for loop in head.data.loops:
        if loop.vertex_index in head_ring:neck_uv.setdefault(loop.vertex_index,head.data.uv_layers.active.data[loop.index].uv.copy())
    def bridge_uv(k):
        if k>=offset:return neck_uv[k-offset]
        nearest=min(head_ring,key=lambda q:(head.data.vertices[q].co-points[k]).length)
        return neck_uv[nearest]
    faces.extend(bridge);uvs.extend([[{'UVMap':bridge_uv(k)} for k in face] for face in bridge]);material_ids.extend([material]*len(bridge))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(points,[],faces);mesh.update()
    result=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(result)
    for mat in materials:mesh.materials.append(mat)
    layer_names=list(dict.fromkeys(layer.name for obj in objects for layer in obj.data.uv_layers))
    layers={name:mesh.uv_layers.new(name=name) for name in layer_names}
    for f,mi,coords in zip(mesh.polygons,material_ids,uvs):
        f.material_index=mi;f.use_smooth=True
        for li,co in zip(f.loop_indices,coords):
            for layer_name,layer in layers.items():layer.data[li].uv=co.get(layer_name,Vector((0,0)))
    for obj,base in ((body,0),(head,offset)):
        names={g.index:g.name for g in obj.vertex_groups};buckets=defaultdict(list)
        for v in obj.data.vertices:
            for g in v.groups:buckets[(names[g.group],round(g.weight,7))].append(v.index+base)
        for (group,weight),indices in buckets.items():(result.vertex_groups.get(group) or result.vertex_groups.new(name=group)).add(indices,weight,'REPLACE')
    keys=list(dict.fromkeys(k.name for obj in objects for k in obj.data.shape_keys.key_blocks))
    basis=result.shape_key_add(name='Basis',from_mix=False)
    basis.value=0.
    for key_name in keys:
        if key_name=='Basis':continue
        new=result.shape_key_add(name=key_name,from_mix=False);coords=[]
        for obj in objects:
            key=obj.data.shape_keys.key_blocks.get(key_name) or obj.data.shape_keys.key_blocks[0]
            coords.extend(c for p in key.data for c in p.co)
        new.data.foreach_set('co',coords)
        original=body.data.shape_keys.key_blocks.get(key_name)
        settings=head.data.shape_keys.key_blocks.get(key_name) or original
        if settings:new.slider_min=settings.slider_min;new.slider_max=settings.slider_max
        new.value=original.value if original else 0.
    for key in result.data.shape_keys.key_blocks[1:]:
        settings=head.data.shape_keys.key_blocks.get(key.name) or body.data.shape_keys.key_blocks.get(key.name)
        if settings:key.relative_key=result.data.shape_keys.key_blocks.get(settings.relative_key.name) or basis
    # The bridge is part of the same mesh and uses the exact boundary weights.
    return result,{'body_ring':len(body_ring),'head_ring':len(head_ring),'bridge_faces':len(bridge),'body_vertices':offset,'head_vertices':len(head.data.vertices),'rings':{'body':body_ring,'head':[i+offset for i in head_ring]}}


def repair_neck_alpha(obj,neck_z,output):
    """Give the repaired neck an opaque, sampled skin gradient and its own UVs.

    The source skin atlas has intentional transparent collar cutouts. Keep
    that atlas for the ears, and own a small portable texture for the neck.
    """
    import numpy as np
    skin=next(m for m in obj.data.materials if material_name(m)=='肌')
    body=next(m for m in obj.data.materials if material_name(m)=='Body')
    source_node=skin.node_tree.nodes.get('mmd_base_tex')
    body_node=body.node_tree.nodes.get('mmd_base_tex')
    if source_node is None or source_node.image is None or body_node is None or body_node.image is None:
        raise ValueError('Both skin maps are needed to match the neck')
    uv=obj.data.uv_layers.active;selected=[]
    for face in obj.data.polygons:
        if obj.data.materials[face.material_index]!=skin:continue
        points=[obj.data.vertices[i].co for i in face.vertices]
        if min(p.z for p in points)>neck_z+.045 or max(abs(p.x) for p in points)>.05:continue
        selected.append(face)
    if not selected:raise ValueError('No central neck skin domain')
    source_uv=[uv.data[i].uv.copy() for f in selected for i in f.loop_indices]
    body_uv=[uv.data[i].uv.copy() for f in obj.data.polygons if obj.data.materials[f.material_index]==body
             and max(obj.data.vertices[i].co.z for i in f.vertices)>neck_z-.012
             and max(abs(obj.data.vertices[i].co.x) for i in f.vertices)<.05 for i in f.loop_indices]
    def sampled_color(image,coordinates):
        w,h=image.size;buffer=np.empty(w*h*4,dtype=np.float32);image.pixels.foreach_get(buffer);pixels=buffer.reshape(h,w,4)
        values=[pixels[min(h-1,max(0,int(p.y*h))),min(w-1,max(0,int(p.x*w)))] for p in coordinates]
        values=np.asarray([v[:3] for v in values if v[3]>.99 and min(v[:3])>.2])
        if not len(values):raise ValueError('No valid neck skin color samples')
        return np.median(values,axis=0)
    top_color=sampled_color(source_node.image,source_uv);bottom_color=sampled_color(body_node.image,body_uv)
    width,height=16,256;pixels=np.ones((height,width,4),dtype=np.float32)
    for y in range(height):
        t=y/(height-1);t=t*t*(3-2*t);pixels[y,:,:3]=bottom_color*(1-t)+top_color*t
    owned=bpy.data.images.new('Keqing_Neck_Skin_Gradient',width,height,alpha=True)
    owned.colorspace_settings.name=source_node.image.colorspace_settings.name
    owned.pixels.foreach_set(pixels.reshape(-1));owned.update();owned.filepath_raw=str(output);owned.file_format='PNG';owned.save()
    material=skin.copy();material.name='Keqing_NeckBlend';material.mmd_material.name_j='Keqing_NeckBlend'
    material.node_tree.nodes['mmd_base_tex'].image=owned
    obj.data.materials.append(material);index=len(obj.data.materials)-1
    lo=neck_z;hi=max(obj.data.vertices[i].co.z for f in selected for i in f.vertices)
    center=Vector((0,.04,0))
    for face in selected:
        face.material_index=index
        for li in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv=((math.atan2(p.y-center.y,p.x-center.x)+math.pi)/(2*math.pi),min(1.,max(0.,(p.z-lo)/max(hi-lo,1e-6))))
    return {'method':'opaque_neck_gradient','texture':str(output),'material':material.name,'faces':len(selected),
            'sampled_head_rgb':top_color.tolist(),'sampled_body_rgb':bottom_color.tolist(),
            'source_texture':bpy.path.abspath(source_node.image.filepath),'source_image_unchanged':True}
