"""Compare the delivered cloth, bone-only motion, and cloth without guards.

Read the baked trial in a separate Blender. Do not modify the user's open
scene, the prepared blend, or the simulation's modifier/cache configuration.
"""
import sys,json,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/trial3/Cynical_Cloth_15s.blend';bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
out=ROOT/'outputs/cynical_cloth15/research_wrinkles/ablation';out.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene;cloth=bpy.data.objects['Cloth'];proxy=bpy.data.objects['ClothSimulationSurface'];sim=next(m for m in proxy.modifiers if m.type=='CLOTH');assert sim.point_cache.is_baked
follow=cloth.modifiers['Follow simulated fabric'];guards=[m for m in cloth.modifiers if m.type in {'SHRINKWRAP','NODES'}]
state={m:(m.show_viewport,m.show_render) for m in cloth.modifiers};render=engine('extraction');render._setup_render(scene,700,850);scene.view_settings.view_transform='AgX'
data=bpy.data.cameras.new('WrinkleComparison');data.type='ORTHO';data.ortho_scale=1.42;cam=bpy.data.objects.new('WrinkleComparison',data);scene.collection.objects.link(cam);scene.camera=cam
body=bpy.data.objects['达妮娅_mesh'];result={'source':str(source),'modifier_stack':[(m.name,m.type) for m in cloth.modifiers],'cache_initially_baked':True,'comparisons':{}}
def points(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();co=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',co);ev.to_mesh_clear();return co.reshape(-1,3)
for frame in (270,330):
    scene.frame_set(frame);bpy.context.view_layer.update();co=points(body);center=Vector(tuple((co.min(axis=0)+co.max(axis=0))*.5))+Vector((0,0,.17));cam.location=center+Vector((.1,-1,.025)).normalized()*4;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();row={};baseline=None
    for mode in ('delivered','bone_only','cloth_no_guards'):
        for m,(v,r) in state.items():m.show_viewport=v;m.show_render=r
        if mode=='bone_only':follow.show_viewport=False;follow.show_render=False
        if mode=='cloth_no_guards':
            for m in guards:m.show_viewport=False;m.show_render=False
        bpy.context.view_layer.update();coords=points(cloth)
        if baseline is None:baseline=coords.copy()
        assert len(coords)==len(baseline)
        delta=np.linalg.norm(coords-baseline,axis=1);row[mode]={'vertices':len(coords),'max_delta_from_delivered_m':float(delta.max()),'p99_delta_from_delivered_m':float(np.quantile(delta,.99))}
        scene.render.filepath=str(out/f'{frame}_{mode}.png');bpy.ops.render.render(write_still=True)
    result['comparisons'][str(frame)]=row
for m,(v,r) in state.items():m.show_viewport=v;m.show_render=r
scene.frame_set(1);p=proxy.vertex_groups[sim.settings.vertex_group_mass].index;vf={}
for f in proxy.data.polygons:
    for i in f.vertices:vf.setdefault(i,[]).append(f.index)
left=set(range(len(proxy.data.polygons)));islands=[]
while left:
    todo=[left.pop()];ids=set();fs=[]
    while todo:
        fi=todo.pop();fs.append(fi)
        for i in proxy.data.polygons[fi].vertices:
            ids.add(i)
            for j in vf[i]:
                if j in left:left.remove(j);todo.append(j)
    weights=[sum(g.weight for g in proxy.data.vertices[i].groups if g.group==p) for i in ids];pts=[proxy.data.vertices[i].co for i in ids]
    islands.append({'vertices':len(ids),'faces':len(fs),'fully_pinned':sum(w>.999 for w in weights),'partially_pinned':sum(0<w<=.999 for w in weights),'rest_z':[min(v.z for v in pts),max(v.z for v in pts)]})
result['proxy_islands']=islands;result['solver']={k:getattr(sim.settings,k) for k in ('quality','bending_stiffness','tension_stiffness','use_dynamic_mesh','pin_stiffness')};result['cache_still_baked']=sim.point_cache.is_baked
(out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('WRINKLE_COMPARISON_COMPLETE',json.dumps(result,ensure_ascii=False),flush=True)
