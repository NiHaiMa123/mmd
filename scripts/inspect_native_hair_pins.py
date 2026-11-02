import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/hair_tests_v2/native_xpbd_probe';bpy.ops.wm.open_mainfile(filepath=str(root/'NativeXPBD_Hair_Probe.blend'),load_ui=False,use_scripts=False)
sim=bpy.data.objects['HairContact_XPBD_Surface'];report={};scene=bpy.context.scene
for f in (0,1,2):
 scene.frame_set(f);bpy.context.view_layer.update();ev=sim.evaluated_get(bpy.context.evaluated_depsgraph_get());data=ev.to_mesh();attrs={}
 for attr in data.attributes:
  if any(s in attr.name.lower() for s in ('pin','mass','selection','compliance','sourcevertex','sim:prop:cloth')):
   values=[]
   if attr.data_type in ('FLOAT','INT','BOOLEAN'):values=[getattr(d,'value',None) for d in attr.data]
   attrs[attr.name]={'domain':attr.domain,'type':attr.data_type,'count':len(attr.data),'min':min(values) if values else None,'max':max(values) if values else None,'nonzero':sum(bool(v) for v in values)}
 positions=np.array([ev.matrix_world@v.co for v in data.vertices]);source=bpy.data.objects['HairContact_SourceReference'].evaluated_get(bpy.context.evaluated_depsgraph_get());sd=source.to_mesh();source_co=np.array([source.matrix_world@v.co for v in sd.vertices]);ids=np.array([d.value for d in data.attributes['HairSourceVertex'].data]);pins=np.array([d.value for d in data.attributes['HairRootPin'].data])>.5
 attrs['PIN_ERROR']={'max_m':float(np.linalg.norm(positions[pins]-source_co[ids[pins]],axis=1).max())};source.to_mesh_clear()
 main=bpy.data.objects['东雪莲x达妮娅_素体'];mapping=main.data.attributes['HairContactSimIndex'];attrs['worst_edge_pins']=[(i,mapping.data[i].value,float(data.attributes['HairRootPin'].data[mapping.data[i].value].value)) for i in (61613,61621,61601,61619)]
 report[str(f)]=attrs;ev.to_mesh_clear()
report['bakes']=[]
for mod in sim.modifiers:
 if mod.type=='NODES':
  for bake in mod.bakes:report['bakes'].append({p.identifier:str(getattr(bake,p.identifier,None)) for p in bake.bl_rna.properties if p.identifier!='rna_type'})
(root/'pins_inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('PIN_ATTRS',json.dumps(report,ensure_ascii=False),flush=True)
