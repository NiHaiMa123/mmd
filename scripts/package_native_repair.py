"""Make a compressed, self-contained review copy of a native repair."""
import argparse,sys,json,shutil
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);fit=Path(a.fit).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(fit/'work.blend'),load_ui=False,use_scripts=False)
    lining=bpy.data.objects.get('SleeveLining')
    if lining and not any(m.type=='SOLIDIFY' for m in lining.modifiers):
        thickness=lining.modifiers.new('Sleeve lining thickness','SOLIDIFY');thickness.thickness=.005;thickness.offset=-1.;thickness.use_even_offset=True
    model=ie.model_meshes(list(bpy.context.scene.objects));used=set();seen=set()
    def images(tree):
        if tree in seen:return
        seen.add(tree)
        for node in tree.nodes:
            if node.type=='TEX_IMAGE' and node.image:used.add(node.image)
            if node.type=='GROUP' and node.node_tree:images(node.node_tree)
    for obj in model:
        for material in obj.data.materials:
            if material.use_nodes:images(material.node_tree)
    missing=[];packed=[]
    for im in used:
        if im.packed_file or im.source!='FILE':continue
        path=Path(bpy.path.abspath(im.filepath))
        if not path.is_file():missing.append(str(path));continue
        im.pack();packed.append(im.name)
    if missing:raise ValueError('Missing used textures: '+repr(missing))
    for o in bpy.context.scene.objects:o.hide_set(o not in model);o.select_set(False)
    scene=bpy.context.scene;scene.frame_set(1)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active;space.overlay.show_overlays=False;space.show_gizmo=False;space.shading.type='MATERIAL';space.shading.use_scene_lights=False;space.shading.use_scene_world=False;space.clip_start=.001
    filename=out/'Keqing_Stockings_Sleeves.blend';bpy.ops.wm.save_as_mainfile(filepath=str(filename),compress=True);shutil.copyfile(filename,out/'work.blend')
    for name in ('repair_report.json','stocking_provenance.json','front.png','back.png','legs_front.png','legs_back.png','sleeve_oblique.png','hips_fit_back.png'):
        source=fit/name
        if source.is_file():shutil.copyfile(source,out/name)
    for name in ('review','shoe_preservation','physics_review'):
        if (fit/name).is_dir():shutil.copytree(fit/name,out/name,dirs_exist_ok=True)
    if (out/'repair_report.json').is_file():
        metadata=read_json(out/'repair_report.json');metadata['sleeves']['fitted_lining']['thickness_m']=.005;write_json(out/'repair_report.json',metadata)
    report={'source':str(fit),'file':str(filename),'packed_images':packed,'used_images':len(used),'missing_images':missing,'visible_meshes':len(model),'visible_helpers':[o.name for o in scene.objects if o.visible_get() and o not in model],'compressed_bytes':filename.stat().st_size,'scope':'native Blender review candidate; procedural deformation is not a PMX export'}
    write_json(out/'delivery.json',report);print('NATIVE_REPAIR_PACKAGED',json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
