"""Export actual skin/glove colliders and welded cloth proxies for PPF.

No old world-space simulation cache enters this export. All trajectories are
evaluated from the selected skeletal action and the kinematic cloth reference.
"""
import sys,argparse,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,all_coords,evaluated_coords,inside_votes,add_fixed_outfit_collider
p=argparse.ArgumentParser();p.add_argument('--fit',default='sequence_v2');p.add_argument('--start',type=int,default=1);p.add_argument('--end',type=int,default=496);p.add_argument('--label',default='outfit');p.add_argument('--open-preroll-degrees',type=float,default=0);p.add_argument('--initialize-clearance',type=float,default=0);p.add_argument('--sample-step',type=float,default=1.);p.add_argument('--fixed-outfit',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();folder=ROOT/'outputs/cynical_cloth15/contact_motion'/a.fit;bpy.ops.wm.open_mainfile(filepath=str(folder/'ContactMotion.blend'),load_ui=False,use_scripts=False)
body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];ref=bpy.data.objects['ClothKinematicReference'];proxy=bpy.data.objects['ClothSimulationSurface'];scene=bpy.context.scene
for o in bpy.data.objects:
    if o.type=='MESH' and o!=body:o.hide_viewport=True
ref.hide_viewport=False;ref.hide_set(True)
regions=skin_regions(body,arm);hands=add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);fixed_outfit=add_fixed_outfit_collider(regions,body,arm,bpy.data.objects['Cloth']) if a.fixed_outfit else None
body_faces=[f for r,fs in regions['faces'].items() if r!='excluded' for f in fs];body_ids=sorted({i for f in body_faces for i in f});body_map={i:j for j,i in enumerate(body_ids)};body_tri=np.array([[body_map[i] for i in f] for f in body_faces],dtype=np.int32)
rest=np.array([v.co[:] for v in proxy.data.vertices]);clusters=[];mapping={};quant={}
for i,pnt in enumerate(rest):
    key=tuple(np.round(pnt/1e-5).astype(int));k=quant.get(key)
    if k is None:k=len(clusters);quant[key]=k;clusters.append([])
    clusters[k].append(i);mapping[i]=k
faces=np.array([[mapping[i] for i in f.vertices] for f in proxy.data.polygons],dtype=np.int32);faces=faces[np.array([len(set(f))==3 for f in faces])]
pin_group=proxy.vertex_groups['ClothPins'].index;weights=np.array([sum(g.weight for g in v.groups if g.group==pin_group) for v in proxy.data.vertices]);weights=np.array([weights[c].max() for c in clusters])
cloth=[];skin=[];adjusted=0;max_adjustment=0.;attachment_binding={}
sample_frames=set(np.arange(a.start,a.end+a.sample_step*.1,a.sample_step).tolist())
for layer in arm.animation_data.action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                sample_frames.update(float(k.co.x) for k in curve.keyframe_points if a.start<=k.co.x<=a.end and abs(k.co.x-round(k.co.x))>1e-6)
sample_frames=sorted(sample_frames)
for frame in sample_frames:
    scene.frame_set(int(frame),subframe=frame%1)
    if frame<=46 and a.open_preroll_degrees:
        t=max(0,min(1,(frame-1)/45));strength=1-t*t*(3-2*t)
        for side,sign in (('L',-1),('R',1)):
            bone=arm.pose.bones['腕.'+side];axis=(arm.matrix_world@bone.matrix).to_3x3().inverted()@Vector((0,1,0));bone.rotation_quaternion=bone.rotation_quaternion@Quaternion(axis,sign*math.radians(a.open_preroll_degrees)*strength)
        arm.update_tag();bpy.context.view_layer.update()
    co=evaluated_coords(ref);fabric=np.array([co[c].mean(axis=0) for c in clusters],dtype=np.float32);skin_co=all_coords(body,regions)[body_ids].astype(np.float32)
    if a.initialize_clearance:
        if frame==a.start:bvh=BVHTree.FromPolygons(skin_co.tolist(),body_tri.tolist(),all_triangles=True)
        selected=range(len(fabric)) if frame==a.start else []
        for i in selected:
            point=Vector(fabric[i]);q,n,fi,d=bvh.find_nearest(point)
            if q is None or d>.08:continue
            signed=(point-q).dot(n)
            if (signed>=0 and d<a.initialize_clearance) or (signed<0 and inside_votes(bvh,point)):
                new=q+n*a.initialize_clearance;max_adjustment=max(max_adjustment,(new-point).length);fabric[i]=new;adjusted+=1
        if frame==a.start:
            for i in np.flatnonzero(weights>=.99999):
                q,n,fi,d=bvh.find_nearest(Vector(fabric[i]));indices=body_tri[fi];tri=skin_co[indices].astype(float);matrix=np.column_stack((tri[1]-tri[0],tri[2]-tri[0]));uv=np.linalg.lstsq(matrix,np.array(q)-tri[0],rcond=None)[0];bary=np.array([1-uv.sum(),uv[0],uv[1]]);offset=max(a.initialize_clearance,(Vector(fabric[i])-q).dot(n));attachment_binding[int(i)]=(indices,bary,offset)
        for i,(indices,bary,offset) in attachment_binding.items():
            tri=skin_co[indices].astype(float);normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);normal/=max(np.linalg.norm(normal),1e-12);fabric[i]=bary@tri+normal*offset
    cloth.append(fabric);skin.append(skin_co)
    if frame%100==0:print('PPF_OUTFIT_EXPORT',frame,flush=True)
out=folder/'ppf'/a.label;out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/'trajectories.npz',cloth=np.array(cloth),body=np.array(skin),cloth_faces=faces,body_faces=body_tri,pins=weights,original_mapping=np.array([mapping[i] for i in range(len(rest))]))
(out/'manifest.json').write_text(json.dumps(dict(source=str(folder/'ContactMotion.blend'),action=arm.animation_data.action.name,frames=[a.start,a.end],fps=30,sample_times_s=[(f-a.start)/30 for f in sample_frames],cloth_vertices=len(clusters),cloth_faces=len(faces),body_vertices=len(body_ids),body_faces=len(body_faces),hands=hands,fixed_outfit=fixed_outfit,old_caches_used=False,preroll_arm_open_degrees=a.open_preroll_degrees,initial_and_attachment_clearance_m=a.initialize_clearance,projected_samples=adjusted,max_initial_or_attachment_adjustment_m=max_adjustment,hard_attachment_tracking='same source skin triangle and barycentric coordinates across all frames',skin_triangle_attachments=len(attachment_binding)),ensure_ascii=False,indent=2),encoding='utf-8');print('PPF_OUTFIT_EXPORTED',str(out),flush=True)
