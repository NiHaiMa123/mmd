"""Actual triangle contact and posed renders for complete target stockings."""
import argparse,sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json
from bridal_multiview_review import crossing
from inspect_sleeves_stockings import parts

def evaluate(obj):
    deps=bpy.context.evaluated_depsgraph_get();me=bpy.data.meshes.new_from_object(obj.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps);me.calc_loop_triangles();return me,[obj.matrix_world@v.co for v in me.vertices]

IMAGES={}
def opaque(me,t,p):
    material=me.materials[t.material_index]
    node=material.node_tree.nodes.get('mmd_base_tex') if material.use_nodes else None
    if not node or not node.image:return True
    im=node.image
    if im.name not in IMAGES:
        w,h=im.size;a=np.empty(w*h*4,dtype=np.float32);im.pixels.foreach_get(a);IMAGES[im.name]=a.reshape(h,w,4)[:,:,3]
    a=IMAGES[im.name];h,w=a.shape;uv=me.uv_layers.active
    coords=[Vector((*uv.data[i].uv,0)) for i in t.loops];mapped=barycentric_transform(p,*(me.vertices[i].co for i in t.vertices),*coords)
    return a[int(mapped.y*h)%h,int(mapped.x*w)%w]>.1

def contacts(body,stock,cloth,body_arm_ids,sleeve_ids):
    bm,bp=evaluate(body);sm,sp=evaluate(stock);cm,cp=evaluate(cloth)
    body_tri=[t for t in bm.loop_triangles if bm.materials[t.material_index].mmd_material.name_j in {'Body','Nails'} and max(body.data.vertices[i].co.z for i in t.vertices)<1.12 and abs(sum(body.data.vertices[i].co.x for i in t.vertices)/3)<.22]
    stock_tri=list(sm.loop_triangles)
    def check(ap,at,bp,bt,mesh=None):
        aa=BVHTree.FromPolygons(ap,[tuple(t.vertices) for t in at],all_triangles=True);bb=BVHTree.FromPolygons(bp,[tuple(t.vertices) for t in bt],all_triangles=True);pairs=[]
        for i,j in aa.overlap(bb):
            segment=crossing([ap[k] for k in at[i].vertices],[bp[k] for k in bt[j].vertices])
            if segment and (mesh is None or opaque(mesh,bt[j],sum(segment,Vector())*.5)):
                entry={'body_triangle':i,'cloth_triangle':j,'center':list(sum(segment,Vector())*.5)}
                if mesh:
                    material=mesh.materials[bt[j].material_index];entry.update(material=material.name,mmd_alpha=material.mmd_material.alpha)
                pairs.append(entry)
        return pairs
    s=check(bp,body_tri,sp,stock_tri)
    arm_tri=[t for t in bm.loop_triangles if sum(i in body_arm_ids for i in t.vertices)>=2]
    attr=cm.attributes.get('OutfitAudit_SleeveRegion') or cm.attributes.get('SleeveRegion.001')
    assert attr is not None,'Missing sleeve region after evaluation'
    sleeve_tri=[t for t in cm.loop_triangles if all(attr.data[i].value>.5 for i in t.vertices)]
    sleeves=check(bp,arm_tri,cp,sleeve_tri,cm)
    hip=sm.attributes.get('OutfitAudit_TightsHipRegion') or sm.attributes.get('TightsHipRegion.001')
    assert hip is not None,'Missing hip region after evaluation'
    hip_count=sum(any(hip.data[i].value>.5 for i in stock_tri[p['cloth_triangle']].vertices) for p in s)
    for me in (bm,sm,cm):bpy.data.meshes.remove(me)
    return {'stockings_crossing_pairs':len(s),'hip_crossing_pairs':hip_count,'stockings_crossings':s,'sleeves_crossing_pairs':len(sleeves),'sleeves_crossings':sleeves}

def main():
    p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--motion',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);fit=Path(a.fit).resolve();out=fit/'review';out.mkdir(exist_ok=True)
    ie,render=engine('import_export'),engine('extraction');package=ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(fit/'work.blend'),load_ui=False,use_scripts=False)
    body=bpy.data.objects['达妮娅_mesh'];stock=bpy.data.objects['Stockings'];cloth=bpy.data.objects['Cloth'];arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    names={g.index:g.name for g in body.vertex_groups};arm_ids={v.index for v in body.data.vertices if sum(g.weight for g in v.groups if names[g.group].startswith(('腕','ひじ','肩')) and not names[g.group].startswith('mmd_'))>.5}
    sleeve_ids={i for row in parts(cloth,['新規','服+jinshu']) for i in row['vertices']}
    model=ie.model_meshes(list(bpy.context.scene.objects));scene=bpy.context.scene
    for o in scene.objects:o.hide_render=True
    for o in model:o.hide_render=False
    render._setup_render(scene,1000,1100);render._setup_lights(scene);data=bpy.data.cameras.new('PosedRepair');data.type='ORTHO';cam=bpy.data.objects.new('PosedRepair',data);scene.collection.objects.link(cam);scene.camera=cam
    results={};neutral=contacts(body,stock,cloth,arm_ids,sleeve_ids);results['neutral']=neutral
    def shot(name,center,scale,direction):
        center=Vector(center);data.ortho_scale=scale;cam.location=center+Vector(direction).normalized()*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
    shot('neutral_side',(0,.02,.83),1.75,(1,0,.02))
    matrices={b.name:b.matrix_basis.copy() for b in arm.pose.bones}
    for name,angles in [('elbows_bent',{'ひじ.L':(1.4,0,0),'ひじ.R':(1.4,0,0)}),('hip_flex',{'足.L':(-.7,0,.15),'足.R':(.35,0,-.15)}),('legs_apart',{'足.L':(0,0,-.35),'足.R':(0,0,.35)})]:
        for b in arm.pose.bones:b.matrix_basis=matrices[b.name]
        for n,values in angles.items():b=arm.pose.bones[n];b.rotation_mode='XYZ';b.rotation_euler=values
        bpy.context.view_layer.update();results[name]=contacts(body,stock,cloth,arm_ids,sleeve_ids)
        shot(name,(0,.02,1.15) if name=='elbows_bent' else (0,.02,.73),.85 if name=='elbows_bent' else 1.45,(.5,-1,.1))
    for b in arm.pose.bones:b.matrix_basis=matrices[b.name]
    bpy.context.view_layer.update()
    if a.motion:
        vmd=ROOT/'outputs/keqing_head/proportions_v2/mmd/grounded.vmd';arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm
        bpy.ops.mmd_tools.import_vmd(filepath=str(vmd),scale=.08,rename_bones=True,margin=0,log_level='ERROR')
        for frame in (1,121,256,3401):
            scene.frame_set(frame);bpy.context.view_layer.update();results['vmd_'+str(frame)]=contacts(body,stock,cloth,arm_ids,sleeve_ids)
            me,points=evaluate(body);center=tuple((min(p[k] for p in points)+max(p[k] for p in points))*.5 for k in range(3));bpy.data.meshes.remove(me);shot('vmd_'+str(frame),center,1.85,(.3,-1,.08))
    write_json(out/'contacts.json',results);print('REPAIR_CONTACTS',json.dumps({k:{n:r[n] for n in ('stockings_crossing_pairs','hip_crossing_pairs','sleeves_crossing_pairs')} for k,r in results.items()}),flush=True)

if __name__=='__main__':main()
