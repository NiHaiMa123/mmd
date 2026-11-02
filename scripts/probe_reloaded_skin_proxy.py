"""Verify saved collision geometry still encloses the reloaded live body."""
import argparse,sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import SKIN,inside_votes,triangle_crosses
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()),load_ui=False,use_scripts=False);bpy.context.scene.frame_set(325);bpy.context.view_layer.update()
def capture(name):
    obj=bpy.data.objects[name];ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();m=np.array(obj.matrix_world);co=np.array([v.co[:] for v in mesh.vertices]);co=co@m[:3,:3].T+m[:3,3];faces=np.array([t.vertices[:] for t in mesh.loop_triangles if name!='达妮娅_mesh' or mesh.materials[t.material_index].name in SKIN|{'Nails'}]);ev.to_mesh_clear();return co,faces
skin,sf=capture('达妮娅_mesh');proxy,pf=capture('Outfit_ClosedSkinContactProxy');tree=BVHTree.FromPolygons(proxy.tolist(),pf.tolist(),all_triangles=True);outside=[]
for i in np.unique(sf):
    q,n,j,d=tree.find_nearest(Vector(skin[i]));signed=(Vector(skin[i])-q).dot(n)
    if signed>.00001:outside.append((int(i),float(d),skin[i].tolist()))
other=BVHTree.FromPolygons(skin.tolist(),sf.tolist(),all_triangles=True);pairs=[(i,j) for i,j in tree.overlap(other) if triangle_crosses([Vector(v) for v in proxy[pf[i]]],[Vector(v) for v in skin[sf[j]]])];print('RELOADED_BODY_PROXY',json.dumps({'outside_body_vertices':len(outside),'largest_outside':sorted(outside,key=lambda v:-v[1])[:6],'true_crossings':len(pairs)}),flush=True)
