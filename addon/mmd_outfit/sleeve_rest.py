"""Make a simulated sleeve drape the new editable rest shape.

Mesh, relative morphs, sleeve bones, rigid bodies and joint anchors move
together. The experimental free cuff particles can be removed in favour of
an upper-arm attachment; original hanging sleeve chains remain dynamic.
"""
import bpy
from mathutils import Matrix,Vector


def apply(cloth,arm,settled,components,remove_free_cuff=True):
    matrices={name:Matrix(value)@arm.data.bones[name].matrix_local.inverted() for name,value in settled['bones'].items()}
    ids={i for p in components for i in p['vertices']};names={g.index:g.name for g in cloth.vertex_groups}
    # Small tassels and metal ornaments are disconnected mesh islands too.
    # Every vertex driven by a rebased sleeve bone must move with that rest.
    ids.update(v.index for v in cloth.data.vertices if any(names[g.group] in matrices and g.weight>1e-7 for g in v.groups))
    transforms={}
    identity=Matrix.Identity(4)
    for i in ids:
        weights=[(names[g.group],g.weight) for g in cloth.data.vertices[i].groups if not names[g.group].startswith('mmd_') and g.weight>1e-7]
        total=sum(w for n,w in weights);matrix=Matrix(((0,0,0,0),)*4)
        for name,w in weights:matrix+=matrices.get(name,identity)*(w/total)
        transforms[i]=matrix
    maximum=0.
    normal_values=[(transforms[loop.vertex_index].to_3x3().inverted().transposed()@normal.vector).normalized() if loop.vertex_index in transforms else normal.vector.copy() for loop,normal in zip(cloth.data.loops,cloth.data.corner_normals)] if cloth.data.has_custom_normals else None
    for i,matrix in transforms.items():
        old=cloth.data.vertices[i].co.copy();cloth.data.vertices[i].co=matrix@old;maximum=max(maximum,(matrix@old-old).length)
    if cloth.data.shape_keys:
        for key in cloth.data.shape_keys.key_blocks:
            for i,matrix in transforms.items():key.data[i].co=matrix@key.data[i].co
    if normal_values:cloth.data.normals_split_custom_set(normal_values)
    removed_bones={n for n in matrices if n.startswith('袖環')} if remove_free_cuff else set()
    # Ring nodes have no anatomical target. Reattach their mass to the upper arm.
    for i in ids:
        transferred={}
        for g in list(cloth.data.vertices[i].groups):
            name=names[g.group]
            if name in removed_bones:
                side=name[-1];transferred[side]=transferred.get(side,0.)+g.weight;cloth.vertex_groups[name].remove([i])
        for side,w in transferred.items():
            group=cloth.vertex_groups['腕.'+side];old=next((g.weight for g in cloth.data.vertices[i].groups if g.group==group.index),0.);group.add([i],old+w,'REPLACE')
    rigids=[o for o in bpy.data.objects if getattr(o,'mmd_type','')=='RIGID_BODY'];removed_rigids={o for o in rigids if o.mmd_rigid.bone in removed_bones}
    remove=[];moved_rigids=0;moved_joints=0
    for o in bpy.data.objects:
        typ=getattr(o,'mmd_type','')
        if typ=='RIGID_BODY' and o not in removed_rigids and o.mmd_rigid.bone in matrices:
            o.matrix_world=arm.matrix_world@matrices[o.mmd_rigid.bone]@arm.matrix_world.inverted()@o.matrix_world;moved_rigids+=1
        if typ=='JOINT':
            c=o.rigid_body_constraint
            if c.object1 in removed_rigids or c.object2 in removed_rigids:remove.append(o);continue
            target=next((r for r in (c.object2,c.object1) if r and r.mmd_rigid.bone in matrices),None)
            if target:o.matrix_world=arm.matrix_world@matrices[target.mmd_rigid.bone]@arm.matrix_world.inverted()@o.matrix_world;moved_joints+=1
    for o in remove+list(removed_rigids):bpy.data.objects.remove(o,do_unlink=True)
    arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT')
    for name,value in settled['bones'].items():
        if name in removed_bones:continue
        b=arm.data.edit_bones[name];length=b.length;b.matrix=Matrix(value);b.length=length
    for name in removed_bones:arm.data.edit_bones.remove(arm.data.edit_bones[name])
    bpy.ops.object.mode_set(mode='OBJECT')
    for name in removed_bones:
        if name in cloth.vertex_groups:cloth.vertex_groups.remove(cloth.vertex_groups[name])
    bpy.context.view_layer.update()
    return {'method':'simulated_drape_as_rest','vertices':len(ids),'max_drape_displacement_m':maximum,'original_sleeve_chains_retained':True,'removed_free_cuff_bones':len(removed_bones),'removed_free_cuff_rigids':len(removed_rigids),'removed_free_cuff_joints':len(remove),'updated_rigids':moved_rigids,'updated_joints':moved_joints}
