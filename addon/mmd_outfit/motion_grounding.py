"""Non-deforming floor correction via a stationary top-level VMD root track.

Only that bone's records change. Other bone records and every trailing VMD
section are retained byte-for-byte, including expressions and IK switches.
"""
import hashlib
import math
from pathlib import Path
import struct

RECORD_SIZE=111


def split_vmd(data):
    if len(data)<54 or not data.startswith(b'Vocaloid Motion Data 0002'):
        raise ValueError('Expected a VMD 0002 file')
    count=struct.unpack_from('<I',data,50)[0]
    end=54+count*RECORD_SIZE
    if end>len(data): raise ValueError('Truncated VMD bone section')
    records=[data[54+i*RECORD_SIZE:54+(i+1)*RECORD_SIZE] for i in range(count)]
    return data[:50],records,data[end:]


def bone_name(record):
    return record[:15].split(b'\0',1)[0].decode('cp932',errors='replace')


def floor_lifts(minima,clearance=.0005,floor_z=0.,max_lift=.03,radius=6):
    if not minima or not all(math.isfinite(x) for x in minima):
        raise ValueError('Finite per-frame shoe heights required')
    raw=[max(0.,floor_z+clearance-x) for x in minima]
    if max(raw)>max_lift:
        raise ValueError(f'Floor correction exceeds limit: {max(raw):.6f} > {max_lift:.6f} m')
    # A maximum envelope never undercuts a required lift and softens entry/exit.
    sigma=max(1.,radius/2)
    return [max(raw[j]*math.exp(-.5*((j-i)/sigma)**2) for j in range(max(0,i-radius),min(len(raw),i+radius+1)))
            for i in range(len(raw))]


def patch_root_track(data,lifts,vmd_direction,root_name='全ての親'):
    header,records,tail=split_vmd(data)
    roots=[r for r in records if bone_name(r)==root_name]
    if len(roots)!=1 or struct.unpack_from('<I',roots[0],15)[0]!=0:
        raise ValueError('Grounding currently requires one stationary root key at VMD frame 0')
    root=roots[0]
    if not lifts or not all(math.isfinite(v) and v>=0 for v in lifts): raise ValueError('Invalid root lifts')
    if len(vmd_direction)!=3 or not all(math.isfinite(v) for v in vmd_direction): raise ValueError('Invalid root translation direction')
    base=struct.unpack_from('<fff',root,19)
    interpolation=bytes([20]*8+[107]*8)+root[47+16:111]
    changed=[]
    for frame,lift in enumerate(lifts):
        location=[base[i]+vmd_direction[i]*lift for i in range(3)]
        changed.append(root[:15]+struct.pack('<Ifff',frame,*location)+root[31:47]+interpolation)
    retained=[r for r in records if bone_name(r)!=root_name]
    output=header+struct.pack('<I',len(retained)+len(changed))+b''.join(retained+changed)+tail
    h,new,t=split_vmd(output)
    assert h==header and t==tail
    assert [r for r in new if bone_name(r)!=root_name]==retained
    return output


