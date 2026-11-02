import bpy,sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
out=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input';r=json.loads((out/'export_complete.json').read_text('utf8'));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['source_blend'],load_ui=False,use_scripts=False);p=json.loads(Path(r['rig_profile']).read_text('utf8'));skin,faces,meta=build_exact_skin_topology(bpy.data.objects[p['mesh']],bpy.data.objects[p['armature']],p,triangulate=True,include_face_sources=True);np.testing.assert_array_equal(skin,np.load(out/'skin_ids.npy'));np.testing.assert_array_equal(faces,np.load(out/'body_faces.npy'));flag=~np.array(meta.pop('closure_face_mask'));np.save(out/'real_body_faces.npy',flag.astype(np.int32));(out/'skin_face_provenance.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');print('REAL_SKIN_FACES',int(flag.sum()),'CLOSURE_FACES',int((~flag).sum()),flush=True)
