"""Full-head component/attachment inventory and sampled visible-skin baseline."""
import json,sys,re
from pathlib import Path
from collections import Counter,defaultdict
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,crosses
base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle';out.mkdir(parents=True,exist_ok=True);source=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/surface_projection/assembled_temporal/SelectedBundle_SurfaceCorrective_NotFullyAccepted.blend';engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);profile=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);topology=np.load(base/'hair_tests_v2/hair_topology.npz');ids=topology['ids'];component=dict(zip(ids.tolist(),topology['component'].tolist()));hairfaces=topology['faces'].tolist();anchors=set(profile['root_hair_anchor_bones']);groupnames={g.index:g.name for g in mesh.vertex_groups if g.name in arm.data.bones}
def family(name):
 if name in anchors:return 'ATTACHMENT:'+name
 bone=arm.data.bones.get(name)
 while bone and bone.parent and bone.parent.name not in anchors:bone=bone.parent
 return bone.name if bone else name
families={n:family(n) for n in groupnames.values()};bpy.context.scene.frame_set(1);bpy.context.view_layer.update();co=coords(mesh);head=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);inv=np.linalg.inv(head);headlocal=co@inv[:3,:3].T+inv[:3,3];stats=[]
for c in sorted(set(component.values())):
 selected=[i for i in ids if component[int(i)]==c];weights=Counter();roots=Counter();anchor=0
 for i in selected:
  for g in mesh.data.vertices[i].groups:
   if g.group in groupnames:weights[groupnames[g.group]]+=g.weight;roots[families[groupnames[g.group]]]+=g.weight
  anchor+=sum(g.weight for g in mesh.data.vertices[i].groups if groupnames.get(g.group) in anchors)>=.8
 stats.append({'component':c,'vertices':len(selected),'triangles':sum(component[f[0]]==c for f in hairfaces),'head_local_min':headlocal[selected].min(0).tolist(),'head_local_max':headlocal[selected].max(0).tolist(),'head_anchor_vertices_ge_08':int(anchor),'dominant_bones':weights.most_common(12),'attachment_families':roots.most_common(16),'mixed_attachment_families':sum(v>len(selected)*.01 for n,v in roots.items())>1,'already_sampled_pass':c==4})
frames=sorted(set(list(range(1,451,15))+[240,247.5,256,285,321,342,350,355.125,373,450]));rows=[]
for frame in frames:
 bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();co=coords(mesh);world=co.tolist();tree=BVHTree.FromPolygons(world,hairfaces,all_triangles=True);counts=Counter();byregion=Counter();bycomponent=defaultdict(Counter)
 for role in ('head','torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R'):
  bodyfaces=parts['faces'][role];bodytree=BVHTree.FromPolygons(world,bodyfaces,all_triangles=True)
  for ia,ib in tree.overlap(bodytree):
   a,b=hairfaces[ia],bodyfaces[ib]
   if crosses([Vector(co[i]) for i in a],[Vector(co[i]) for i in b]):c=component[a[0]];counts[c]+=1;byregion[role]+=1;bycomponent[c][role]+=1
 row={'frame':frame,'total_crossings':sum(counts.values()),'by_component':dict(counts),'by_region':dict(byregion),'component_regions':{str(c):dict(v) for c,v in bycomponent.items()}};rows.append(row);print('HAIR_INVENTORY_FRAME',frame,row['total_crossings'],dict(counts),flush=True)
result={'source':str(source),'component_count':len(stats),'components':stats,'sampled_frames':frames,'samples':rows,'all_hair_solved':False,'initial_attachment_contact_exempted':False,'ccd_proven':False}
(out/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
for c,side in [(3,'L'),(4,'R')]:
 selected=topology['ids'][topology['component']==c].tolist();chain=[f'Sidetail{i}.{side}' for i in range(1,7)];assert all(n in arm.pose.bones for n in chain);bundle={'schema':1,'name':'Sidetail_'+side,'component':c,'vertex_ids':selected,'guide_bones':chain,'anchor_bone':'頭','source_vertex_count':len(mesh.data.vertices),'source_profile':str(base/'body_track/rig_profile.json')};(out/f'bundle_{side}.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf8')
print('HAIR_INVENTORY_COMPLETE',out,flush=True)
