"""A small UI over the same job API used by automation clients."""
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty

from . import jobs

_job = None
_scene_name = None


class MMDOUTFIT_Settings(bpy.types.PropertyGroup):
    source: StringProperty(name="来源角色 PMX", subtype="FILE_PATH")
    target: StringProperty(name="目标素体 PMX", subtype="FILE_PATH")
    profile: StringProperty(name="换衣配置 JSON", subtype="FILE_PATH")
    model: StringProperty(name="待检查 PMX", subtype="FILE_PATH")
    motion: StringProperty(name="测试动作 VMD（可选）", subtype="FILE_PATH")
    output: StringProperty(name="输出目录", subtype="DIR_PATH", default="//outfit_jobs")
    preset: EnumProperty(name="适配预设", items=[
        ("conservative", "通用保守配置", "不使用刻晴专用材质规则"),
        ("keqing_daniya", "刻晴 → 达妮娅（实验）", "复用已有袜层适配，需检查效果")])
    render: BoolProperty(name="生成四视角预览", default=True)
    ground_motion: BoolProperty(name='另存鞋底接地动作',default=False,
        description='保持鞋形和腿姿，为平地动作另存高度修正副本；需要测试动作与闭口鞋模式')
    cuff_physics: BoolProperty(name='生成袖口物理（试验）',default=False,
        description='仅刻晴预设：生成环形碰撞节点与过渡权重；需开启物理求解并复查，不保证消除穿模')
    timeout: IntProperty(name="超时（秒）", default=1800, min=1, max=86400)
    status: StringProperty(name="状态", default="尚未运行")
    job_dir: StringProperty(name="任务目录", subtype="DIR_PATH")
    result_blend: StringProperty(subtype="FILE_PATH")


def _refresh():
    global _job
    if _job is None:
        return None
    state = _job.poll()
    scene = bpy.data.scenes.get(_scene_name)
    if scene:
        props = scene.mmd_outfit
        props.status = f"{state.get('state')}: {state.get('stage', '')}"
    if state.get("state") in jobs.TERMINAL:
        if scene:
            props.status = state["state"]
            if state.get("profile"):
                props.profile = state["profile"]
            if state.get("pmx"):
                props.model = state["pmx"]
            if state.get("blend"):
                props.result_blend = state["blend"]
            if state.get("error"):
                props.status += ": " + state["error"]["message"]
        _job = None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    return 0.5 if _job is not None else None


class MMDOUTFIT_OT_submit(bpy.types.Operator):
    bl_idname = "mmd_outfit.submit"
    bl_label = "运行换衣任务"
    action: EnumProperty(items=[("inspect", "预检并生成配置", ""),
                               ("fit", "按配置换衣", ""),
                               ("validate", "检查成品", "")])

    @classmethod
    def poll(cls, context):
        return _job is None

    def execute(self, context):
        global _job, _scene_name
        props = context.scene.mmd_outfit
        request = {"action": self.action, "output_root": bpy.path.abspath(props.output),
                   "timeout": props.timeout, "render": props.render}
        if self.action == "inspect":
            request.update(source=bpy.path.abspath(props.source), target=bpy.path.abspath(props.target),
                           preset=props.preset)
        elif self.action == "fit":
            request["profile"] = bpy.path.abspath(props.profile)
            request['ground_motion']=props.ground_motion
            request['cuff_physics']=props.cuff_physics
        else:
            request["model"] = bpy.path.abspath(props.model)
            if props.profile:
                request["profile"] = bpy.path.abspath(props.profile)
        if props.motion and self.action != "inspect":
            request["motion"] = bpy.path.abspath(props.motion)
        try:
            _job = jobs.submit(request, bpy.app.binary_path)
        except Exception as exc:
            props.status = str(exc)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _scene_name = context.scene.name
        props.job_dir = str(_job.directory)
        props.status = "RUNNING: starting"
        bpy.app.timers.register(_refresh, first_interval=0.5)
        return {"FINISHED"}


class MMDOUTFIT_OT_cancel(bpy.types.Operator):
    bl_idname = "mmd_outfit.cancel"
    bl_label = "取消当前任务"

    def execute(self, context):
        if _job is not None:
            _job.cancel()
        return {"FINISHED"}


class MMDOUTFIT_OT_folder(bpy.types.Operator):
    bl_idname = "mmd_outfit.folder"
    bl_label = "打开任务目录"

    def execute(self, context):
        path = context.scene.mmd_outfit.job_dir
        if not path or not Path(path).is_dir():
            return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=path)
        return {"FINISHED"}


class MMDOUTFIT_PT_panel(bpy.types.Panel):
    bl_label = "MMD 换衣 · 0.9 实验版"
    bl_idname = "MMDOUTFIT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MMD 换衣"

    def draw(self, context):
        layout = self.layout
        props = context.scene.mmd_outfit
        column = layout.column()
        column.enabled = _job is None
        column.prop(props, "source")
        column.prop(props, "target")
        column.prop(props, "preset")
        column.prop(props, "output")
        column.operator("mmd_outfit.submit", text="1. 预检并生成配置").action = "inspect"
        column.separator()
        column.prop(props, "profile")
        column.prop(props, "motion")
        column.prop(props,'ground_motion')
        column.prop(props,'cuff_physics')
        column.prop(props, "render")
        column.prop(props, "timeout")
        column.operator("mmd_outfit.submit", text="2. 按配置换衣").action = "fit"
        column.separator()
        column.prop(props, "model")
        column.operator("mmd_outfit.submit", text="3. 检查成品").action = "validate"
        layout.separator()
        layout.label(text="在独立后台进程运行，保留当前工程", icon="INFO")
        layout.label(text="适配后需要检查手、脚、袖口与裙摆")
        layout.label(text=props.status[:90])
        if _job is not None:
            layout.operator("mmd_outfit.cancel")
        if props.job_dir:
            layout.operator("mmd_outfit.folder")


_classes = (MMDOUTFIT_Settings, MMDOUTFIT_OT_submit, MMDOUTFIT_OT_cancel,
            MMDOUTFIT_OT_folder, MMDOUTFIT_PT_panel)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mmd_outfit = PointerProperty(type=MMDOUTFIT_Settings)


def unregister():
    global _job
    if _job is not None:
        _job.cancel()
        _job = None
    if bpy.app.timers.is_registered(_refresh):
        bpy.app.timers.unregister(_refresh)
    del bpy.types.Scene.mmd_outfit
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
