"""Read-only decomposition of already-cached frame 1->2 strain."""
import argparse,json,numpy as np
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--candidate');args=parser.parse_args()
base=Path(__file__).resolve().parents[2]/'work/headswap_xl_codex';p=Path(args.candidate) if args.candidate else base/'standard_proxy_20261031/clumps07';out=p/('stopped_analysis' if args.candidate else 'bottleneck_analysis');out.mkdir(exist_ok=True)
initial_path=p/'initial_display_audit/hair_world_1.npy'
if not initial_path.exists():initial_path=p/'audit_stopped/hair_world_1.npy'
rest=np.load(p/'clump_proxy_rest.npz');last=np.load(p/'native_last_frame.npz');z=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');initial=np.load(initial_path);hair=last['hair'];edges=z['edges'];labels=rest['source_clump_labels'];hard=z['same_true_hard_root_mask'];config=json.loads((p/'configuration.json').read_text('utf8'))
def stats(ratio):
    return dict(count=len(ratio),min=float(ratio.min()),p01=float(np.quantile(ratio,.01)),p50=float(np.median(ratio)),p99=float(np.quantile(ratio,.99)),max=float(ratio.max()),above_1_2=int((ratio>1.2).sum()),above_1_5=int((ratio>1.5).sum()),above_2=int((ratio>2).sum())) if len(ratio) else dict(count=0)
l1=np.linalg.norm(initial[edges[:,0]]-initial[edges[:,1]],axis=1);l2=np.linalg.norm(hair[edges[:,0]]-hair[edges[:,1]],axis=1);valid=z['source_edge_lengths']>.0005;ratio=l2/np.maximum(l1,1e-20)
same=labels[edges[:,0]]==labels[edges[:,1]];fixed=hard[edges[:,0]]|hard[edges[:,1]]
rows=dict(all=stats(ratio[valid]),same_clump=stats(ratio[valid&same]),across_clump_or_static_boundary=stats(ratio[valid&~same]),same_dynamic_clump=stats(ratio[valid&same&~fixed]),fixed_to_dynamic=stats(ratio[valid&fixed&~(hard[edges[:,0]]&hard[edges[:,1]])]))
rows['comparison_frames']=[1,int(last['frame'])]
tri=rest['triangles'];pe=np.unique(np.sort(np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]),axis=1),axis=0);x=rest['vertices'];y=last['proxy'];pl1=np.linalg.norm(x[pe[:,0]]-x[pe[:,1]],axis=1);pl2=np.linalg.norm(y[pe[:,0]]-y[pe[:,1]],axis=1);pr=pl2/np.maximum(pl1,1e-20)
rows['physical_proxy_edges_above_half_mm']=stats(pr[pl1>.0005]);rows['physical_proxy_edges_above_50_microns']=stats(pr[pl1>.00005])
pi=np.flatnonzero(pl1>.0005)[np.argsort(pr[pl1>.0005])[-20:][::-1]]
rows['worst_physical_proxy_edges']=[dict(proxy_vertices=pe[i].tolist(),initial_length_mm=float(pl1[i]*1000),
    last_length_mm=float(pl2[i]*1000),step_ratio=float(pr[i]),pins=rest['pins'][pe[i]].astype(bool).tolist()) for i in pi]
bad=valid&(ratio>2);rows['display_edges_above_2_total']=int(bad.sum());rows['display_edges_above_2_across_boundaries']=int((bad&~same).sum());rows['display_edges_above_2_same_clump']=int((bad&same).sum())
per=[]
for i,clump in enumerate(config['clumps']):
    chosen=valid&(labels[edges[:,0]]==i)&(labels[edges[:,1]]==i)
    per.append(dict(name=clump['name'],display_same_clump_edges=stats(ratio[chosen]),proxy_edges=stats(pr[(rest['clump_ids'][pe[:,0]]==i)&(pl1>.0005)])))
rows['per_clump']=per
indices=np.flatnonzero(valid)[np.argsort(ratio[valid])[-20:][::-1]];rows['worst_display_edges']=[dict(edge_index=int(i),source_vertices=z['ids'][edges[i]].tolist(),clump_labels=labels[edges[i]].tolist(),initial_length_mm=float(l1[i]*1000),last_length_mm=float(l2[i]*1000),step_ratio=float(ratio[i])) for i in indices]
(out/'strain_decomposition.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:v for k,v in rows.items() if k not in ['per_clump','worst_display_edges','worst_physical_proxy_edges']},indent=2))
