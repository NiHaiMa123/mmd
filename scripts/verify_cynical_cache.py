"""Reload the finished disk cache and inspect sparse full-body views."""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine


def main():
    p=argparse.ArgumentParser();p.add_argument('--fit',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.fit).resolve();review=out/'cache_review';review.mkdir(exist_ok=True)
    engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;proxy=bpy.data.objects['ClothSimulationSurface'];sim=next(m for m in proxy.modifiers if m.type=='CLOTH');assert sim.point_cache.is_baked,'Reloaded cloth cache is not baked'
    expected=json.loads((out/'simulation_report.json').read_text(encoding='utf-8'));first=int(scene.get('outfit_preview_first',1));last=int(scene.get('outfit_preview_last',450));available=[int(k) for k in expected['frames'] if first<=int(k)<=last];samples=[last,first]+[min(available,key=lambda f:abs(f-(first+source-1))) for source in (240,150,330)];result={'cache_baked_on_reload':True,'preview_frames':[first,last],'frames':{}}
    for frame in samples:
        start=time.monotonic();scene.frame_set(frame);bpy.context.view_layer.update();ev=proxy.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();co=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',co);co=co.reshape(-1,3);ev.to_mesh_clear();bounds=np.array([co.min(axis=0),co.max(axis=0)])
        error=float(np.abs(bounds-np.array(expected['frames'][str(frame)]['bounds'])).max());assert error<1e-5,(frame,error)
        result['frames'][str(frame)]={'bounds_error_m':error,'random_seek_seconds':time.monotonic()-start}
    # Align the cover track's first attack to the motion's opening marker.
    strips=scene.sequence_editor.strips if hasattr(scene.sequence_editor,'strips') else scene.sequence_editor.sequences
    for strip in strips:
        if strip.type=='SOUND':strip.frame_start=first-2
    result['audio_trim_start_s']=2/30
    scene.frame_set(first);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True)
    # The fixed diagnostic camera is only used for these stills; the saved
    # project keeps the supplied animated camera.
    data=bpy.data.cameras.new('ClothFullBodyReview');data.type='ORTHO';data.ortho_scale=1.9;cam=bpy.data.objects.new('ClothFullBodyReview',data);scene.collection.objects.link(cam);scene.camera=cam
    scene.render.resolution_x=560;scene.render.resolution_y=700
    body=bpy.data.objects['达妮娅_mesh']
    for source_frame in (1,150,240,270,330,450):
        frame=first+source_frame-1
        scene.frame_set(frame);bpy.context.view_layer.update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();pts=[body.matrix_world@v.co for v in me.vertices];center=Vector(tuple((min(p[k] for p in pts)+max(p[k] for p in pts))*.5 for k in range(3)));ev.to_mesh_clear()
        cam.location=center+Vector((.15,-1,.025)).normalized()*4;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(review/f'full_{source_frame:04d}.png');bpy.ops.render.render(write_still=True)
    (out/'cache_reload_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('CLOTH_CACHE_RELOAD_VERIFIED',json.dumps(result),flush=True)


if __name__=='__main__':main()
