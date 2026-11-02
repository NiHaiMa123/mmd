"""Isolate each foot, inspect twelve directions and mark real triangle crossings."""
import argparse,json,sys
from pathlib import Path
from collections import Counter
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json


def crossing(a,b):
    points=[]
    for first,second in ((a,b),(b,a)):
        normal=(second[1]-second[0]).cross(second[2]-second[0])
        if normal.length<1e-12:continue
        normal.normalize();signed=[(p-second[0]).dot(normal) for p in first]
        if min(signed)>-1e-7 or max(signed)<1e-7:continue
        for k in range(3):
            start,end=first[k],first[(k+1)%3];direction=end-start
            if direction.length_squared<1e-16:continue
            hit=intersect_ray_tri(*second,direction,start,True)
            if hit is None:continue
            t=(hit-start).dot(direction)/direction.length_squared
            if -1e-6<=t<=1+1e-6 and not any((p-hit).length<1e-6 for p in points):points.append(hit)
    if len(points)<2:return None
    pair=max(((x,y) for i,x in enumerate(points) for y in points[i+1:]),key=lambda v:(v[0]-v[1]).length)
    return pair if (pair[0]-pair[1]).length>2e-5 else None


def snapshot(obj,side,cap):
    rest=obj.data.attributes.get('ReviewRestPosition') or obj.data.attributes.new('ReviewRestPosition','FLOAT_VECTOR','POINT')
    for value,vertex in zip(rest.data,obj.data.vertices):value.vector=vertex.co
    obj.data.update();obj.update_tag(refresh={'DATA'});bpy.context.view_layer.update()
    data=bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()),preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
    attr=data.attributes.new('ReviewSourceIndex','INT','POINT')
    attr.data.foreach_set('value',list(range(len(data.vertices))))
    if not obj.get('external_shoe'):
        bm=bmesh.new();bm.from_mesh(data)
        sign=1 if side=='L' else -1
        bm.verts.ensure_lookup_table()
        rest=data.attributes['ReviewRestPosition']
        doomed=[v for v in bm.verts if (obj.matrix_world@rest.data[v.index].vector).x*sign<0 or (obj.matrix_world@rest.data[v.index].vector).z>cap]
        bmesh.ops.delete(bm,geom=doomed,context='VERTS');bm.to_mesh(data);bm.free()
    copy=bpy.data.objects.new('Review_'+obj.name,data);bpy.context.scene.collection.objects.link(copy);copy.matrix_world=obj.matrix_world
    data.calc_loop_triangles();points=[copy.matrix_world@v.co for v in data.vertices]
    triangles=[t.vertices[:] for t in data.loop_triangles]
    tree=BVHTree.FromPolygons(points,triangles,all_triangles=True)
    return copy,points,triangles,tree


