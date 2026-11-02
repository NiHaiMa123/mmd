"""Prepare a real pinned-mesh cloth trial from the fitted native model."""
import argparse,json,sys,math,importlib,struct
from pathlib import Path
from collections import Counter
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from mmd_outfit.hosiery_cleanup import clean

MODEL=ROOT/'outputs/stockings_sleeves/review_ready/work.blend'
ASSETS=Path('E:/data/模之屋/动作')
MOTION=ASSETS/'シニカルナイトプラン/シニカルナイトプラン.vmd'
CAMERA=next(ASSETS.glob('シニカルナイトプラン_CAMERA*.vmd'))
MUSIC=Path('E:/data/music/Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3')


def material(name,color,roughness=.65):
    m=bpy.data.materials.new(name);m.use_nodes=True
    bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=roughness
    return m


def stage(scene):
    # Continuous curved white floor/wall avoids a horizon line behind the dancer.
    profile=[(-8.,-.012),(3.,-.012)]
    for i in range(1,17):
        a=-math.pi/2+i*math.pi/32;profile.append((3+math.cos(a),.988+math.sin(a)))
    profile.append((4.,6.));n=len(profile)
    me=bpy.data.meshes.new('WhiteWall');me.from_pydata([(x,y,z) for x in (-8,8) for y,z in profile],[],[(i,i+1,n+i+1,n+i) for i in range(n-1)]);me.materials.append(material('WhiteWall',(.82,.82,.82)))
    o=bpy.data.objects.new('WhiteWall',me);scene.collection.objects.link(o)
    for f in me.polygons:f.use_smooth=True
    render=engine('extraction');render._setup_render(scene,640,360);render._setup_lights(scene)
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.28,.28,.28,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
    scene.view_settings.view_transform='AgX'
    if hasattr(scene,'eevee'):scene.eevee.taa_render_samples=16
    scene.render.fps=30;scene.render.fps_base=1.
    return o


def islands(mesh):
    vf={}
    for f in mesh.polygons:
        for i in f.vertices:vf.setdefault(i,[]).append(f.index)
    remaining=set(range(len(mesh.polygons)));out=[]
    while remaining:
        todo=[remaining.pop()];faces=[];ids=set()
        while todo:
            fi=todo.pop();faces.append(fi)
            for i in mesh.polygons[fi].vertices:
                ids.add(i)
                for j in vf[i]:
                    if j in remaining:remaining.remove(j);todo.append(j)
        out.append((faces,ids))
    return out


