"""Carry sleeve rest geometry with the anatomical upper arm, ignoring helper axes."""
import math
from mathutils import Matrix


def segment_delta(source_head, source_end, target_head, target_end):
    """A rigid transform with no helper roll, scale, or arbitrary display direction."""
    source_axis=source_end-source_head
    target_axis=target_end-target_head
    if min(source_axis.length,target_axis.length)<1e-6:
        raise ValueError('Anatomical upper-arm segment is degenerate')
    if not all(math.isfinite(v) for p in (source_head,source_end,target_head,target_end) for v in p):
        raise ValueError('Anatomical upper-arm landmarks must be finite')
    rotation=source_axis.rotation_difference(target_axis).to_matrix().to_4x4()
    return Matrix.Translation(target_head)@rotation@Matrix.Translation(-source_head)


def apply(source_arm,target_arm,deltas):
    """Replace only arm/twist and sleeve-chain rest deltas; keep target rig intact.

    This is the explicit Keqing sleeve convention, not a bone-name-only universal
    garment classifier. Hand, shoulder, torso, skirt and shoe deltas are untouched.
    """
    updates={};rows=[]
    for side in ('L','R'):
        upper='腕.'+side;elbow='ひじ.'+side
        if any(name not in arm.data.bones for arm in (source_arm,target_arm) for name in (upper,elbow)):
            raise ValueError('Anatomical upper arm and elbow bones are required on both rigs')
        sh,se=[source_arm.data.bones[n].head_local for n in (upper,elbow)]
        th,te=[target_arm.data.bones[n].head_local for n in (upper,elbow)]
        delta=segment_delta(sh,se,th,te)
        names=[];changes=[]
        for name,old in deltas.items():
            if not name.endswith('.'+side) or not name.startswith(('腕','袖_')):continue
            bone=source_arm.data.bones.get(name)
            if bone is None:continue
            # A prefixed bone on an unrelated branch is never silently moved.
            cursor=bone
            while cursor is not None and cursor.name!=upper:cursor=cursor.parent
            if cursor is None:raise ValueError('Arm/sleeve helper has no anatomical upper-arm ancestor: '+name)
            updates[name]=delta.copy();names.append(name)
            changes.append({'bone':name,'rotation_change_degrees':math.degrees(old.to_quaternion().rotation_difference(delta.to_quaternion()).angle),
                            'anchor_change_m':((delta@bone.head_local)-(old@bone.head_local)).length})
        rows.append({'side':side,'bones':sorted(names),'changes':changes,
                     'source_length_m':(se-sh).length,'target_length_m':(te-th).length,
                     'matrix':[list(row) for row in delta]})
    # Validate both arms before mutating the caller's map.
    deltas.update(updates)
    return {'method':'anatomical_upper_arm','sides':rows,'overridden_bones':len(updates),
            'scale':1.,'target_armature_modified':False,
            'scope':'rigid rest mapping only; sleeve sizing and moving-arm collision require separate review'}