def main():
    p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--out',required=True);p.add_argument('--no-marks',action='store_true')
    p.add_argument('--vmd');p.add_argument('--frames',nargs='+',type=int,default=[1]);p.add_argument('--audit-only',action='store_true');p.add_argument('--assert-clear',action='store_true')
    p.add_argument('--sides',nargs='+',choices=['L','R'],default=['L','R']);p.add_argument('--views',nargs='+')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    ie,render=[engine(n) for n in ('import_export','extraction')];ie.ensure_mmd_tools()
    bpy.ops.wm.open_mainfile(filepath=a.blend,load_ui=False,use_scripts=False)
    original=list(bpy.context.scene.objects);arm=next(o for o in original if o.type=='ARMATURE')
    layers=[o for o in ie.model_meshes() if not o.get('external_shoe')]
    shoes=[o for o in original if o.get('external_shoe')]
    # Generated clothing inherits rest coordinates from its upstream body.
    # Populate every source before evaluating any downstream geometry node.
    for obj in layers:
        rest=obj.data.attributes.get('ReviewRestPosition') or obj.data.attributes.new('ReviewRestPosition','FLOAT_VECTOR','POINT')
        for value,vertex in zip(rest.data,obj.data.vertices):value.vector=vertex.co
        obj.data.update();obj.update_tag(refresh={'DATA'})
    bpy.context.view_layer.update()
    if a.vmd:
        arm.hide_set(False);bpy.context.view_layer.objects.active=arm;arm.select_set(True)
        bpy.ops.mmd_tools.import_vmd(filepath=a.vmd,scale=.08,rename_bones=True,margin=0,log_level='ERROR')
        arm.hide_set(True)
    for obj in original:obj.hide_render=True
    scene=bpy.context.scene;render._setup_render(scene,1000,1000);render._setup_lights(scene)
    camera_data=bpy.data.cameras.new('DedicatedShoeReview');camera_data.type='ORTHO'
    camera=bpy.data.objects.new('DedicatedShoeReview',camera_data);scene.collection.objects.link(camera);scene.camera=camera
    marker_material=bpy.data.materials.new('ActualCrossing_Red');marker_material.use_nodes=True
    nodes=marker_material.node_tree.nodes;nodes.clear();emission=nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(1,.015,.005,1)
    output=nodes.new('ShaderNodeOutputMaterial');marker_material.node_tree.links.new(emission.outputs[0],output.inputs['Surface'])
    report={'source':str(Path(a.blend).resolve()),'sides':{},'vmd':a.vmd,'scope':'isolated left/right foot photos and non-coplanar triangle crossings; calf cut at rest height 0.27 m is diagnostic only; markers can include hidden contacts; no cloth/rigid dynamics'}
    for frame,side,sign in [(f,s,k) for f in a.frames for s,k in [('L',1),('R',-1)] if s in a.sides]:
        scene.frame_set(frame);bpy.context.view_layer.update()
        group=[];skin=[];shoe=[]
        for obj in layers:
            row=snapshot(obj,side,.27);group.append(row[0]);skin.append((obj.name,row))
        for obj in shoes:
            if not obj.name.endswith('.'+side):continue
            row=snapshot(obj,side,.27);group.append(row[0]);shoe.append((obj.name,row))
        segments=[];counts=Counter()
        for layer,(lo,lp,lt,lbvh) in skin:
            for part,(so,sp,st,sbvh) in shoe:
                count=0
                for i,j in lbvh.overlap(sbvh):
                    pair=crossing([lp[k] for k in lt[i]],[sp[k] for k in st[j]])
                    if pair:
                        count+=1;segments.append({'layer':layer,'shoe':part,'points':[list(p) for p in pair],
                            'layer_vertices':[lo.data.attributes['ReviewSourceIndex'].data[k].value for k in lt[i]],
                            'layer_material':lo.data.materials[lo.data.loop_triangles[i].material_index].name})
                if count:counts[layer+' -> '+part]=count
        key=side if not a.vmd and len(a.frames)==1 else f'{frame}_{side}'
        report['sides'][key]={'crossing_pairs':len(segments),'by_layer_and_part':dict(counts),'segments':segments}
        write_json(out/'report.json',report)
        print('DEDICATED_SHOE_CONTACTS',key,len(segments),dict(counts),flush=True)
        if a.audit_only:
            for obj in group:bpy.data.objects.remove(obj,do_unlink=True)
            continue
        marker_data=bpy.data.curves.new('CrossingSegments_'+side,'CURVE');marker_data.dimensions='3D';marker_data.bevel_depth=.00018;marker_data.bevel_resolution=0
        for row in segments:
            spline=marker_data.splines.new('POLY');spline.points.add(1)
            for point,co in zip(spline.points,row['points']):point.co=(*co,1)
        marker=bpy.data.objects.new('CrossingMarkers_'+side,marker_data);scene.collection.objects.link(marker);marker_data.materials.append(marker_material)
        ankle=arm.data.bones['足首D.'+side].head_local
        center=Vector((ankle.x,.015,.13))
        views=[('front',(0,-1,.08),center,.32),('back',(0,1,.08),center,.32),
               ('outer',(sign,0,.02),center,.32),('inner',(-sign,0,.02),center,.32),
               ('outer_front',(sign,-1,.25),center,.32),('inner_front',(-sign,-1,.25),center,.32),
               ('top',(0,-.55,1),center,.32),('bottom',(0,-.2,-1),center,.32),
               ('heel_inner',(-sign,1,.1),Vector((ankle.x,.075,.095)),.18),
               ('heel_outer',(sign,1,.1),Vector((ankle.x,.075,.095)),.18),
               ('toe_outer',(sign,-1,.8),Vector((ankle.x,-.045,.04)),.15),
               ('toe_inner',(-sign,-1,.8),Vector((ankle.x,-.045,.04)),.15)]
        for name,direction,target,scale in views:
            if a.views and name not in a.views:continue
            motion=arm.pose.bones['足首D.'+side].matrix@arm.data.bones['足首D.'+side].matrix_local.inverted()
            target=motion@target;direction=motion.to_3x3()@Vector(direction)
            camera_data.ortho_scale=scale;camera.location=target+Vector(direction).normalized()*3
            camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            marker.hide_render=True;scene.render.filepath=str(out/f'{key}_{name}.png');bpy.ops.render.render(write_still=True)
            if not a.no_marks:
                marker.hide_render=False;scene.render.filepath=str(out/f'{key}_{name}_marked.png');bpy.ops.render.render(write_still=True)
        for obj in [*group,marker]:bpy.data.objects.remove(obj,do_unlink=True)
    write_json(out/'report.json',report)
    if a.assert_clear:assert all(row['crossing_pairs']==0 for row in report['sides'].values()),'Foot/shoe intersections remain'
    print('DEDICATED_SHOE_REVIEW_COMPLETE',out,flush=True)


if __name__=='__main__':main()
