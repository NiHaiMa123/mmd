"""Sequential stock Cloth evaluation with actual full-head stopping checks.

This script observes native physics, caches and renders it. It implements no
dynamics, collision response, deformation correction or temporal filtering.
"""
import argparse,json,sys,time,traceback
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,crosses
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--last',type=int,default=360)
p.add_argument('--preview-frame',type=int)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.candidate);base=ROOT.parent/'work/headswap_xl_codex';start=time.monotonic()
def status(stage,**kw):
    data=dict(stage=stage,elapsed_s=time.monotonic()-start,**kw);tmp=out/'simulation_status.tmp.json';tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'simulation_status.json');print('STOCK_CLUMP_SIM',json.dumps(data,ensure_ascii=False),flush=True)
def evaluated(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    try:
        co=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',co);co=co.reshape(-1,3);mw=np.array(ev.matrix_world);co=co@mw[:3,:3].T+mw[:3,3]
        vi=np.array([x.value for x in me.attributes['SourceVertexID'].data],np.int32)
        return co,vi
    finally:ev.to_mesh_clear()
def normal_render(frame):
    folder=out/'normal_evidence';folder.mkdir(exist_ok=True);prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.filepath=str(folder/f'完整角色_f{frame:04d}.png')
    bpy.ops.render.render(write_still=True);return s.render.filepath
try:
    assert not (out/'simulation_status.json').exists(),'Do not duplicate a simulation job'
    config=json.loads((out/'configuration.json').read_text('utf8'));assert len(config['clumps'])==27
    assert not config['clumps_with_coverage_failure'],config['clumps_with_coverage_failure']
    assert not config['root_attachment_review_failures'],config['root_attachment_review_failures']
    if config.get('regular_open_ribbons') or config.get('geometric_volume'):
        rest_audit=json.loads((out/'rest_audit/initial_contact_analysis.json').read_text('utf8'))
        assert rest_audit['self_audit_complete'] and rest_audit['same_clump_crossing_pairs']==0 and rest_audit['between_clump_crossing_pairs']==0 and rest_audit['proxy_body_crossing_pairs']==0 and rest_audit['free_vertices_inside_configured_body_margin']==0,'Initial simulation mesh/contact clearance must pass before advancing physics'
    if config.get('geometric_volume'):
        topology=json.loads((out/'geometric_topology.json').read_text('utf8'))
        assert all(c['rooted'] for c in topology['components']),'Every physical component must have real head attachment'
    if config.get('manifold_clean_asset'):
        assert rest_audit['moving_face_samples_inside_body_margin']==0,'Proxy face interiors violate the initial skin envelope'
        assert rest_audit['nonlocal_self_vertex_face_pairs_inside_margin']==0,'Initial nonlocal self-contact margin failed'
        assert rest_audit['boundary_edges']==0 and rest_audit['nonmanifold_edges']==0,'Closed manifold proxy required'
        initial_review=json.loads((out/'initial_review.json').read_text('utf8'))
        assert initial_review['actual_display_initial_pass'],'Actual complete displayed hair must pass before dynamics'
        assert initial_review.get('initial_candidate_pass',False),'Complete initial review, including face-level skin padding, must pass'
        skin_rest=json.loads((out/'proxy_skin_rest_padding_audit.json').read_text('utf8'))
        assert skin_rest['complete'] and skin_rest['padding_overlap_pairs']==0,'Exact initial proxy/skin triangle padding must pass'
        native_rest=json.loads((out/'native_rest_padding_audit.json').read_text('utf8'))
        assert native_rest['complete'] and native_rest['padding_overlap_pairs']==0,'Native triangle-pair padding audit must pass before dynamics'
    engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=config['blend'],use_scripts=False,load_ui=False)
    s=bpy.context.scene;s.frame_start=1;s.frame_end=a.last
    actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();display=bpy.data.objects[s['HairDisplayObject']];proxy=bpy.data.objects['HairProxy_全头共享几何体积' if config.get('geometric_volume') else 'HairProxy_27束连续笼体']
    cloth=next(md for md in proxy.modifiers if md.type=='CLOTH');pc=cloth.point_cache;assert not pc.is_baked
    assert sum(md.type=='SURFACE_DEFORM' and md.is_bound for md in display.modifiers)==(1 if config.get('geometric_volume') else 27)
    pc.frame_start=1;pc.frame_end=a.last;pc.use_disk_cache=True
    path=out/'完整角色_原生分束代理_连续物理待验收.blend';s.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.object.select_all(action='DESELECT');proxy.hide_set(False);proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
    actor.data.calc_loop_triangles();tri=np.array([t.vertices[:] for t in actor.data.loop_triangles]);classes=np.array([actor.data.attributes['SurfaceClass'].data[t.polygon_index].value for t in actor.data.loop_triangles])
    hairfaces=tri[classes==3];skinfaces=tri[np.isin(classes,[1,2])];assert len(hairfaces)==40181 and len(skinfaces)==50428
    z=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');ids=z['ids'];hard=z['same_true_hard_root_mask'];edges=z['edges'];rest=z['source_edge_lengths'];valid=rest>.0005
    rows=[];head0=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);inv0=np.linalg.inv(head0)
    def full():
        result=np.full((len(actor.data.vertices),3),np.nan);co,vi=evaluated(actor);result[vi]=co;co,vi=evaluated(display);result[vi]=co;return result
    initial=full()[ids];initial_local=initial@inv0[:3,:3].T+inv0[:3,3];rootlocal=initial_local[hard]
    export=base/'fullhair_repro_20261030/input_body_aware'
    expected_skin=np.load(export/'body.npy',mmap_mode='r');skin_ids=np.load(export/'skin_ids.npy')
    chain_labels=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')['chain_labels']
    proxy_rest=np.load(out/'clump_proxy_rest.npz');pf=proxy_rest['triangles']
    proxy_edges=np.unique(np.sort(np.concatenate([pf[:,[0,1]],pf[:,[1,2]],pf[:,[2,0]]]),axis=1),axis=0)
    initial_proxy=coords(proxy);proxy_edge_lengths=np.linalg.norm(initial_proxy[proxy_edges[:,0]]-initial_proxy[proxy_edges[:,1]],axis=1)
    proxy_valid=proxy_edge_lengths>.0005
    def audit(frame):
        co=full();points=[Vector(v) for v in co];hbvh=BVHTree.FromPolygons(co.tolist(),hairfaces.tolist(),all_triangles=True);sbvh=BVHTree.FromPolygons(co.tolist(),skinfaces.tolist(),all_triangles=True)
        hits=[]
        for hi,si in hbvh.overlap(sbvh):
            hf=hairfaces[hi];sf=skinfaces[si]
            if set(hf)&set(sf):continue
            if crosses([points[i] for i in hf],[points[i] for i in sf]):hits.append(dict(hair_triangle=int(hi),skin_triangle=int(si),position=co[hf].mean(0).tolist()))
        x=co[ids];ratio=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1)[valid]/rest[valid];head=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);expected=rootlocal@head[:3,:3].T+head[:3,3]
        row=dict(frame=frame,crossings=len(hits),witnesses=hits[:30],edge_ratio_min=float(ratio.min()),edge_ratio_max=float(ratio.max()),edge_ratio_p01=float(np.quantile(ratio,.01)),edge_ratio_p99=float(np.quantile(ratio,.99)),root_error_m=float(np.linalg.norm(x[hard]-expected,axis=1).max()))
        invhead=np.linalg.inv(head);local=x@invhead[:3,:3].T+invhead[:3,3];motion=np.linalg.norm(local-initial_local,axis=1)
        row.update(body_error_m=float(np.max(np.abs(co[skin_ids]-expected_skin[(frame-1)*8]))),
            head_local_motion_p95_m=float(np.quantile(motion,.95)),head_local_motion_max_m=float(motion.max()),
            clump_head_local_motion_p95_m=[float(np.quantile(motion[chain_labels==ci],.95)) for ci in range(27)])
        pcworld=coords(proxy);pr=np.linalg.norm(pcworld[proxy_edges[:,0]]-pcworld[proxy_edges[:,1]],axis=1)[proxy_valid]/proxy_edge_lengths[proxy_valid]
        row.update(proxy_edge_ratio_min=float(pr.min()),proxy_edge_ratio_max=float(pr.max()),proxy_edge_ratio_p99=float(np.quantile(pr,.99)))
        if config.get('physics_binding_target'):
            relay=bpy.data.objects[config['physics_binding_target']]
            row['native_relay_error_m']=float(np.max(np.abs(coords(relay)-pcworld/config['simulation_scale'])))
            assert row['native_relay_error_m']<5e-6,'Native local-space relay mismatch'
        evaluated_cloth=proxy.evaluated_get(bpy.context.evaluated_depsgraph_get()).modifiers[cloth.name]
        sr=evaluated_cloth.solver_result
        if sr is not None:
            flags=sorted(sr.status) if isinstance(sr.status,set) else [str(sr.status)]
            row['native_solver_result']=dict(status=flags,max_error=sr.max_error,avg_error=sr.avg_error,
                min_error=sr.min_error,max_iterations=sr.max_iterations,avg_iterations=sr.avg_iterations,min_iterations=sr.min_iterations)
        rows.append(row);(out/'sequential_surface_checks.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8');return row
    failure=None
    for frame in range(1,a.last+1):
        s.frame_set(frame);bpy.context.view_layer.update();physical=coords(proxy)
        if not np.all(np.isfinite(physical)) or np.max(np.abs(physical))>100:failure=dict(frame=frame,reason='Native physics diverged');break
        if config.get('manifold_clean_asset') or frame in (1,2,3) or frame%15==0 or frame>=301:
            row=audit(frame)
            if row['crossings'] or row['edge_ratio_p01']<.85 or row['edge_ratio_p99']>1.15 or row['edge_ratio_max']>1.5 or row['root_error_m']>.0001 or row['body_error_m']>5e-6 or row['proxy_edge_ratio_max']>1.5:
                failure=dict(reason='Actual complete hair crossed skin, stretched or lost roots',**row);break
        if frame==a.preview_frame:
            before_preview=full()[ids];preview_image=normal_render(frame)
            assert float(np.max(np.abs(full()[ids]-before_preview)))<5e-6,'Preview changed native physics state'
            status('NORMAL_COMPLETE_CHARACTER_KEYFRAME_RENDERED',frame=frame,image=preview_image)
        if frame%5==0 or frame<=3:status('SEQUENTIAL_NATIVE_CLOTH',frame=frame,last=a.last)
    last=frame;s.frame_end=last
    last_hair=full()[ids];np.savez_compressed(out/'native_last_frame.npz',frame=last,proxy=physical/config.get('simulation_scale',1.),native_proxy_world=physical,hair=last_hair)
    # Freeze the native computed cache, rather than calculating another run.
    pc.frame_end=last
    with bpy.context.temp_override(scene=s,object=proxy,active_object=proxy,point_cache=pc):bpy.ops.ptcache.bake_from_cache()
    cache_baked=bool(pc.is_baked);assert float(np.max(np.abs(full()[ids]-last_hair)))<5e-6,'Cache freeze changed the computed hair';bpy.ops.wm.save_as_mainfile(filepath=str(path))
    if failure:
        status('STOPPED_ACTUAL_HAIR_FAILURE',frame=last,failure=failure,blend=str(path),native_cache_baked=cache_baked)
        np.save(out/f'failure_full_hair_f{last:04d}.npy',full()[ids]);image_path=normal_render(last)
        result=dict(status='STOPPED_ACTUAL_HAIR_FAILURE',accepted=False,frames_simulated=[1,last],failure=failure,blend=str(path),normal_image=image_path,native_cache_baked=cache_baked,eleven_second_validated=False,physics_backend='Unmodified Blender Cloth',complete_hair_vertices=len(ids))
        (out/'simulation_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');status('STOPPED_ACTUAL_HAIR_FAILURE_EVIDENCE_SAVED',**result)
    else:
        assert cache_baked,'Native sequential cache was not frozen'
        status('NATIVE_FRAMES_COMPUTED_REQUIRES_REOPEN_DENSE_AND_VISUAL_REVIEW',frames_computed=[1,last],blend=str(path),native_cache_baked=cache_baked)
except BaseException as exc:
    status('SCRIPT_ERROR_REPAIR_AUTONOMOUSLY',error=repr(exc),traceback=traceback.format_exc());raise
