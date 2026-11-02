"""Actual visible garment/body triangle intersections with material localization."""
import argparse,json,sys,time
from collections import Counter
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,triangle_crosses,inside_votes
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--output',required=True);p.add_argument('--frames',nargs='+',type=int,default=[325]);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];regions=skin_regions(body,arm)
def meshdata(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh();mesh.calc_loop_triangles();co=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',co);co=co.reshape(-1,3);m=np.array(obj.matrix_world);co=co@m[:3,:3].T+m[:3,3];faces=np.array([t.vertices[:] for t in mesh.loop_triangles],dtype=np.int32);materials=np.array([t.material_index for t in mesh.loop_triangles]);names=[m.name if m else '<none>' for m in mesh.materials];evaluated.to_mesh_clear();return co,faces,materials,names
inventory={}
for obj in engine('import_export').model_meshes():inventory[obj.name]={'vertices':len(obj.data.vertices),'materials':[m.name for m in obj.data.materials],'modifiers':[{'name':m.name,'type':m.type,'viewport':m.show_viewport,'render':m.show_render} for m in obj.modifiers]}
helpers={}
for name in ('ClothKinematicReference','ClothSimulationSurface','ClothShapePreservingTarget','ClothUnskinnedVisualCarrier','Outfit_SkinCollider'):
    obj=bpy.data.objects.get(name)
    if not obj:continue
    helpers[name]={'vertices':len(obj.data.vertices),'attributes':[x.name for x in obj.data.attributes],'modifiers':[{'name':m.name,'type':m.type,'viewport':m.show_viewport,'cache':m.filepath if m.type=='MESH_CACHE' else None} for m in obj.modifiers],'groups':[g.name for g in obj.vertex_groups]}
report={'scope':'Visible garment versus ALL evaluated skin/nail triangles, including mixed bone boundaries; not cloth self/cross-layer or CCD acceptance','blend':a.blend,'inventory':inventory,'helpers':helpers,'frames':{}};start=time.perf_counter();(out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
garments=[bpy.data.objects[n] for n in inventory if n in ('Cloth','Stockings','SleeveLining') or 'Bridal' in n]
for frame in a.frames:
    scene.frame_set(frame);bpy.context.view_layer.update();co,bf,bm,bnames=meshdata(body);skin_faces=[];labels=[]
    region_by_face={tuple(f):region for region,fs in regions['faces'].items() if region!='excluded' for f in fs}
    skin_materials={'Body','面','面1','肌','Keqing_NeckBlend','Nails'}
    for face,material in zip(bf,bm):
        if bnames[int(material)] not in skin_materials:continue
        skin_faces.append(face);labels.append(region_by_face.get(tuple(face),'mixed_skin_boundary'))
    ids=np.unique(skin_faces);remap={int(v):i for i,v in enumerate(ids)};sf=np.array([[remap[v] for v in f] for f in skin_faces]);sc=co[ids];tree=BVHTree.FromPolygons(sc.tolist(),sf.tolist(),all_triangles=True);row={};exports={'skin':sc,'skin_faces':sf};proxy_tree=None
    proxy=bpy.data.objects.get('Outfit_ClosedSkinContactProxy')
    if proxy:
        pc,pf,_,_=meshdata(proxy);proxy_tree=BVHTree.FromPolygons(pc.tolist(),pf.tolist(),all_triangles=True)
    for obj in garments:
        if obj.hide_viewport:continue
        gc,gf,materials,material_names=meshdata(obj);gt=BVHTree.FromPolygons(gc.tolist(),gf.tolist(),all_triangles=True);counts=Counter();face_counts=Counter();bad=set();pairs=[]
        for i,j in gt.overlap(tree):
            if triangle_crosses([Vector(v) for v in gc[gf[i]]],[Vector(v) for v in sc[sf[j]]]):
                material=material_names[int(materials[i])] if int(materials[i])<len(material_names) else '<invalid_material_'+str(materials[i])+'>';counts[(material,labels[j])]+=1;face_counts[material]+=1;bad.add(i);pairs.append((i,j))
        name=obj.name;row[name]={'vertices':len(gc),'triangles':len(gf),'true_crossings':sum(counts.values()),'by_material_and_skin':{' | '.join(k):v for k,v in counts.items()},'affected_cloth_triangles':len(bad),'bounds_m':[gc.min(axis=0).tolist(),gc.max(axis=0).tolist()],'bad_triangle_ids':sorted(bad),'pairs':pairs}
        if proxy_tree and name in ('Cloth','Stockings','SleeveLining'):
            buried=[];proxy_inside=0
            for point in gc:
                q,n,fi,d=tree.find_nearest(Vector(point))
                if d>.08 or (Vector(point)-q).dot(n)>=-.0001:continue
                pq,pn,pi,pd=proxy_tree.find_nearest(Vector(point))
                if (Vector(point)-pq).dot(pn)<-.00001 and inside_votes(proxy_tree,Vector(point)):
                    proxy_inside+=1;buried.append(float(d))
            row[name]['buried_vertex_probe']={'vertices_negative_to_skin_and_inside_proxy':proxy_inside,'max_nearest_skin_depth_m':max(buried,default=0.),'interpretation':'Diagnostic combines local normal sign and proxy containment; proxy padding and skin topology prevent treating this as exact signed distance'}
        if bad:row[name]['intersection_bounds_m']=[gc[np.unique(gf[list(bad)])].min(axis=0).tolist(),gc[np.unique(gf[list(bad)])].max(axis=0).tolist()]
        exports[name]=gc;exports[name+'_faces']=gf;exports[name+'_materials']=materials;print('OUTFIT_BODY_AUDIT',frame,name,sum(counts.values()),json.dumps(row[name]['by_material_and_skin'],ensure_ascii=False),flush=True)
    np.savez_compressed(out/f'surfaces_{frame}.npz',**exports);report['frames'][str(frame)]=row;(out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
report['seconds']=time.perf_counter()-start;(out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
