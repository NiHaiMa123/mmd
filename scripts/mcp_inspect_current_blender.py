import json,bpy
scene=bpy.context.scene
spring=bpy.types.RigidBodyConstraint.bl_rna.properties.get('spring_type')
print(json.dumps(dict(filepath=bpy.data.filepath,dirty=bpy.data.is_dirty,saved=bpy.data.is_saved,scene=scene.name,objects=[dict(name=o.name,type=o.type) for o in scene.objects][:20],spring_types=[(x.identifier,x.description) for x in spring.enum_items] if spring else None),ensure_ascii=False))
