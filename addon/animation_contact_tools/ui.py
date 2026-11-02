import json,subprocess,os
from datetime import datetime
from pathlib import Path
import bpy,bmesh
from bpy.props import StringProperty,PointerProperty,IntProperty,EnumProperty
from .surface import mmd_profile,regions,audit_frame

class ACT_Settings(bpy.types.PropertyGroup):
    mesh:PointerProperty(name='角色网格',type=bpy.types.Object,poll=lambda self,o:o.type=='MESH')
    profile:StringProperty(name='骨架／接触配置',subtype='FILE_PATH')
    output:StringProperty(name='输出目录',subtype='DIR_PATH',default='//contact_jobs')
    first:IntProperty(name='起始帧',default=1);last:IntProperty(name='结束帧',default=450)
    step:IntProperty(name='检测步长',default=5,min=1)
    surface:EnumProperty(name='选中面的类型',items=[('1','身体',''),('2','头部皮肤',''),('3','实际头发',''),('0','忽略视觉层','')])
    status:StringProperty(name='状态',default='请设置网格和配置；当前身体求解器仅处理普通手臂接触')
    last_job:StringProperty(name='最近任务目录')

def resolve(context):
    s=context.scene.animation_contact;o=s.mesh or context.active_object
    if not o or o.type!='MESH':raise ValueError('选择角色网格')
    arm=next((m.object for m in o.modifiers if m.type=='ARMATURE' and m.object),None)
    if arm is None:raise ValueError('网格必须绑定骨架')
    if s.profile:profile=json.loads(Path(bpy.path.abspath(s.profile)).read_text('utf8'))
    else:
        if not hasattr(arm.pose.bones[0],'mmd_bone'):raise ValueError('非 MMD 骨架请提供明确的骨骼角色 JSON 配置')
        profile=mmd_profile(o,arm)
    profile['mesh']=o.name;profile['armature']=arm.name
    return s,o,arm,profile

class ACT_OT_mark(bpy.types.Operator):
    bl_idname='animation_contact.mark_surface';bl_label='标记选中面的表面类型';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return context.active_object and context.active_object.type=='MESH' and context.mode=='EDIT_MESH'
    def execute(self,context):
        o=context.active_object;bm=bmesh.from_edit_mesh(o.data);layer=bm.faces.layers.int.get('SurfaceClass') or bm.faces.layers.int.new('SurfaceClass')
        for f in bm.faces:
            if f.select:f[layer]=int(context.scene.animation_contact.surface)
        bmesh.update_edit_mesh(o.data);return {'FINISHED'}

class ACT_OT_profile(bpy.types.Operator):
    bl_idname='animation_contact.export_profile';bl_label='导出骨架配置（MMD 初始映射）'
    def execute(self,context):
        try:
            s,o,arm,p=resolve(context);out=Path(bpy.path.abspath(s.output));out.mkdir(parents=True,exist_ok=True);path=out/'rig_profile.json'
            aliases={getattr(getattr(b,'mmd_bone',None),'name_j','') or b.name:b.name for b in arm.pose.bones}
            p['control_chains']=[[aliases[n] for n in ('左腕','左ひじ','左手首')],[aliases[n] for n in ('右腕','右ひじ','右手首')]]
            path.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8');s.profile=str(path);s.status='已导出配置；请填写 protected_windows 后再修正'
            return {'FINISHED'}
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}

class ACT_OT_audit(bpy.types.Operator):
    bl_idname='animation_contact.audit_current';bl_label='检测当前帧（实际表面）'
    def execute(self,context):
        try:
            s,o,arm,p=resolve(context);parts=regions(o,arm,p);r=audit_frame(o,arm,p,parts)
            out=Path(bpy.path.abspath(s.output));out.mkdir(parents=True,exist_ok=True);(out/'current_frame.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
            s.status=f"普通交线 {r['ordinary_crossings']}；闭合面内部点 {r['ordinary_contained_samples']}；延后接触 {r['deferred_crossings']}；未映射面 {parts['missing_body_mapping']}"
            return {'FINISHED'}
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}

class ACT_OT_job(bpy.types.Operator):
    bl_idname='animation_contact.background_job';bl_label='在副本上运行';mode:EnumProperty(items=[('audit','全段检测',''),('solve','修正普通手臂接触','')])
    def execute(self,context):
        try:
            s,o,arm,p=resolve(context);out=Path(bpy.path.abspath(s.output))/datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True,exist_ok=False);s.last_job=str(out)
            if self.mode=='solve' and not p.get('control_chains'):raise ValueError('配置缺少 control_chains；先配置实际控制骨，不自动猜测任意骨架')
            (out/'job_profile.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
            snapshot=out/'input_snapshot.blend';bpy.ops.wm.save_as_mainfile(filepath=str(snapshot),copy=True,compress=True)
            command=[bpy.app.binary_path,'-b','--python-exit-code','1','--python',str(Path(__file__).with_name('worker.py')),'--','--source',str(snapshot),'--profile',str(out/'job_profile.json'),'--out',str(out),'--mode',self.mode,'--first',str(s.first),'--last',str(s.last),'--step',str(s.step)]
            with (out/'worker.log').open('w',encoding='utf8') as log:proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            s.status=f'后台任务 {proc.pid}；输出 {out}';return {'FINISHED'}
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}

class ACT_OT_status(bpy.types.Operator):
    bl_idname='animation_contact.job_status';bl_label='读取任务状态'
    def execute(self,context):
        s=context.scene.animation_contact;p=Path(s.last_job or bpy.path.abspath(s.output))/'job_status.json'
        s.status=p.read_text('utf8')[:220] if p.exists() else '尚无任务回执；可检查 worker.log';return {'FINISHED'}

class ACT_PT_panel(bpy.types.Panel):
    bl_label='动画接触 / 穿模';bl_idname='ACT_PT_panel';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='动画接触'
    def draw(self,context):
        s=context.scene.animation_contact;l=self.layout;l.prop(s,'mesh');l.prop(s,'profile');l.prop(s,'output')
        l.prop(s,'surface');l.operator('animation_contact.mark_surface');l.operator('animation_contact.export_profile')
        l.operator('animation_contact.audit_current');r=l.row(align=True);r.prop(s,'first');r.prop(s,'last');l.prop(s,'step')
        l.operator('animation_contact.background_job',text='后台全段检测').mode='audit'
        l.operator('animation_contact.background_job',text='后台普通手臂修正（实验）').mode='solve'
        l.operator('animation_contact.job_status');l.label(text=s.status[:85]);l.label(text='双手交叠须设置保护窗口；头发后端单独验收')

CLASSES=[ACT_Settings,ACT_OT_mark,ACT_OT_profile,ACT_OT_audit,ACT_OT_job,ACT_OT_status,ACT_PT_panel]
def register():
    for c in CLASSES:bpy.utils.register_class(c)
    bpy.types.Scene.animation_contact=PointerProperty(type=ACT_Settings)
def unregister():
    del bpy.types.Scene.animation_contact
    for c in reversed(CLASSES):bpy.utils.unregister_class(c)
