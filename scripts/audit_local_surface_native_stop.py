"""Read-only audit: repaired fringe versus the newly failing long tail."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p=argparse.ArgumentParser();p.add_argument('--run',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run)
r=json.loads((run/'result.json').read_text('utf8'));last=r['frames'][1]
base=repo.parent/'work/headswap_xl_codex'
d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
skin=np.load(base/'fullhair_repro_20261030/input_body_aware/skin_ids.npy')
bf=np.load(base/'fullhair_repro_20261030/input_body_aware/body_faces.npy')
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];rows=[]
for f in sorted(set([233,301,316,331,346,361,376,last])):
 if f>last:continue
 s.frame_set(f);bpy.context.view_layer.update();co=coords(actor);field=ClosedColliderField(co[skin],bf);signed,_=field(co[d['ids']]);chains=[]
 for label in [5,26]:
  mask=d['chain_labels']==label;dist=signed.copy();dist[~mask]=1.
  contact=embedded_patch_metrics(co[d['ids']],dist,d['edges'],limit_m=.05)
  faces=d['faces'][np.all(mask[d['faces']],axis=1)];centers=co[d['ids']][faces].mean(1);cd,_=field(centers)
  proxy=bpy.data.objects['ClassicHair_'+meta['chains'][label]['name']];q=coords(proxy);pd,_=field(q)
  edges=np.array([e.vertices[:] for e in proxy.data.edges]);pc=embedded_patch_metrics(q,pd,edges,limit_m=.05)
  chains.append(dict(chain=meta['chains'][label]['name'],actual_inside_vertices=contact['inside_vertices'],
    actual_span_cm=contact['maximum_patch_extent_m']*100,actual_depth_cm=contact['maximum_depth_m']*100,
    actual_inside_face_centers=int((cd<-.0001).sum()),proxy_inside_vertices=pc['inside_vertices'],
    proxy_span_cm=pc['maximum_patch_extent_m']*100,proxy_depth_cm=pc['maximum_depth_m']*100))
 rows.append(dict(frame=f,original_seconds=(f-1)/30,chains=chains))
report=dict(new_simulation_started=False,geometry_edited=False,frames=rows,
 left_fringe_native_surface_binding=actor.modifiers['Native_SurfaceDeform_FrontHair5-1.L'].show_viewport)
(run/'fringe_and_tail_stop_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
