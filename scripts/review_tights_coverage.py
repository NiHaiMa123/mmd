"""Check externally visible hip skin against tights from twelve directions.

Raw internal triangle intersections are retained in the separate contact
report. This test asks whether an external ray reaches hip skin before nylon.
"""
import sys,argparse,math,json
from pathlib import Path
from collections import Counter
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json
from review_tights_sleeves import evaluate

def main():
    p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--region',choices=['hips','sleeves'],default='hips');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);fit=Path(a.fit).resolve()
    ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(fit/'work.blend'),load_ui=False,use_scripts=False);body=bpy.data.objects['达妮娅_mesh'];stock=bpy.data.objects['Stockings'];arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');(fit/'review').mkdir(exist_ok=True)
    if a.region=='sleeves':stock=bpy.data.objects['SleeveLining']
    results={}
    def check():
        bm,bp=evaluate(body);sm,sp=evaluate(stock)
        bt=[t for t in bm.loop_triangles if bm.materials[t.material_index].mmd_material.name_j=='Body'];st=[t for t in sm.loop_triangles]
        body_tree=BVHTree.FromPolygons(bp,[tuple(t.vertices) for t in bt],all_triangles=True);stock_tree=BVHTree.FromPolygons(sp,[tuple(t.vertices) for t in st],all_triangles=True)
        if a.region=='sleeves':region={k for k,t in enumerate(bt) if body.data.attributes['OutfitSleeveLiningAuditFaces'].data[t.polygon_index].value}
        else:region={k for k,t in enumerate(bt) if all(.79<body.data.vertices[i].co.z<1.035 and abs(body.data.vertices[i].co.x)<.205 for i in t.vertices)}
        centers=[sum((bp[i] for i in bt[k].vertices),Vector())/3 for k in sorted(region)[::3]];views=[]
        for azimuth in range(0,360,30):
            angle=math.radians(azimuth);direction=Vector((math.sin(angle),math.cos(angle),.08)).normalized();tested=0;leaks=[]
            for point in centers:
                origin=point+direction*3;bh,bn,bi,bd=body_tree.ray_cast(origin,-direction,3.1)
                if bh is None or bi not in region:continue
                tested+=1;sh,sn,si,sd=stock_tree.ray_cast(origin,-direction,bd+.02)
                if sh is None or sd>bd+.0004:leaks.append({'point':list(bh),'depth_m':sd-bd if sh else None,'body_triangle':bi})
            views.append({'azimuth':azimuth,'tested_skin_samples':tested,'visible_skin_leaks':len(leaks),'examples':leaks[:25]})
        for me in (bm,sm):bpy.data.meshes.remove(me)
        return views
    results['neutral']=check();arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.mmd_tools.import_vmd(filepath=str(ROOT/'outputs/keqing_head/proportions_v2/mmd/grounded.vmd'),scale=.08,rename_bones=True,margin=0,log_level='ERROR')
    for f in (1,121,256,3401):bpy.context.scene.frame_set(f);bpy.context.view_layer.update();results[str(f)]=check();print('HIP_COVERAGE',f,sum(r['visible_skin_leaks'] for r in results[str(f)]),flush=True)
    filename='visible_sleeve_lining_coverage.json' if a.region=='sleeves' else 'visible_hip_coverage.json'
    write_json(fit/'review'/filename,results);print('COVERAGE_DONE',a.region,json.dumps({k:sum(r['visible_skin_leaks'] for r in rows) for k,rows in results.items()}),flush=True)

if __name__=='__main__':main()
