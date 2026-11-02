"""Read-only separation of classic Cloth strain and display transfer strain."""
import argparse,json,sys,struct
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run)
r=json.loads((run/'result.json').read_text('utf8'));setup=json.loads((run/'setup.json').read_text('utf8'));prepared=json.loads((Path(setup['prepared']).parent/'setup.json').read_text('utf8'));last=r['frames'][1]
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];base=repo.parent/'work/headswap_xl_codex';d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');exp=base/'fullhair_repro_20261030/input_body_aware';skin=np.load(exp/'skin_ids.npy');body=np.load(exp/'body.npy',mmap_mode='r')
s.frame_set(1);bpy.context.view_layer.update();co0=coords(actor);p0={q['proxy']:coords(bpy.data.objects[q['proxy']]) for q in prepared['proxies']}
s.frame_set(last);bpy.context.view_layer.update();co=coords(actor);proxy_rows=[]
for row in prepared['proxies']:
 ob=bpy.data.objects[row['proxy']];initial=p0[ob.name];current=coords(ob);edges=np.array([e.vertices[:] for e in ob.data.edges]);length=np.linalg.norm(initial[edges[:,0]]-initial[edges[:,1]],axis=1);now=np.linalg.norm(current[edges[:,0]]-current[edges[:,1]],axis=1);valid=length>.001
 proxy_rows.append(dict(chain=row['chain'],edge_ratio_p01_p99=np.quantile(now[valid]/length[valid],[.01,.99]).tolist(),maximum_edge_ratio=float((now[valid]/length[valid]).max()),maximum_edge_extension_m=float((now-length).max()),valid_pin_group=next(m for m in ob.modifiers if m.type=='CLOTH').settings.vertex_group_mass=='HairRootPinGroup'))
edges=d['ids'][d['edges']];l0=np.linalg.norm(co0[edges[:,0]]-co0[edges[:,1]],axis=1);l1=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1);extension=l1-l0
label=next(j for j,row in enumerate(prepared['proxies']) if row['chain']==r['stop']['stretched_chains'][0]['chain'])
mask=(d['chain_labels'][d['edges'][:,0]]==label)&(d['chain_labels'][d['edges'][:,1]]==label)&(l0>.001)
index=int(np.flatnonzero(mask)[np.argmax(extension[mask])]);pair=edges[index]
def screen(point):
 v=world_to_camera_view(s,s.camera,Vector(point));return [float(v.x*1920),float((1-v.y)*1080)]
bad=np.unique(edges[mask & (l1>l0*1.5) & (extension>.005)])
record=dict(frame=last,seconds=(last-1)/30,reason=r['stop']['reason'],display_chain=prepared['proxies'][label]['chain'],source_edge=pair.tolist(),initial_edge_m=float(l0[index]),stopped_edge_m=float(l1[index]),edge_extension_m=float(extension[index]),edge_ratio=float(l1[index]/l0[index]),edge_pixels=[screen(co[int(i)]) for i in pair],bad_display_vertex_pixels=[screen(co[int(i)]) for i in bad],proxy=proxy_rows[label],all_proxy_results=proxy_rows,all_27_native_pin_groups_valid=all(q['valid_pin_group'] for q in proxy_rows),maximum_recorded_pin_error_m=max(q['maximum_native_pin_error_m'] for q in r['samples']),body_error_m=float(np.abs(co[skin]-body[(last-1)*8]).max()),reopened_global_edge_ratio_p01_p99=np.quantile(l1[l0>.001]/l0[l0>.001],[.01,.99]).tolist(),new_simulation_started=False)
caches=[]
for path in sorted((run/'cache').glob('*.pc2')):
 with path.open('rb') as f:magic,version,points,start,step,samples=struct.unpack('<12siiffi',f.read(32))
 assert magic==b'POINTCACHE2\0' and path.stat().st_size==32+points*samples*12
 if path.name.startswith('ClassicHair_'):assert samples==last
 caches.append(dict(path=str(path),points=points,samples=samples,start=start,step=step))
record['verified_cache_headers']=caches
(run/'stopped_review.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:v for k,v in record.items() if k not in ['all_proxy_results','verified_cache_headers','bad_display_vertex_pixels']},ensure_ascii=False),flush=True)
