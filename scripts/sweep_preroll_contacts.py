"""Choose a cloth-aware opening pose from actual triangle intersections."""
import sys,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,all_coords,evaluated_coords
from bridal_multiview_review import crossing
engine('import_export').ensure_mmd_tools();folder=ROOT/'outputs/cynical_cloth15/contact_motion/sequence_v5';bpy.ops.wm.open_mainfile(filepath=str(folder/'ContactMotion.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene;body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];ref=bpy.data.objects['ClothKinematicReference'];ref.hide_viewport=False
for o in bpy.data.objects:
    if o.type=='MESH' and o not in (body,ref):o.hide_viewport=True
regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);faces=[f for r,fs in regions['faces'].items() if r!='excluded' for f in fs];cf=[tuple(f.vertices) for f in ref.data.polygons];scene.frame_set(1);bones=[arm.pose.bones['腕.'+s] for s in ('L','R')];base=[b.rotation_quaternion.copy() for b in bones];axes=[(arm.matrix_world@b.matrix).to_3x3().inverted()@Vector((0,1,0)) for b in bones];rows=[]
for angle in (0,15,25,30,35,40,45,50,55,60,65,70):
    for i,b in enumerate(bones):b.rotation_quaternion=base[i]@Quaternion(axes[i],(-1 if i==0 else 1)*math.radians(angle))
    arm.update_tag();bpy.context.view_layer.update();skin=[Vector(v) for v in all_coords(body,regions)];cloth=[Vector(v) for v in evaluated_coords(ref)];ctree=BVHTree.FromPolygons(cloth,cf,all_triangles=True);btree=BVHTree.FromPolygons(skin,faces,all_triangles=True)
    self_pairs=[(i,j) for i,j in ctree.overlap(ctree) if i<j and not set(cf[i])&set(cf[j]) and crossing([cloth[k] for k in cf[i]],[cloth[k] for k in cf[j]])]
    pairs=[(i,j) for i,j in ctree.overlap(btree) if crossing([cloth[k] for k in cf[i]],[skin[k] for k in faces[j]])]
    row=dict(angle_degrees=angle,cloth_self=len(self_pairs),cloth_body=len(pairs));rows.append(row);print('PREROLL_SPACE_SWEEP',row,flush=True)
(folder/'preroll_space_sweep.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
