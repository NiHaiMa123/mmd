import bpy,json
mesh=bpy.data.meshes.new('OnlyAPIProbe_ClothPin');mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
obj=bpy.data.objects.new('OnlyAPIProbe_ClothPin',mesh);bpy.context.scene.collection.objects.link(obj)
mod=obj.modifiers.new('APIProbe','CLOTH');mod.settings.vertex_group_mass='MissingYet'
before=mod.settings.vertex_group_mass;vg=obj.vertex_groups.new(name='MissingYet');after=mod.settings.vertex_group_mass
mod.settings.vertex_group_mass=vg.name;fixed=mod.settings.vertex_group_mass
print(json.dumps(dict(before_group_creation=before,after_group_creation=after,after_assignment=fixed)))
bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