def cloth_proxy(cloth,arm,body,out,last):
    from mmd_outfit.skin_collision import collider
    from mmd_outfit.jobs import write_json
    # One physical layer per overlapping printed/metal overlay pair.
    chosen=[];driven=set();kind={}
    for faces,ids in islands(cloth.data):
        mats={cloth.data.materials[cloth.data.polygons[i].material_index].mmd_material.name_j for i in faces}
        pts=[cloth.data.vertices[i].co for i in ids];z0=min(p.z for p in pts);z1=max(p.z for p in pts)
        if mats=={'新規'} and len(faces)>250 and z0<.65:
            chosen.extend(faces)
            for i in ids:kind[i]=('sleeve',1.10,1.21)
        elif mats=={'裙'} and len(faces)>250:
            chosen.extend(faces)
            # The separate lower skirt starts below the main skirt's waist.
            # Each island needs its own attachment band, or the lower island
            # has zero pins and simply falls off the character.
            start,end=(.985,1.05) if z1>1.05 else (z1-.05,z1-.012)
            for i in ids:kind[i]=('skirt',start,end)
    assert chosen,'No cloth surface selected'
    # Proxy intentionally has no shape-key stack: it is not a new character.
    ids=sorted({i for fi in chosen for i in cloth.data.polygons[fi].vertices});mapping={i:k for k,i in enumerate(ids)}
    mesh=bpy.data.meshes.new('ClothSimulationSurface');mesh.from_pydata([tuple(cloth.data.vertices[i].co) for i in ids],[],[[mapping[i] for i in cloth.data.polygons[fi].vertices] for fi in chosen]);mesh.update()
    proxy=bpy.data.objects.new('ClothSimulationSurface',mesh);bpy.context.scene.collection.objects.link(proxy);proxy.matrix_world=cloth.matrix_world.copy();proxy['outfit_backup']=True
    pin=proxy.vertex_groups.new(name='ClothPins');weights=[]
    for old in ids:
        p=cloth.data.vertices[old].co
        _,start,end=kind[old];w=max(0.,min(1.,(p.z-start)/(end-start)))
        # Smooth transition from fixed attachment to free cloth.
        w=w*w*(3-2*w);weights.append(w)
        if w:pin.add([mapping[old]],w,'REPLACE')
    for g in cloth.vertex_groups:proxy.vertex_groups.new(name=g.name)
    for old in ids:
        for g in cloth.data.vertices[old].groups:
            if not cloth.vertex_groups[g.group].name.startswith('mmd_'):proxy.vertex_groups[cloth.vertex_groups[g.group].name].add([mapping[old]],g.weight,'REPLACE')
    arm_mod=proxy.modifiers.new('Animated attachment pose','ARMATURE');arm_mod.object=arm
    # Bind the original garment plus its overlays/decorations to the proxy.
    group=cloth.vertex_groups.new(name='MeshClothRegion')
    from mathutils.kdtree import KDTree
    kd=KDTree(len(ids))
    for k,i in enumerate(ids):kd.insert(cloth.data.vertices[i].co,k)
    kd.balance()
    for v in cloth.data.vertices:
        _,_,dist=kd.find(v.co)
        secondary=sum(g.weight for g in v.groups if cloth.vertex_groups[g.group].name.startswith(('袖_','スカート_')))
        if dist<.019 or secondary>.05:driven.add(v.index)
    group.add(sorted(driven),1.,'REPLACE')
    follow=cloth.modifiers.new('Follow simulated fabric','SURFACE_DEFORM');follow.target=proxy;follow.vertex_group=group.name
    for o in bpy.context.selected_objects:o.select_set(False)
    cloth.hide_set(False);cloth.select_set(True);bpy.context.view_layer.objects.active=cloth
    bpy.ops.object.modifier_move_to_index(modifier=follow.name,index=next(i+1 for i,m in enumerate(cloth.modifiers) if m.type=='ARMATURE'))
    bpy.ops.object.surfacedeform_bind(modifier=follow.name)
    assert follow.is_bound,'Surface-deform bind failed'
    # Garment-independent evaluated skin: cloth never feeds back into the
    # collision source, avoiding a dependency cycle.
    skin=bpy.data.objects.get('Outfit_SkinCollider') or collider(body)
    from mmd_outfit.mesh_cloth import configure
    sim,solver=configure(proxy,pin.name,[skin],first=1,last=last);proxy.hide_set(True)
    report={'proxy_vertices':len(ids),'proxy_faces':len(chosen),'driven_visual_vertices':len(driven),'fully_pinned':sum(w>.999 for w in weights),'partially_pinned':sum(0<w<.999 for w in weights),**solver,'duplicate_material_layers_simulated_once':True,'mmd_sleeve_rigid_bodies_active':False}
    write_json(out/'cloth_setup.json',report)
    return proxy,sim,report


