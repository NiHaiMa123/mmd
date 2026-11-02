import bpy, json
from pathlib import Path
rig=bpy.data.objects.get('东雪莲x达妮娅_骨架')
mesh=bpy.data.objects.get('东雪莲x达妮娅_素体')
data={'file':bpy.data.filepath,'frame':bpy.context.scene.frame_current,
 'objects':len(bpy.data.objects),'camera':bpy.context.scene.camera.name if bpy.context.scene.camera else None,
 'modifiers':[{'name':m.name,'type':m.type,'viewport':m.show_viewport,'render':m.show_render,
 'vertex_group':getattr(m,'vertex_group',None),'filepath':getattr(m,'filepath',None),'object':getattr(getattr(m,'object',None),'name',None)} for m in mesh.modifiers],
 'nla':[{'name':t.name,'mute':t.mute,'strips':[{'name':s.name,'action':s.action.name if s.action else None} for s in t.strips]} for t in rig.animation_data.nla_tracks],
 'action':rig.animation_data.action.name if rig.animation_data.action else None,
 'bones':[{'name':b.name,'parent':b.parent.name if b.parent else None,'deform':b.bone.use_deform,'head':list(b.bone.head_local),'tail':list(b.bone.tail_local),
 'constraints':[{'type':c.type,'name':c.name,'mute':c.mute,'influence':c.influence} for c in b.constraints]} for b in rig.pose.bones],
 'mesh_matrix':[list(r) for r in mesh.matrix_world],'rig_matrix':[list(r) for r in rig.matrix_world],
 'attributes':[{'name':a.name,'domain':a.domain,'type':a.data_type} for a in mesh.data.attributes],
 'drivers':len(rig.animation_data.drivers),'actions':[{'name':a.name,'frame_range':list(a.frame_range)} for a in bpy.data.actions]}
out=Path(r'E:\project\mmd\work\headswap_xl_codex\jiggle_physics_20261031');out.mkdir(exist_ok=True)
(out/'source_inventory.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in data.items() if k not in ['bones','actions']},ensure_ascii=False))
