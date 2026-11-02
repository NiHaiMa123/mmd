"""Audit original displayed face classes, without using solver collider topology."""
import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,crosses
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--out',required=True);p.add_argument('--frames',default='326,331,336');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);src=Path(a.delivery);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);pub=json.loads((src/'cache_publication.json').read_text('utf8'));manifest=json.loads((Path(pub['input'])/'export_complete.json').read_text('utf8'));profile=json.loads(Path(manifest['rig_profile']).read_text('utf8'));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(src/'完整角色_整头连续物理_15秒.blend'),load_ui=False,use_scripts=False);m=bpy.data.objects[profile['mesh']];s=bpy.context.scene;m.data.calc_loop_triangles();attr=m.data.attributes[profile['surface_attribute']];alltri=np.asarray([t.vertices[:] for t in m.data.loop_triangles]);classes=np.asarray([attr.data[t.polygon_index].value for t in m.data.loop_triangles]);materials=np.asarray([m.data.polygons[t.polygon_index].material_index for t in m.data.loop_triangles]);hair=np.flatnonzero(np.isin(classes,profile['hair_classes']));skin=np.flatnonzero(np.isin(classes,profile['body_classes']+profile['head_classes']));rows=[]
for frame in map(float,a.frames.split(',')):
 s.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();co=coords(m);v=[Vector(x) for x in co];ht=BVHTree.FromPolygons(co.tolist(),alltri[hair].tolist(),all_triangles=True);bt=BVHTree.FromPolygons(co.tolist(),alltri[skin].tolist(),all_triangles=True);hits=[]
 for hi,bi in ht.overlap(bt):
  hf=alltri[hair[hi]];bf=alltri[skin[bi]]
  if set(hf).intersection(bf):continue
  if crosses([v[i] for i in hf],[v[i] for i in bf]):hits.append(dict(hair_triangle=int(hair[hi]),skin_triangle=int(skin[bi]),hair_vertices=hf.tolist(),skin_vertices=bf.tolist(),hair_material=m.material_slots[int(materials[hair[hi]])].material.name,skin_material=m.material_slots[int(materials[skin[bi]])].material.name,point=(co[hf].mean(0)).tolist()))
 rows.append(dict(frame=frame,raw_skin_triangles=len(skin),raw_hair_triangles=len(hair),crossings=len(hits),witnesses=hits[:100]));np.save(out/f'world_{frame:g}.npy',co);print('RAW_RENDER_SURFACE_AUDIT',frame,len(hits),flush=True)
classification=[]
for mi,slot in enumerate(m.material_slots):
 selected=materials==mi
 if selected.any():classification.append(dict(material=slot.material.name,triangles=int(selected.sum()),surface_classes={str(c):int(np.sum(classes[selected]==c)) for c in np.unique(classes[selected])}))
mods=[dict(name=mod.name,type=mod.type,viewport=mod.show_viewport,render=mod.show_render,levels=getattr(mod,'levels',None),render_levels=getattr(mod,'render_levels',None),node_group=mod.node_group.name if mod.type=='NODES' and mod.node_group else None) for mod in m.modifiers];report=dict(rows=rows,modifiers=mods,materials=classification,skin_collider_summary={k:v for k,v in manifest['skin_topology'].items() if not isinstance(v,list)},visible_meshes=[dict(name=o.name,vertices=len(o.data.vertices)) for o in s.objects if o.type=='MESH' and not o.hide_render and not o.name.startswith('BG::')]);(out/'raw_surfaces.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('RAW_SURFACE_REPORT_READY',flush=True)
