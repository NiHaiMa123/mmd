"""Trace both sleeve islands through simulation, transfer and contact stages."""
import sys,json,math
from pathlib import Path
from collections import defaultdict
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();folder=ROOT/'outputs/cynical_cloth15/chest_hd';out=ROOT/'outputs/sleeve_13s/diagnosis';out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(folder/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;cloth=bpy.data.objects['Cloth'];proxy=bpy.data.objects['ClothSimulationSurface'];target=bpy.data.objects['ClothShapePreservingTarget'];carrier=bpy.data.objects['ClothUnskinnedVisualCarrier'];mesh=proxy.data;edges=np.array([tuple(e.vertices) for e in mesh.edges]);base=np.array([v.co[:] for v in mesh.vertices]);lengths=np.linalg.norm(base[edges[:,0]]-base[edges[:,1]],axis=1);regions={}
for side in ('L','R'):
 group=proxy.vertex_groups['腕.'+side].index;ids={v.index for v in mesh.vertices if any(g.group==group and g.weight>.5 for g in v.groups)};regions[side]={'ids':sorted(ids),'edges':np.array([k for k,(a,b) in enumerate(edges) if a in ids and b in ids])}
def coords(obj):
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();a=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',a);ev.to_mesh_clear();return a.reshape(-1,3)
report={'time_mapping':'video 13.0s = Blender frame 437; character anatomical L/R both checked','frames':{},'carrier_binding':{}}
for side,r in regions.items():
 selected=np.array(r['ids']);report['carrier_binding'][side]={'proxy_vertices':len(selected),'rest_bounds':[base[selected].min(axis=0).tolist(),base[selected].max(axis=0).tolist()]}
for frame in (47,376,407,417,422,427,432,437,442,447,452,467,496):
 scene.frame_set(frame);row={}
 for label,obj in [('solver',proxy),('blended_target',target)]:
  points=coords(obj);current=np.linalg.norm(points[edges[:,0]]-points[edges[:,1]],axis=1);stage={}
  for side,r in regions.items():
   es=r['edges'];ratios=current[es]/np.maximum(lengths[es],1e-6);worst=int(es[np.argmax(ratios)]);stage[side]={'edge_ratio_p99':float(np.quantile(ratios,.99)),'edge_ratio_max':float(ratios.max()),'edge_ratio_min':float(ratios.min()),'max_edge_m':float(current[es].max()),'worst_edge':edges[worst].tolist(),'bounds':[points[r['ids']].min(axis=0).tolist(),points[r['ids']].max(axis=0).tolist()]}
  row[label]=stage
 report['frames'][str(frame)]=row
 print('SLEEVE_TRACE',frame,json.dumps({name:{side:round(value['edge_ratio_max'],3) for side,value in data.items()} for name,data in row.items()}),flush=True)
# Carrier extrapolation can magnify a small triangle even when solver bounds
# look reasonable. Record the most extreme weights/normal offsets explicitly.
attrs=carrier.data.attributes;weights=np.column_stack([[d.value for d in attrs['OutfitBindW'+str(i)].data] for i in range(3)]);offset=np.array([d.value for d in attrs['OutfitBindNormalOffset'].data]);report['carrier_binding'].update({'max_absolute_barycentric_weight':float(np.abs(weights).max()),'normal_offset_max_m':float(np.abs(offset).max()),'outside_triangle_vertices':int(np.any(weights<-.001,axis=1).sum())})
render=engine('extraction');render._setup_render(scene,1080,1080);scene.view_settings.view_transform='AgX';data=bpy.data.cameras.new('SleeveTrace');data.type='ORTHO';data.ortho_scale=1.35;cam=bpy.data.objects.new('SleeveTrace',data);scene.collection.objects.link(cam);scene.camera=cam;scene.frame_set(437);arm=bpy.data.objects['达妮娅_arm'];center=arm.matrix_world@arm.pose.bones['上半身2'].head+Vector((0,0,-.05));mods=list(cloth.modifiers)
for label,last in [('armature',0),('cloth_transfer',1),('skin_contact',3),('final',len(mods)-1)]:
 for k,m in enumerate(mods):m.show_render=k<=last
 for angle,direction in [('front',(0,-1,0)),('back',(0,1,0))] if label=='final' else [('front',(0,-1,0))]:
  cam.location=center+Vector(direction)*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{label}_{angle}_437.png');bpy.ops.render.render(write_still=True)
(out/'trace.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('SLEEVE_DIAGNOSIS_COMPLETE',flush=True)
