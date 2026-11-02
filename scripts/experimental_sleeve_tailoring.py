"""Probe smooth, arm-axis sleeve tailoring on copies only (not release code)."""
from mathutils import Vector


def fit(cloth, arm, components, apply_positions, *, radial_scale=1.7, axial_scale=.78):
    import bpy
    original=[cloth.matrix_world@v.co for v in cloth.data.vertices]
    points=[p.copy() for p in original]
    warps={};report=[]
    for side in ('L','R'):
        ids=set(i for row in components if row['side']==side for i in row['vertices'])
        a=arm.matrix_world@arm.data.bones['腕.'+side].head_local
        b=arm.matrix_world@arm.data.bones['ひじ.'+side].head_local
        axis=(b-a).normalized()
        def warp(p,a=a.copy(),axis=axis.copy()):
            t=(p-a).dot(axis);radial=p-a-axis*t
            blend=min(1.,max(0.,(.22-radial.length)/.10))
            blend=blend*blend*(3-2*blend)
            return a+axis*t*axial_scale+radial*(1+(radial_scale-1)*blend)
        warps[side]=warp
        for i in ids:points[i]=warp(original[i])
        report.append({'side':side,'vertices':len(ids),'radial_scale':radial_scale,'axial_scale':axial_scale,
                       'max_displacement_m':max((points[i]-original[i]).length for i in ids)})
    inverse=cloth.matrix_world.inverted()
    apply_positions(cloth.data,[inverse@p for p in points])
    # Keep the cloth chain rest anchors in the same tailored sleeve space.
    bpy.context.view_layer.objects.active=arm;arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        for bone in arm.data.edit_bones:
            if bone.name.startswith('袖_') and bone.name.endswith(('.L','.R')):
                warp=warps[bone.name[-1]]
                bone.head=arm.matrix_world.inverted()@warp(arm.matrix_world@bone.head)
                bone.tail=arm.matrix_world.inverted()@warp(arm.matrix_world@bone.tail)
    finally:bpy.ops.object.mode_set(mode='OBJECT')
    return {'method':'experimental_axis_tailoring','sides':report,'scope':'not approved; copied model and pose review only'}
