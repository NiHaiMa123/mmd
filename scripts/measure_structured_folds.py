"""Compare added geometric folds relative to each cloth island's rest form."""
import sys,json
from pathlib import Path
from collections import defaultdict
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();out=ROOT/'outputs/cynical_cloth15/structured_v2';report={}
def coords(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();a=np.array([v.co[:] for v in me.vertices]);ev.to_mesh_clear();return a
def fold_angles(co,faces,pairs):
    tri=np.array(faces);normals=np.cross(co[tri[:,1]]-co[tri[:,0]],co[tri[:,2]]-co[tri[:,0]]);normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12);return np.degrees(np.arccos(np.clip(np.sum(normals[pairs[:,0]]*normals[pairs[:,1]],axis=1),-1,1)))
for label,folder in [('old',ROOT/'outputs/cynical_cloth15/trial3'),('repaired',out)]:
    bpy.ops.wm.open_mainfile(filepath=str(folder/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);proxy=bpy.data.objects['ClothSimulationSurface'];target=bpy.data.objects.get('ClothShapePreservingTarget') or proxy;mesh=proxy.data;faces=[tuple(f.vertices) for f in mesh.polygons];vf=defaultdict(list)
    for f in mesh.polygons:
        for i in f.vertices:vf[i].append(f.index)
    left=set(range(len(faces)));regions={}
    while left:
        todo=[left.pop()];ids=set();polys=set()
        while todo:
            fi=todo.pop();polys.add(fi)
            for i in faces[fi]:
                ids.add(i)
                for j in vf[i]:
                    if j in left:left.remove(j);todo.append(j)
        z0=min(mesh.vertices[i].co.z for i in ids);z1=max(mesh.vertices[i].co.z for i in ids);name='sleeve' if z0<.65 else 'main_skirt' if z1>1.05 else 'lower_skirt';regions.setdefault(name,set()).update(polys)
    adjacent=defaultdict(list)
    for fi,f in enumerate(faces):
        for a,b in zip(f,f[1:]+f[:1]):adjacent[tuple(sorted((a,b)))].append(fi)
    pairs=np.array([p for p in adjacent.values() if len(p)==2]);base=np.array([v.co[:] for v in mesh.vertices]);rest=fold_angles(base,faces,pairs);first=int(bpy.context.scene.get('outfit_preview_first',1));rows={}
    for source in (270,330):
        bpy.context.scene.frame_set(first+source-1);bpy.context.view_layer.update();angles=fold_angles(coords(target),faces,pairs);row={}
        for name,polys in regions.items():
            selection=np.array([a in polys and b in polys for a,b in pairs]);extra=np.abs(angles[selection]-rest[selection]);row[name]={'edges':int(selection.sum()),'extra_fold_median_deg':float(np.median(extra)),'extra_fold_p90_deg':float(np.quantile(extra,.9))}
        rows[str(source)]=row
    report[label]=rows
(out/'fold_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('FOLD_COMPARISON',json.dumps(report),flush=True)
