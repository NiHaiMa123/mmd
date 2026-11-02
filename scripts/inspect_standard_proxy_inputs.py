"""Read-only full-head asset inspection for stock Cloth/Surface Deform."""
import json,sys,time
from pathlib import Path
import bpy,bmesh,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
P=ROOT.parent/'work/headswap_xl_codex';out=P/'standard_proxy_20261031/inspection';out.mkdir(parents=True,exist_ok=True)
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=str(P/'jiggle_physics_20261031/candidate10/完整角色_Jiggle配置_未烘焙.blend'),load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update();m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=m.find_armature()
z=np.load(P/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');ids=z['ids'];hard=z['same_true_hard_root_mask'];hair=coords(m)[ids]
lookup={int(v):i for i,v in enumerate(ids)};faces=np.array([[lookup[int(i)] for i in f] for f in z['triangles']],np.int32) if z['triangles'].max()>=len(ids) else z['triangles']
gn={g.index:g.name for g in m.vertex_groups};config=json.loads((P/'jiggle_physics_20261031/candidate10/configuration.json').read_text('utf8'));names={r['name'] for r in config['hair_bones']}
roots={}
for n in names:
    b=arm.pose.bones[n]
    while b.parent and b.parent.name in names:b=b.parent
    roots[n]=b.name
chain_names=sorted(set(roots.values()));ci={n:i for i,n in enumerate(chain_names)}
weights=np.zeros((len(ids),len(chain_names)),np.float32)
for j,i in enumerate(ids):
    for g in m.data.vertices[int(i)].groups:
        if gn[g.group] in roots:weights[j,ci[roots[gn[g.group]]]]+=g.weight
labels=np.argmax(weights,axis=1);labels[np.max(weights,axis=1)<1e-5]=-1
parent=list(range(len(ids)))
def find(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
edges=[]
for e in m.data.edges:
    a,b=map(int,e.vertices)
    if a in lookup and b in lookup:
        a,b=lookup[a],lookup[b];edges.append((a,b));parent[find(a)]=find(b)
comp=np.array([find(i) for i in range(len(ids))]);rows=[]
for c in sorted(set(comp)):
    sel=comp==c;u,count=np.unique(labels[sel],return_counts=True);rows.append(dict(count=int(sel.sum()),hard=int(hard[sel].sum()),chains={str(int(i)):int(n) for i,n in zip(u,count)},bbox=np.ptp(hair[sel],axis=0).tolist()))
basis=np.array([v.co[:] for v in m.data.shape_keys.key_blocks[0].data])[ids]
np.savez_compressed(out/'inputs.npz',ids=ids,hard=hard,world=hair,basis=basis,faces=faces,edges=edges,chain_weights=weights,chain_labels=labels,components=comp,head_matrix=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix))
report=dict(chains=[dict(name=n,vertices=int((labels==i).sum()),hard=int(hard[labels==i].sum()),bones=sorted(k for k,v in roots.items() if v==n)) for i,n in enumerate(chain_names)],static_vertices=int((labels<0).sum()),nonhard_static=int(((labels<0)&~hard).sum()),components=rows,hair_vertices=len(ids),hair_faces=len(faces),source_keys=len(m.data.shape_keys.key_blocks))
(out/'inputs.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('INPUT_INSPECTION',json.dumps({k:v for k,v in report.items() if k!='components'},ensure_ascii=False),flush=True)
