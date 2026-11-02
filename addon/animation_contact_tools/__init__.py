# SPDX-License-Identifier: GPL-3.0-or-later
"""Transferable evaluated-surface contact tools for Blender armatures."""
bl_info={'name':'Animation Contact Tools / 动画穿模工具','author':'MMD project','version':(0,1,6),
 'blender':(4,2,0),'location':'View3D > Sidebar > 动画接触','category':'Animation',
 'description':'Profile-based surface audit and ordinary arm-contact correction; bilateral gestures protected'}

def register():
    from . import ui
    ui.register()

def unregister():
    from . import ui
    ui.unregister()
