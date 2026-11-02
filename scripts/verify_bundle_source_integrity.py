"""Case-level source hashes and protected body replay for a cached bundle."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.track import fcurves
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run);report=json.loads((run/('assembly_report.json' if (run/'assembly_report.json').exists() else 'report.json')).read_text('utf8'));candidate=Path(report.get('candidate',str(run/'SingleBundle_CachedCandidate_NotAccepted.blend')));motion=np.load(run/('dense_motion.npz' if (run/'dense_motion.npz').exists() else 'bundle_motion.npz'));ids=set(motion['ids'].tolist());engine('import_export').ensure_mmd_tools();frames=[1,200,218,240,247.5,256,285,321,350,375,450]
def actions():
 result={}
 for action in bpy.data.actions:
  value=[(c.data_path,c.array_index,[(list(k.co),list(k.handle_left),list(k.handle_right),k.interpolation) for k in c.keyframe_points]) for c in fcurves(action)]
  result[action.name]=hashlib.sha256(json.dumps(value).encode()).hexdigest()
 return result
def geometry_hash(mesh):
 h=hashlib.sha256();co=np.empty(len(mesh.data.vertices)*3,dtype=np.float32);mesh.data.vertices.foreach_get('co',co);h.update(co.tobytes());loops=np.empty(len(mesh.data.loops),dtype=np.int32);mesh.data.loops.foreach_get('vertex_index',loops);h.update(loops.tobytes())
 for key in mesh.data.shape_keys.key_blocks:
  key.data.foreach_get('co',co);h.update(key.name.encode());h.update(co.tobytes())
 for v in mesh.data.vertices:
  for g in v.groups:h.update(f'{v.index}:{mesh.vertex_groups[g.group].name}:{g.weight:.9g};'.encode())
 return h.hexdigest()
states=[]
for file in (report['source'],str(candidate)):
 bpy.ops.wm.open_mainfile(filepath=file,load_ui=False,use_scripts=False);mesh=bpy.data.objects['东雪莲x达妮娅_素体'];outside=sorted(set(range(len(mesh.data.vertices)))-ids);poses={}
 for frame in frames:
  bpy.context.scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();poses[frame]=coords(mesh)[outside]
 states.append({'actions':actions(),'geometry':geometry_hash(mesh),'poses':poses,'shape_key_count':len(mesh.data.shape_keys.key_blocks)})
source,current=states;assert all(current['actions'].get(n)==h for n,h in source['actions'].items());assert source['geometry']==current['geometry'];error=max(float(np.max(np.abs(source['poses'][f]-current['poses'][f]))) for f in frames);assert error<1e-8,error
result={'status':'CACHED_BUNDLE_SOURCE_GEOMETRY_ACTIONS_AND_BODY_PRESERVED','source':report['source'],'candidate':str(candidate),'source_actions_hash_match':True,'source_action_count':len(source['actions']),'rest_mesh_topology_weights_and_shape_keys_hash_match':True,'shape_key_count':source['shape_key_count'],'unselected_vertices_peak_error_m':error,'checked_frames':frames,'protected_frames_checked':[256,285,321],'whole_hair_accepted':False}
(run/'source_integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('BUNDLE_INTEGRITY',json.dumps(result),flush=True)
