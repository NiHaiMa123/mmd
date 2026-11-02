"""Install a frame-specific, non-destructive garment contact correction."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,HAND_PREFIX
from mmd_outfit.outfit_surface_contact import fit_surface
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--frame',type=int,default=325);p.add_argument('--iterations',type=int,default=35);p.add_argument('--solver',choices=['projection','arap'],default='arap');p.add_argument('--collider');p.add_argument('--objects',nargs='+',default=['Cloth','SleeveLining','Stockings']);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];cloth=bpy.data.objects['Cloth'];scene.frame_set(a.frame)
# SIMPLE subdivision adds no shape here; fit the original garment topology,
# then keep its existing subdivision after the correction.
sub=next(m for m in cloth.modifiers if m.type=='SUBSURF');sub.show_viewport=False;sub.show_render=False
def capture(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles],dtype=np.int32);groups=[[ (g.group,g.weight) for g in v.groups] for v in mesh.vertices];ev.to_mesh_clear();matrix=np.array(obj.matrix_world);return co@matrix[:3,:3].T+matrix[:3,3],faces,groups
regions=skin_regions(body,arm);skin,_,_=capture(body);skin_faces=np.array([f for r,fs in regions['faces'].items() if r!='excluded' for f in fs],dtype=np.int32)
if a.collider:skin,skin_faces,_=capture(bpy.data.objects[a.collider])
report={'status':'FITTING','frame':a.frame,'new_dynamic_cloth_solve':False,'body_hidden_or_deleted':False,'collision_surface':a.collider or body.name,'objects':{}}
def install(obj,co):
    m=np.linalg.inv(np.array(obj.matrix_world));local=co@m[:3,:3].T+m[:3,3];mesh=bpy.data.meshes.new(obj.name+'_ContactPositions');mesh.from_pydata(local.tolist(),[],[]);helper=bpy.data.objects.new(obj.name+'_ContactPositions',mesh);scene.collection.objects.link(helper);helper.matrix_world=obj.matrix_world.copy();helper.hide_render=True;helper.hide_set(True);helper['outfit_backup']=True
    nt=bpy.data.node_groups.new(obj.name+'_StaticContactFit','GeometryNodeTree');nt.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');nt.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n,l=nt.nodes,nt.links;inp=n.new('NodeGroupInput');info=n.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=helper;position=n.new('GeometryNodeInputPosition');index=n.new('GeometryNodeInputIndex');sample=n.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT';l.new(info.outputs['Geometry'],sample.inputs['Geometry']);l.new(position.outputs[0],sample.inputs['Value']);l.new(index.outputs[0],sample.inputs['Index']);time=n.new('GeometryNodeInputSceneTime');compare=n.new('FunctionNodeCompare');compare.data_type='FLOAT';compare.operation='EQUAL';compare.inputs['B'].default_value=float(a.frame);compare.inputs['Epsilon'].default_value=.001;l.new(time.outputs['Frame'],compare.inputs['A']);setpos=n.new('GeometryNodeSetPosition');l.new(inp.outputs['Geometry'],setpos.inputs['Geometry']);l.new(sample.outputs['Value'],setpos.inputs['Position']);l.new(compare.outputs['Result'],setpos.inputs['Selection']);output=n.new('NodeGroupOutput');l.new(setpos.outputs['Geometry'],output.inputs['Geometry']);obj.modifiers.new(f'Static contact fit frame {a.frame}','NODES').node_group=nt
for name,margin in (('Cloth',.002),('SleeveLining',.001),('Stockings',.0008)):
    if name not in a.objects:continue
    obj=bpy.data.objects[name];co,faces,weights=capture(obj);names={g.index:g.name for g in obj.vertex_groups if not g.name.startswith('mmd_') and g.name in arm.pose.bones};locked=np.array([max(((v,names[i]) for i,v in gs if i in names),default=(0.,''))[1].startswith(HAND_PREFIX[1:]) for gs in weights]) if name=='Cloth' else None
    def progress(row):
        print('OUTFIT_STATIC_CONTACT',name,json.dumps(row),flush=True)
    if a.solver=='arap':
        from mmd_outfit.outfit_arap_contact import fit_surface_arap
        corrected,details=fit_surface_arap(co,faces,skin,skin_faces,locked=locked,margin=margin,iterations=a.iterations,progress=progress,workspace=out/name,runtime=ROOT/'tools/contact_stack/venv/Scripts/python.exe',worker=ROOT/'scripts/solve_surface_arap_step.py')
    else:corrected,details=fit_surface(co,faces,skin,skin_faces,locked=locked,margin=margin,iterations=a.iterations,progress=progress)
    install(obj,corrected);report['objects'][name]=details;(out/'contact_fit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
sub.show_viewport=True;sub.show_render=True;sub.levels=1;sub.render_levels=1;bpy.context.view_layer.objects.active=cloth;cloth.select_set(True);contact=next(m for m in cloth.modifiers if m.name.startswith('Static contact fit'));bpy.ops.object.modifier_move_to_index(modifier=contact.name,index=list(cloth.modifiers).index(sub));scene.frame_start=a.frame;scene.frame_end=a.frame;scene.frame_set(a.frame);report['status']='STATIC_CONTACT_FIT_REQUIRES_INDEPENDENT_AUDIT';bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_Contact325.blend'),compress=True);(out/'contact_fit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('OUTFIT_STATIC_CONTACT_SAVED',flush=True)
