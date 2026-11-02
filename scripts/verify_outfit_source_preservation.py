"""Reload comparison for source geometry, morphs, UVs, skin pose and action."""
import argparse,json,hashlib,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--candidate',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);engine('import_export').ensure_mmd_tools()
def digest(obj):
    h=hashlib.sha256();co=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',co);h.update(co.tobytes())
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',co);h.update(key.name.encode());h.update(co.tobytes())
    for uv in obj.data.uv_layers:
        h.update(uv.name.encode());values=np.empty(len(uv.data)*2,dtype=np.float32);uv.data.foreach_get('uv',values);h.update(values.tobytes())
    h.update(str([(m.name if m else '') for m in obj.data.materials]).encode());h.update(str([(tuple(p.vertices),p.material_index) for p in obj.data.polygons]).encode());return h.hexdigest()
def action_digest(action):
    h=hashlib.sha256()
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:h.update(str((fc.data_path,fc.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in fc.keyframe_points])).encode())
    return h.hexdigest()
def body_positions():
    bpy.context.scene.frame_set(325);obj=bpy.data.objects['达妮娅_mesh'];ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();co=np.array([v.co[:] for v in mesh.vertices]);ev.to_mesh_clear();return co
bpy.ops.wm.open_mainfile(filepath=str(Path(a.baseline).resolve()),load_ui=False,use_scripts=False);base={o.name:digest(o) for o in engine('import_export').model_meshes()};poses=body_positions();original=action_digest(bpy.data.actions['シニカルナイトプラン_bone']);bpy.ops.wm.open_mainfile(filepath=str(Path(a.candidate).resolve()),load_ui=False,use_scripts=False);same={name:digest(bpy.data.objects[name])==value for name,value in base.items()};error=float(np.max(np.abs(body_positions()-poses)));preserved=action_digest(bpy.data.actions['シニカルナイトプラン_bone'])==original;report={'source_mesh_morph_uv_topology_materials':same,'source_mesh_count':len(base),'body_evaluated_position_max_error_m':error,'original_action_preserved':preserved,'status':'SOURCE_DATA_PRESERVED' if all(same.values()) and error<1e-7 and preserved else 'SOURCE_DATA_CHANGED'};Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
