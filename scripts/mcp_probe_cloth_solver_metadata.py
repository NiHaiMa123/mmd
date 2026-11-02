"""Read-only RNA metadata; do not touch the user's open scene."""
import bpy,json
names=['ClothSolverResult','ClothSettings']
print(json.dumps({name:[dict(name=p.identifier,type=p.type) for p in getattr(bpy.types,name).bl_rna.properties]
    for name in names},ensure_ascii=False))