def add_preroll(arm):
    scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update();saved={b.name:b.matrix_basis.copy() for b in arm.pose.bones}
    for b in arm.pose.bones:
        paths=('location','rotation_quaternion' if b.rotation_mode=='QUATERNION' else 'rotation_euler','scale')
        for path in paths:b.keyframe_insert(data_path=path,frame=1)
        b.matrix_basis.identity()
        for frame in (-45,-30):
            for path in paths:b.keyframe_insert(data_path=path,frame=frame)
        b.matrix_basis=saved[b.name]
    scene.frame_set(1);bpy.context.view_layer.update()


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',default='outputs/cynical_cloth15/structured_v1');p.add_argument('--last',type=int,default=450);p.add_argument('--mode',choices=['structured','legacy'],default='structured');p.add_argument('--no-still',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=(ROOT/a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(MODEL),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;scene.frame_set(1);body=bpy.data.objects['达妮娅_mesh'];stock=bpy.data.objects['Stockings'];cloth=bpy.data.objects['Cloth'];arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    cleanup=clean(body,stock)
    if a.mode=='structured':
        from mmd_outfit.structured_cloth import install
        specs=[]
        for faces,ids in islands(cloth.data):
            mats={cloth.data.materials[cloth.data.polygons[i].material_index].mmd_material.name_j for i in faces};pts=[cloth.data.vertices[i].co for i in ids];z0=min(p.z for p in pts);z1=max(p.z for p in pts)
            if mats=={'新規'} and len(faces)>250 and z0<.65:
                side='L' if sum(p.x for p in pts)>0 else 'R';specs.append({'faces':faces,'kind':'sleeve_'+side,'attachment_bone':'腕.'+side,'pin_start':1.205,'pin_end':1.235,'free_depth':.55,'motion_min':.35,'motion_max':.75})
            elif mats=={'裙'} and len(faces)>250:
                top=z1>1.05;specs.append({'faces':faces,'kind':'main_skirt' if top else 'lower_skirt','attachment_bone':'下半身','pin_start':1.075 if top else z1-.035,'pin_end':1.115 if top else z1-.008,'free_depth':.30 if top else .16,'motion_min':.18,'motion_max':.45 if top else .55})
        proxy,sim,report=install(cloth,arm,body,specs,first=1,last=a.last+46)
    root=ie.mmd_root(arm)
    for o in bpy.context.selected_objects:o.select_set(False)
    root.hide_set(False);root.select_set(True);bpy.context.view_layer.objects.active=root
    bpy.ops.mmd_tools.import_vmd(filepath=str(MOTION),scale=.08,bone_mapper='PMX',margin=0,use_pose_mode=False,update_scene_settings=True,log_level='ERROR')
    scene.frame_set(1);bpy.context.view_layer.update()
    if a.mode=='structured':add_preroll(arm)
    else:proxy,sim,report=cloth_proxy(cloth,arm,body,out,a.last)
    stage_obj=stage(scene)
    for o in bpy.context.selected_objects:o.select_set(False)
    camdata=bpy.data.cameras.new('CynicalCamera');cam=bpy.data.objects.new('CynicalCamera',camdata);scene.collection.objects.link(cam);cam.select_set(True);bpy.context.view_layer.objects.active=cam
    bpy.ops.mmd_tools.import_vmd(filepath=str(CAMERA),scale=.08,margin=0,update_scene_settings=False,log_level='ERROR');scene.camera=cam
    preview_first=1
    if a.mode=='structured':
        compat=importlib.import_module(ie.ensure_mmd_tools()+'.compat.action_compat')
        for action in bpy.data.actions:
            for curve in compat.get_action_fcurves(action):
                for key in curve.keyframe_points:key.co.x+=46;key.handle_left.x+=46;key.handle_right.x+=46
                curve.update()
        preview_first=47
    editor=scene.sequence_editor_create();strips=editor.strips if hasattr(editor,'strips') else editor.sequences
    audio=strips.new_sound('Shikako - Cynical Night Plan',str(MUSIC),channel=1,frame_start=1);audio.sound.pack()
    audio.frame_start=preview_first-2
    scene['outfit_preview_first']=preview_first;scene['outfit_preview_last']=preview_first+a.last-1
    scene.frame_start=preview_first;scene.frame_end=preview_first+a.last-1;scene.render.fps=30;scene.frame_set(preview_first)
    scene.render.use_sequencer=False
    model=ie.model_meshes()
    for o in scene.objects:
        o.hide_set(o not in model and o!=stage_obj and o.type not in {'LIGHT','CAMERA'});o.select_set(False)
    proxy.hide_render=True;proxy.hide_set(True)
    for o in model:o.hide_render=bool(o.get('outfit_backup'))
    scene.camera=cam;scene.render.filepath=str(out/'frames'/'f')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':area.spaces.active.overlay.show_overlays=False;area.spaces.active.region_3d.view_perspective='CAMERA'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True)
    metadata={'source':str(MODEL),'motion':str(MOTION),'camera':str(CAMERA),'music':str(MUSIC),'frames':[preview_first,preview_first+a.last-1],'preroll_frames':[1,preview_first-1] if preview_first>1 else [],'fps':30,'seconds':a.last/30,'cleanup':cleanup,'cloth':report,'scope':'Actual mesh cloth trial for skirt and sleeve tails; hair and other secondary rigid-body physics not simulated in this first trial.'}
    (out/'setup.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CYNICAL_SCENE_READY',json.dumps(report),flush=True)
    # Before doing a full bake, save a camera-framing still and an explicit
    # fixed front diagnostic. Rendering is not evidence of cloth simulation.
    if not a.no_still:scene.render.filepath=str(out/'camera_start.png');bpy.ops.render.render(write_still=True)
    (out/'cloth_setup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PREPARE_COMPLETE',flush=True)


if __name__=='__main__':main()
