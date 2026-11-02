import bpy,json,sys,argparse,collections
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
def value(v):
 if isinstance(v,bpy.types.ID):return dict(id_type=type(v).__name__,name=v.name)
 if isinstance(v,(str,int,float,bool,type(None))):return v
 try:return list(v)
 except TypeError:return str(v)
mods=[]
def custom(m):
 try:return {k:value(m[k]) for k in m.keys()}
 except TypeError:return {}
for obj in bpy.data.objects:
 for m in obj.modifiers:
  if m.type=='NODES':mods.append(dict(object=obj.name,group=m.node_group.name if m.node_group else None,enabled=m.show_viewport,render=m.show_render,inputs=custom(m),bakes=[dict(id=getattr(b,'bake_id',None),**{k:value(getattr(b,k)) for k in ['directory','frame_start','frame_end','bake_mode','bake_target'] if hasattr(b,k)}) for b in getattr(m,'bakes',[])]))
  if m.type in ['SURFACE_DEFORM','SHRINKWRAP','ARMATURE']:mods.append(dict(object=obj.name,type=m.type,target=m.object.name if m.type=='ARMATURE' and m.object else m.target.name if hasattr(m,'target') and m.target else None,vertex_group=getattr(m,'vertex_group',None),bound=getattr(m,'is_bound',None)))
groups=[]
for g in bpy.data.node_groups:
 nodes=[]
 for n in g.nodes:
  row=dict(name=n.name,label=n.label,type=n.bl_idname)
  if hasattr(n,'node_tree') and n.node_tree:row['group']=n.node_tree.name
  if any(w in n.bl_idname for w in ['ObjectInfo','CollectionInfo','NamedAttribute']):row['inputs']={i.name:value(i.default_value) for i in n.inputs if hasattr(i,'default_value')}
  nodes.append(row)
 groups.append(dict(name=g.name,users=g.users,asset=dict(author=g.asset_data.author,description=g.asset_data.description) if g.asset_data else None,nodes=nodes))
rigs=[]
for obj in bpy.data.objects:
 if obj.type!='ARMATURE':continue
 bones=[dict(name=b.name,parent=b.parent.name if b.parent else None,constraints=[dict(name=c.name,type=c.type,target=getattr(getattr(c,'target',None),'name',None),subtarget=getattr(c,'subtarget',None),influence=c.influence,mute=c.mute,properties={p.identifier:value(getattr(c,p.identifier)) for p in c.bl_rna.properties if c.type=='GEOMETRY_ATTRIBUTE' and p.identifier not in ['rna_type']}) for c in b.constraints]) for b in obj.pose.bones]
 ad=obj.animation_data;rigs.append(dict(name=obj.name,action=getattr(getattr(ad,'action',None),'name',None),nla=[dict(name=t.name,mute=t.mute,strips=[dict(name=s.name,action=s.action.name if s.action else None,frame_start=s.frame_start,frame_end=s.frame_end,influence=s.influence) for s in t.strips]) for t in ad.nla_tracks] if ad else [],bones=bones))
report=dict(modifiers=mods,groups=groups,rigs=rigs);(out/'author_physics_links.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),'utf8');print('AUTHOR_PHYSICS_LINKS_COMPLETE',flush=True)
