"""Read-only inspection of the unmodified author's Blender file."""
import argparse,json,sys,collections
from pathlib import Path
import bpy
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
def idname(v):return v.name if hasattr(v,'name') else v
def props(obj,keys):
 result={}
 for key in keys:
  try:
   value=getattr(obj,key)
   if hasattr(value,'name'):value=value.name
   elif not isinstance(value,(str,int,float,bool,type(None))):value=list(value)
   result[key]=value
  except (AttributeError,TypeError):pass
 return result
objects=[];arms=[]
for obj in bpy.data.objects:
 mods=[]
 for m in obj.modifiers:
  row=dict(name=m.name,type=m.type,show_viewport=m.show_viewport,show_render=m.show_render)
  row.update(props(m,['object','object_path','filepath','vertex_group','node_group','strength','factor','precision']))
  if m.type=='MESH_SEQUENCE_CACHE':row.update(props(m,['cache_file','read_data','use_vertex_interpolation','override_frame','frame','velocity_scale']))
  if m.type=='MESH_CACHE':row.update(props(m,['cache_format','filepath','frame_start','frame_scale','play_mode','deform_mode']))
  if m.type=='CLOTH':row['settings']=props(m.settings,['quality','mass','air_damping','tension_stiffness','compression_stiffness','shear_stiffness','bending_stiffness','vertex_group_mass','use_pin_cloth']);row['collision']=props(m.collision_settings,['use_collision','use_self_collision','distance_min','self_distance_min','collision_quality']);row['point_cache']=props(m.point_cache,['is_baked','is_outdated','frame_start','frame_end','use_disk_cache','filepath'])
  if m.type=='SOFT_BODY':row['settings']=props(m.settings,['mass','goal_default','goal_spring','use_goal','use_edges','pull','push','bend','use_self_collision']);row['point_cache']=props(m.point_cache,['is_baked','frame_start','frame_end','use_disk_cache','filepath'])
  mods.append(row)
 row=dict(name=obj.name,type=obj.type,parent=idname(obj.parent),parent_bone=obj.parent_bone,hide_render=obj.hide_render,modifiers=mods,constraints=[dict(name=c.name,type=c.type,**props(c,['target','subtarget','mute','influence'])) for c in obj.constraints],animation=props(obj.animation_data,['action']) if obj.animation_data else None)
 if obj.type=='MESH':row.update(vertices=len(obj.data.vertices),polygons=len(obj.data.polygons),shape_keys=len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0,materials=[idname(m.material) for m in obj.material_slots])
 if obj.rigid_body:row['rigid_body']=props(obj.rigid_body,['type','kinematic','mass','collision_shape','collision_margin','use_margin','linear_damping','angular_damping'])
 if obj.rigid_body_constraint:row['rigid_body_constraint']=props(obj.rigid_body_constraint,['type','object1','object2','enabled','disable_collisions','spring_type'])
 objects.append(row)
 if obj.type=='ARMATURE':
  bones=[dict(name=b.name,parent=idname(b.parent),constraints=[dict(name=c.name,type=c.type,**props(c,['target','subtarget','mute','influence','head_tail','use_bbone_shape'])) for c in b.constraints]) for b in obj.pose.bones]
  arms.append(dict(name=obj.name,bones=bones))
actions=[]
for action in bpy.data.actions:
 curves=[]
 for layer in action.layers:
  for strip in layer.strips:
   for bag in getattr(strip,'channelbags',[]):curves+=list(bag.fcurves)
 try:curves+=list(action.fcurves)
 except AttributeError:pass
 seen=set();curves=[c for c in curves if not(c.as_pointer() in seen or seen.add(c.as_pointer()))]
 paths=collections.Counter(c.data_path.split('].')[0]+']' if c.data_path.startswith('pose.bones[') else c.data_path for c in curves)
 actions.append(dict(name=action.name,frame_range=list(action.frame_range),fcurves=len(curves),keys=sum(len(c.keyframe_points) for c in curves),channels=dict(paths)))
scenes=[]
for s in bpy.data.scenes:
 w=s.rigidbody_world;scenes.append(dict(name=s.name,frame_start=s.frame_start,frame_end=s.frame_end,fps=s.render.fps,gravity=list(s.gravity),rigidbody_world=props(w,['enabled','collection','constraints','substeps_per_frame','solver_iterations','time_scale']) if w else None))
caches=[dict(name=c.name,**props(c,['filepath','is_sequence','frame','frame_offset','override_frame','scale','object_paths'])) for c in bpy.data.cache_files]
report=dict(source=a.source,blender_version=bpy.app.version_string,scenes=scenes,objects=objects,armatures=arms,actions=actions,cache_files=caches,text_blocks=[dict(name=t.name,body=t.as_string()) for t in bpy.data.texts],node_groups=[dict(name=g.name,nodes=[n.bl_idname for n in g.nodes]) for g in bpy.data.node_groups if any('Simulation' in n.bl_idname for n in g.nodes)])
(out/'author_physics_inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),'utf8');print('ORIGINAL_AUTHOR_PHYSICS_INVENTORY_COMPLETE',len(objects),len(arms),len(actions),len(caches),flush=True)
