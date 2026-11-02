"""MMD Outfit Bridge. Importing the automation API does not require bpy."""

bl_info = {
    "name": "MMD Outfit Bridge / MMD 换衣",
    "author": "MMD project",
    "version": (0, 9, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > MMD 换衣",
    "description": "Profile-based, isolated PMX clothing transfer with reports",
    "category": "Object",
}


def register():
    from . import ui
    ui.register()


def unregister():
    from . import ui
    ui.unregister()