def ground(mesh,arm,source,destination,materials,engine,*,reference_points,clearance=.0005,floor_z=0.,max_lift=.03,notify=None):
    import importlib
    import bpy
    import numpy as np
    from mathutils import Matrix,Vector
    from .preserved_shoe import exported_vertices
    ie=engine('import_export'); package=ie.ensure_mmd_tools()
    source=Path(source); destination=Path(destination)
    if source.resolve()==destination.resolve(): raise ValueError('Grounded motion must be a new file')
    data=source.read_bytes(); _,records,_=split_vmd(data)
    roots=[r for r in records if bone_name(r)=='全ての親']
    if len(roots)!=1 or struct.unpack_from('<I',roots[0],15)[0]!=0:
        raise ValueError('Animated or missing top-level root is not supported by this grounding mode')
    last=max(struct.unpack_from('<I',r,15)[0] for r in records)
    if last>20000: raise ValueError('Grounding motion exceeds 20000-frame limit')
    root=arm.pose.bones.get('全ての親')
    if root is None or root.parent is not None: raise ValueError('A top-level 全ての親 bone is required')
    ids=exported_vertices(mesh,reference_points,materials)
    shoe={};rigid_groups={}
    for i in ids:
        groups=[(mesh.vertex_groups[g.group].name,g.weight) for g in mesh.data.vertices[i].groups
                if g.weight>1e-6 and not mesh.vertex_groups[g.group].name.startswith('mmd_')]
        if len(groups)!=1 or abs(groups[0][1]-1)>1e-6:
            raise ValueError('Floor grounding requires every shoe vertex to have one rigid bone')
        rigid_groups.setdefault(groups[0][0],[]).append(i)
    for side in ('L','R'):
        if '足首D.'+side not in rigid_groups:raise ValueError('No single-ankle preserved shoes found on '+side)
    for name,values in rigid_groups.items():
        if not name.endswith(('.L','.R')):raise ValueError('Rigid footwear component has no left/right bone: '+name)
        side=name[-1]
        if name not in arm.data.bones: raise ValueError('Missing preserved-shoe bone '+name)
        parent=arm.pose.bones[name]
        while parent.parent: parent=parent.parent
        if parent!=root: raise ValueError('Both shoes must descend from the top-level root')
        if mesh.data.shape_keys:
            basis=mesh.data.shape_keys.key_blocks[0]
            for key in mesh.data.shape_keys.key_blocks[1:]:
                if any((key.data[i].co-basis.data[i].co).length>1e-7 for i in values):
                    maximum=max((key.data[i].co-basis.data[i].co).length for i in values)
                    raise ValueError(f'Grounding requires rigid shoes; morph {key.name!r} changes {side} by {maximum:.9f} m')
        bind=arm.data.bones[name].matrix_local.inverted()@arm.matrix_world.inverted()@mesh.matrix_world
        shoe[name]={'bone':name,'side':side,'points':np.asarray([tuple(bind@mesh.data.vertices[i].co) for i in values]),'vertices':len(values)}
    scene=bpy.context.scene; scene.frame_set(1)
    for obj in bpy.context.selected_objects: obj.select_set(False)
    arm.select_set(True); bpy.context.view_layer.objects.active=arm
    bpy.ops.mmd_tools.import_vmd(filepath=str(source),scale=.08,rename_bones=True,margin=0,log_level='ERROR')
    converter=importlib.import_module(package+'.core.vmd.importer').BoneConverter(root,.08)
    columns=[converter.convert_location(Vector(v)) for v in ((1,0,0),(0,1,0),(0,0,1))]
    local=Matrix((columns[0],columns[1],columns[2])).transposed()
    world=arm.matrix_world.to_3x3()@root.bone.matrix_local.to_3x3()@local
    direction=world.inverted()@Vector((0,0,1))
    def measure_frames(phase):
        hidden=[(obj,obj.hide_viewport) for obj in bpy.data.objects if obj.type=='MESH']
        heights=[]; sides=[]
        try:
            for obj,previous in hidden: obj.hide_viewport=True
            for frame in range(last+1):
                scene.frame_set(frame+1); bpy.context.view_layer.update()
                evaluated=arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
                row={'L':float('inf'),'R':float('inf')}
                for info in shoe.values():
                    matrix=arm.matrix_world@evaluated.pose.bones[info['bone']].matrix
                    transform=np.asarray(matrix)
                    side=info['side'];row[side]=min(row[side],float((info['points']@transform[:3,:3].T+transform[:3,3])[:,2].min()))
                sides.append(row); heights.append(min(row.values()))
                if notify and frame%500==0: notify(f'{phase}_{frame}_{last}')
        finally:
            for obj,previous in hidden: obj.hide_viewport=previous
        return heights,sides
    heights,sides=measure_frames('grounding_measure')
    lifts=floor_lifts(heights,clearance,floor_z,max_lift)
    output=patch_root_track(data,lifts,direction)
    destination.parent.mkdir(parents=True,exist_ok=True)
    pending=destination.with_name(destination.stem+'.pending.vmd')
    pending.write_bytes(output)
    scene.frame_set(1)
    bpy.ops.mmd_tools.import_vmd(filepath=str(pending),scale=.08,rename_bones=True,margin=0,log_level='ERROR')
    verified,verified_sides=measure_frames('grounding_verify')
    error=max(abs(verified[i]-(heights[i]+lifts[i])) for i in range(len(lifts)))
    if min(verified)<floor_z+clearance-1e-5 or error>1e-5:
        raise ValueError(f'Grounded VMD reimport failed: minimum {min(verified):.9f} m, prediction error {error:.9f} m')
    pending.replace(destination)
    return {'method':'stationary_root_vertical_lift','source':str(source),'motion':str(destination),
        'source_sha256':hashlib.sha256(data).hexdigest(),'output_sha256':hashlib.sha256(output).hexdigest(),
        'vmd_frame_range':[0,last],'blender_frame_range':[1,last+1],'frames':last+1,
        'floor_z_m':floor_z,'clearance_m':clearance,'max_lift_m':max(lifts),'min_height_before_m':min(heights),
        'min_height_predicted_m':min(a+b for a,b in zip(heights,lifts)),
        'min_height_verified_m':min(verified),'max_prediction_error_m':error,'verified_frames':len(verified),
        'changed_root_keys':len(lifts),'other_bone_records_and_tail_byte_identical':True,
        'shoe_vertices':{s:sum(d['vertices'] for d in shoe.values() if d['side']==s) for s in ('L','R')},
        'rigid_footwear_bones':{name:d['vertices'] for name,d in shoe.items()},
        'per_frame':[{'vmd_frame':i,'before':sides[i],'root_lift_m':lifts[i],
                      'predicted_after':{s:h+lifts[i] for s,h in sides[i].items()},
                      'verified_after':verified_sides[i]} for i in range(len(lifts))],
        'scope':'global character translation only; no shoe deformation, leg pose retarget, or native MMD dynamics acceptance'}
