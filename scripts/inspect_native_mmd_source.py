import argparse,sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
mmd_tools=next(module for name,module in sys.modules.items() if name=='mmd_tools' or name.endswith('.mmd_tools'))
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
def simple(value):
    if isinstance(value,(str,float,int,bool)) or value is None:return value
    try:return list(value)
    except:return str(value)
rigids=[];joints=[];roots=[];arms=[]
for o in bpy.data.objects:
    kind=getattr(o,'mmd_type','')
    if kind=='ROOT':roots.append(dict(name=o.name,built=o.mmd_root.is_built))
    if kind=='RIGID_BODY':
        r=o.mmd_rigid
        rigids.append(dict(name=o.name,bone=r.bone,type=str(r.type),shape=r.shape,size=list(r.size),world=[list(x) for x in o.matrix_world],mass=o.rigid_body.mass if o.rigid_body else None,parent=o.parent.name if o.parent else None))
    if kind=='JOINT':
        c=o.rigid_body_constraint
        row=dict(name=o.name,object1=c.object1.name if c and c.object1 else None,object2=c.object2.name if c and c.object2 else None)
        if c:row.update({x.identifier:simple(getattr(c,x.identifier)) for x in c.bl_rna.properties if x.identifier.startswith(('limit_','spring_','use_limit_','use_spring_'))})
        joints.append(row)
    if o.type=='ARMATURE':arms.append(dict(name=o.name,bones=len(o.data.bones),world=[list(x) for x in o.matrix_world],constraints={b.name:[dict(name=c.name,type=c.type) for c in b.constraints] for b in o.pose.bones if b.constraints}))
ops={}
for name in ['export_pmx','export_vmd','import_vmd']:
    op=getattr(bpy.ops.mmd_tools,name)
    ops[name]=[dict(id=x.identifier,type=x.type,default=simple(getattr(x,'default',None)),description=x.description) for x in op.get_rna_type().properties]
pose_scale={o.name:{b.name:list(b.scale) for b in o.pose.bones if max(abs(v-1) for v in b.scale)>1e-5} for o in bpy.data.objects if o.type=='ARMATURE'}
report=dict(pose_scale=pose_scale,module=mmd_tools.__file__,version=getattr(mmd_tools,'bl_info',{}),source=a.source,roots=roots,arms=arms,rigids=rigids,joints=joints,operators=ops)
out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print('NATIVE_MMD_SOURCE',len(rigids),'rigids',len(joints),'joints',roots,'MODULE',mmd_tools.__file__,flush=True)
