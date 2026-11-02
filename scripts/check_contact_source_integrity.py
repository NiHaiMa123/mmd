import sys,json,hashlib
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.track import fcurves
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';name='东雪莲x达妮娅_素体'
def action_digest(action):
 rows=[(c.data_path,c.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in c.keyframe_points]) for c in fcurves(action)]
 return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
def fingerprint(path):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False);mesh=bpy.data.objects[name];d=mesh.data;keys=d.shape_keys.key_blocks;h=hashlib.sha256();buffer=np.empty(len(d.vertices)*3,dtype=np.float32)
 for key in keys:key.data.foreach_get('co',buffer);h.update(key.name.encode('utf8'));h.update(buffer.tobytes())
 weights=hashlib.sha256(json.dumps([(v.index,[(mesh.vertex_groups[g.group].name,g.weight) for g in v.groups]) for v in d.vertices],ensure_ascii=False).encode()).hexdigest()
 topo=hashlib.sha256(json.dumps([(tuple(p.vertices),p.material_index) for p in d.polygons]).encode()).hexdigest()
 return {'action':action_digest(bpy.data.actions['シニカルナイトプラン_bone']),'shape_keys':h.hexdigest(),'shape_key_count':len(keys),'weights':weights,'topology':topo,'vertices':len(d.vertices),'polygons':len(d.polygons)}
source=ROOT.parent/'work/headswap_xl_codex/animation15_20261028/东雪莲_固定镜头_15秒.blend';candidate=root/'body_track/BodyContact_UpperBodyCandidate.blend';a=fingerprint(source);b=fingerprint(candidate);result={'reference':str(source),'candidate':str(candidate),'reference_fingerprints':a,'candidate_fingerprints':b,'all_equal':a==b}
(root/'body_track/upper_body_source_integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('SOURCE_INTEGRITY',a==b,flush=True);assert a==b,result
