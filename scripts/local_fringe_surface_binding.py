"""Scope Blender's already-bound Surface Deform to the left fringe only."""
import bpy

CHAIN = 'FrontHair5-1.L'
BONES = ('FrontHair5-1.L', 'FrontHair5-2.L', 'FrontHair5-3.L')


def configure(actor):
    arm = actor.find_armature()
    tracks = [c for name in BONES for c in arm.pose.bones[name].constraints
              if c.name.startswith('ClassicCloth_跟踪代理_')]
    assert len(tracks) == 3
    for con in tracks:
        con.influence = 0.0
    modifiers = [m for m in actor.modifiers
                 if m.type == 'SURFACE_DEFORM' and m.name.startswith('Native_SurfaceDeform_')]
    assert len(modifiers) == 27
    selected = next(m for m in modifiers if m.name == 'Native_SurfaceDeform_' + CHAIN)
    assert selected.is_bound and selected.target.name == 'ClassicHair_' + CHAIN
    for m in modifiers:
        m.show_viewport = m == selected
        m.show_render = m == selected
    bpy.context.view_layer.update()
    return dict(chain=CHAIN, inactive_tracking_bones=list(BONES),
                modifier=selected.name, target=selected.target.name,
                method='Native Surface Deform only on left fringe; other 141 Damped Track bindings unchanged',
                original_weights_edited=False, per_frame_corrective_motion=False)
