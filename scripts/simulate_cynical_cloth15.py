"""Sequential cloth calculation with strain diagnostics and preview frames."""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine


def main():
    p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--last',type=int,default=450);p.add_argument('--render-step',type=int,default=2);p.add_argument('--shots',type=int,nargs='*',default=[]);p.add_argument('--bake',action='store_true');p.add_argument('--object',default='ClothSimulationSurface');p.add_argument('--cache-name',default='CynicalCloth15');p.add_argument('--report-prefix',default='');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.fit).resolve();(out/'frames').mkdir(exist_ok=True)
    engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;proxy=bpy.data.objects[a.object];sim=next(m for m in proxy.modifiers if m.type=='CLOTH');cache=sim.point_cache
    proxy.hide_set(False);proxy.hide_render=True;proxy.display_type='WIRE';proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
    cache.use_disk_cache=True;cache.name=a.cache_name
    preview_first=int(scene.get('outfit_preview_first',1));edges=np.array([e.vertices[:] for e in proxy.data.edges]);basis=np.array([v.co[:] for v in proxy.data.vertices]);base_lengths=np.linalg.norm(basis[edges[:,0]]-basis[edges[:,1]],axis=1);initial=None;first=cache.frame_start;report={'frames':{},'sequential_simulation':True,'requested_frames':[first,a.last],'preview_first':preview_first,'render_step':a.render_step,'seconds_at_source_fps':max(0,a.last-preview_first+1)/30,'reference':'first simulated frame; base geometry metrics reported separately'};start=time.monotonic()
    visuals=[o for o in engine('import_export').model_meshes() if o.name!='达妮娅_mesh'];visibility={o:o.hide_viewport for o in visuals}
    for o in visuals:o.hide_viewport=True
    # Save cache configuration before writing disk frames: cache identity must
    # stay attached to this exact blend filename.
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True)
    for frame in range(first,a.last+1):
        scene.frame_set(frame);bpy.context.view_layer.update();ev=proxy.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();co=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',co);co=co.reshape(-1,3);ev.to_mesh_clear()
        if not np.isfinite(co).all() or np.abs(co).max()>20:raise RuntimeError(f'Cloth simulation exploded at {frame}')
        lengths=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1)
        if initial is None:initial=lengths.copy()
        ratios=lengths/np.maximum(initial,1e-6)
        if frame in (first,preview_first) or frame%30==0 or frame==a.last or frame in a.shots:
            base_ratios=lengths/np.maximum(base_lengths,1e-6)
            row={'edge_ratio_median':float(np.median(ratios)),'edge_ratio_p99':float(np.quantile(ratios,.99)),'edge_ratio_max':float(ratios.max()),'base_edge_ratio_p99':float(np.quantile(base_ratios,.99)),'base_edge_ratio_max':float(base_ratios.max()),'extension_from_base_p99_m':float(np.quantile(lengths-base_lengths,.99)),'bounds':[co.min(axis=0).tolist(),co.max(axis=0).tolist()],'cache_info':cache.info}
            report['frames'][str(frame)]=row
            print('CLOTH_FRAME',frame,json.dumps(row),flush=True)
            (out/(a.report_prefix+'simulation_progress.json')).write_text(json.dumps({'frame':frame,'elapsed_s':time.monotonic()-start}),encoding='utf-8')
        if frame in a.shots or (a.render_step>0 and frame>=preview_first and ((frame-preview_first)%a.render_step==0 or frame==a.last)):
            for o,v in visibility.items():o.hide_viewport=v
            bpy.context.view_layer.update()
            scene.render.filepath=str(out/'frames'/f'f{frame:04d}.png');bpy.ops.render.render(write_still=True)
            for o in visuals:o.hide_viewport=True
    if a.bake:
        assert a.last==cache.frame_end,'Cannot finalize an incomplete cache'
        with bpy.context.temp_override(scene=scene,object=proxy,active_object=proxy,point_cache=cache):bpy.ops.ptcache.bake_from_cache()
        report['cache_baked']=cache.is_baked
        assert cache.is_baked,'Cloth cache was not finalized'
    report['elapsed_s']=time.monotonic()-start;report['disk_cache']=cache.use_disk_cache
    (out/(a.report_prefix+'simulation_report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for o,v in visibility.items():o.hide_viewport=v
    proxy.hide_set(True);proxy.select_set(False);scene.frame_set(preview_first);bpy.context.view_layer.objects.active=None
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True)
    print('CLOTH_TRIAL_COMPLETE',json.dumps({'frames':a.last,'elapsed_s':report['elapsed_s'],'cache_baked':report.get('cache_baked',False)}),flush=True)


if __name__=='__main__':main()
