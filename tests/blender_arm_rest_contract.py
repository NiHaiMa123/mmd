"""Regression: arbitrary MMD twist-helper display axes must not fold sleeves."""
from pathlib import Path
import sys,unittest,math
import bpy
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'));sys.path.insert(0,str(ROOT))
from mmd_outfit.arm_rest import segment_delta,apply
from src import dressing


class ArmRestContracts(unittest.TestCase):
    def fixture(self):
        arms=[]
        for label in ('source','target'):
            data=bpy.data.armatures.new(label);obj=bpy.data.objects.new(label,data)
            bpy.context.scene.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
            for side,sign in (('L',1),('R',-1)):
                upper=data.edit_bones.new('腕.'+side);upper.head=(0,0,0);upper.tail=(sign,0,0)
                elbow=data.edit_bones.new('ひじ.'+side);elbow.head=upper.tail;elbow.tail=(sign*2,0,0);elbow.parent=upper
                twist=data.edit_bones.new('腕捩1.'+side);twist.head=(sign*.4,0,0)
                twist.tail=(sign*.4,0,1) if label=='source' else (sign*.8,0,0);twist.parent=upper
                sleeve=data.edit_bones.new('袖_0_1.'+side);sleeve.head=(sign*.6,.2,0);sleeve.tail=(sign*.6,.6,0);sleeve.parent=upper
            bpy.ops.object.mode_set(mode='OBJECT');obj.select_set(False);arms.append(obj)
        return arms

    def test_segment_maps_origin_and_axis_without_scaling(self):
        sh,se,th,te=map(Vector,((1,0,0),(3,0,0),(0,2,0),(0,5,0)))
        d=segment_delta(sh,se,th,te)
        self.assertLess((d@sh-th).length,1e-6)
        self.assertLess(((d@se-th).normalized()-(te-th).normalized()).length,1e-6)
        self.assertAlmostEqual((d@se-d@sh).length,2.,places=6)
        self.assertAlmostEqual(d.to_3x3().determinant(),1.,places=6)

    def test_degenerate_and_nonfinite_landmarks_rejected(self):
        for end in ((0,0,0),(float('nan'),0,0)):
            with self.assertRaises(ValueError):segment_delta(Vector(),Vector(end),Vector(),Vector((1,0,0)))

    def test_helper_display_direction_ignored_target_rig_unchanged(self):
        sa,ta=self.fixture()
        mapping={b.name:b.name for b in sa.data.bones}
        old=dressing.rest_deltas(sa,ta,mapping)
        before={b.name:(b.head_local.copy(),b.tail_local.copy()) for b in ta.data.bones}
        untouched=old['ひじ.L'].copy()
        self.assertGreater(abs(old['腕捩1.L'].to_quaternion().angle),1.)
        report=apply(sa,ta,old)
        self.assertEqual(report['overridden_bones'],6)
        for n in ('腕.L','腕捩1.L','袖_0_1.L'):
            self.assertLess(sum(abs(old[n][i][j]-Matrix.Identity(4)[i][j]) for i in range(4) for j in range(4)),1e-5)
        self.assertEqual(old['ひじ.L'],untouched)
        for b in ta.data.bones:self.assertEqual((b.head_local,b.tail_local),before[b.name])

    def test_mixed_arm_weights_keep_triangle_shape_and_morph_delta(self):
        sa,ta=self.fixture();d=dressing.rest_deltas(sa,ta,{b.name:b.name for b in sa.data.bones});apply(sa,ta,d)
        me=bpy.data.meshes.new('sleeve');me.from_pydata([(.3,.1,0),(.5,.1,0),(.4,.3,0)],[],[(0,1,2)])
        obj=bpy.data.objects.new('sleeve',me);bpy.context.scene.collection.objects.link(obj)
        for n,w in [('腕.L',.5),('腕捩1.L',.5)]:obj.vertex_groups.new(name=n).add([0,1,2],w,'REPLACE')
        obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='expression');key.data[0].co.z+=.01
        coords=[v.co.copy() for v in me.vertices]
        dressing.reskin(obj,d,{n:n for n in d})
        self.assertLess(max((v.co-p).length for v,p in zip(me.vertices,coords)),1e-6)
        self.assertAlmostEqual(key.data[0].co.z-me.shape_keys.key_blocks[0].data[0].co.z,.01,places=6)

    def test_unrelated_prefixed_branch_fails_transactionally(self):
        sa,ta=self.fixture();d=dressing.rest_deltas(sa,ta,{b.name:b.name for b in sa.data.bones})
        bpy.context.view_layer.objects.active=sa;sa.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
        sa.data.edit_bones['袖_0_1.R'].parent=None;bpy.ops.object.mode_set(mode='OBJECT')
        before={n:m.copy() for n,m in d.items()}
        with self.assertRaises(ValueError):apply(sa,ta,d)
        self.assertEqual(d,before)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ArmRestContracts)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
