"""Static body attachment using smooth skeletal frames, avoiding triangle twists."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.contact_position_override import install
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];carrier=bpy.data.objects['BodyFittedGarmentCarrier'];sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.show_viewport=False;sub.show_render=False;binding=cloth.modifiers['Panels follow actual posed body'];binding.show_viewport=False;binding.show_render=False
def capture(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles]);ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces
cache=cloth.modifiers.get('Structured cloth absolute positions')
if cache:cache.show_viewport=False;cache.show_render=False
raw,faces=capture(cloth);posed,_=capture(body);bmat=np.array(body.matrix_world);brest=np.array([v.co[:] for v in body.data.vertices]);brest=brest@bmat[:3,:3].T+bmat[:3,3];cma=np.array(carrier.matrix_world);fitted=np.array([v.co[:] for v in carrier.data.vertices]);fitted=fitted@cma[:3,:3].T+cma[:3,3];attrs=carrier.data.attributes;indices=np.array([[attrs['SleeveStableI'+str(k)].data[i].value for k in range(3)] for i in range(len(raw))]);bary=np.array([[attrs['SleeveStableW'+str(k)].data[i].value for k in range(3)] for i in range(len(raw))]);weight=np.array([v.value for v in cloth.data.attributes['OutfitLiveSkinBinding'].data]);chosen=np.flatnonzero(weight>0);aw=np.array(arm.matrix_world);transforms={g.index:aw@np.array(arm.pose.bones[g.name].matrix)@np.linalg.inv(np.array(arm.data.bones[g.name].matrix_local))@np.linalg.inv(aw) for g in body.vertex_groups if g.name in arm.data.bones};frames=np.zeros((len(brest),3,3))
for v in body.data.vertices:
    total=0.
    for g in v.groups:
        if g.group in transforms:frames[v.index]+=transforms[g.group][:3,:3]*g.weight;total+=g.weight
    if total:frames[v.index]/=total
    else:frames[v.index]=np.eye(3)
ids=indices[chosen];w=bary[chosen];qrest=np.sum(brest[ids]*w[:,:,None],axis=1);qpose=np.sum(posed[ids]*w[:,:,None],axis=1);matrix=np.sum(frames[ids]*w[:,:,None,None],axis=1);u,s,vt=np.linalg.svd(matrix);rotation=u@vt;negative=np.linalg.det(rotation)<0;u[negative,:,-1]*=-1;rotation=u@vt;target=qpose+np.einsum('nij,nj->ni',rotation,fitted[chosen]-qrest);final=raw.copy();final[chosen]+=(target-raw[chosen])*weight[chosen,None];mod=install(cloth,final,325);bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=list(cloth.modifiers).index(sub));sub.show_viewport=True;sub.show_render=True;sub.levels=2;sub.render_levels=2
stock=bpy.data.objects['ContinuousExteriorNylon']
for polygon in stock.data.polygons:polygon.use_smooth=True
edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0);length=np.linalg.norm(final[edges[:,0]]-final[edges[:,1]],axis=1);source_length=np.linalg.norm(raw[edges[:,0]]-raw[edges[:,1]],axis=1);ratio=length/np.maximum(source_length,1e-8);report={'status':'SMOOTH_SKIN_ATTACHMENT_REQUIRES_AUDIT','frame':325,'selected_vertices':len(chosen),'max_displacement_m':float(np.linalg.norm(final-raw,axis=1).max()),'edge_ratio_quantiles':np.quantile(ratio,[0,.01,.5,.99,1]).tolist(),'new_physics':False};scene.frame_start=325;scene.frame_end=325;bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_SmoothSkin325.blend'),compress=True);(out/'fit_report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
