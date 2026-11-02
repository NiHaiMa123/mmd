import sys,unittest
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.heeled_foot import HeelPose,deform_mesh,bind_shod_forefoot


class HeelPoseContracts(unittest.TestCase):
    def test_zero_pose_is_identity(self):
        pose=HeelPose((.07,.05,.1),0,-.04,.03)
        for p in ((.07,-.06,.02),(.08,.08,.06),(.07,0,.2)):
            self.assertLess((pose(p)-Vector(p)).length,1e-7)

    def test_calf_and_upper_body_are_unchanged(self):
        pose=HeelPose((.07,.05,.1),20,-.04,.03)
        for p in ((.07,0,.18),(.06,-.02,.5),(.2,0,1.),(.4,-.1,.02)):
            self.assertEqual(tuple(pose(p)),tuple(Vector(p)))

    def test_forefoot_stays_horizontal(self):
        pose=HeelPose((.07,.05,.1),20,-.04,.03)
        a=pose((.07,-.08,.02));b=pose((.07,-.09,.02))
        self.assertAlmostEqual(a.z,b.z,places=7)
        self.assertAlmostEqual((a-b).length,.01,places=6)

    def test_heel_fit_is_mirrored_and_keeps_forefoot_width(self):
        left=HeelPose((.07,.05,.1),12,-.04,.03,.012,.005,.9,.0015)
        right=HeelPose((-.07,.05,.1),12,-.04,.03,.012,.005,.9,.0015)
        for p in ((.09,.09,.04),(.08,-.06,.03),(.07,.03,.14)):
            a=left(p);b=right((-p[0],p[1],p[2]))
            self.assertLess((Vector((-a.x,a.y,a.z))-b).length,1e-7)
        self.assertAlmostEqual(left((.10,-.06,.02)).x,.10,places=6)

    def test_heel_width_adjustment_is_local(self):
        pose=HeelPose((.07,.05,.1),0,-.04,.03,heel_width=.9,heel_shift=.0015)
        self.assertAlmostEqual(pose((.10,.10,.04)).x,.0955,places=6)
        self.assertEqual(tuple(pose((.10,.10,.18))),tuple(Vector((.10,.10,.18))))

    def test_shod_toes_keep_skin_geometry_and_calf_blending(self):
        from types import SimpleNamespace
        bpy.ops.wm.read_factory_settings(use_empty=True)
        me=bpy.data.meshes.new('foot_weights');me.from_pydata([(.07,-.05,.03),(.08,.04,.08),(.07,0,.3)],[],[(0,1,2)])
        obj=bpy.data.objects.new('foot_weights',me);bpy.context.scene.collection.objects.link(obj)
        obj.vertex_groups.new(name='足先EX.L').add([0,1,2],.8,'REPLACE')
        obj.vertex_groups.new(name='ひざD.L').add([0,1,2],.2,'REPLACE')
        obj.vertex_groups.new(name='mmd_edge_scale').add([0,1,2],.5,'REPLACE')
        arm=SimpleNamespace(data=SimpleNamespace(bones={
            '足首D.L':SimpleNamespace(head_local=Vector((.07,.05,.1))),
            '足首D.R':SimpleNamespace(head_local=Vector((-.07,.05,.1)))}))
        before=[tuple(v.co) for v in me.vertices]
        report=bind_shod_forefoot(obj,arm)
        self.assertEqual(report['changed_vertices'],2);self.assertEqual(before,[tuple(v.co) for v in me.vertices])
        self.assertAlmostEqual(obj.vertex_groups['足首D.L'].weight(0),.8,places=6)
        self.assertAlmostEqual(obj.vertex_groups['ひざD.L'].weight(0),.2,places=6)
        self.assertAlmostEqual(obj.vertex_groups['mmd_edge_scale'].weight(0),.5,places=6)
        self.assertAlmostEqual(obj.vertex_groups['足先EX.L'].weight(2),.8,places=6)

    def test_every_morph_uses_same_pose_without_deleting_feet(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        me=bpy.data.meshes.new('foot');me.from_pydata([(.07,-.06,.02),(.08,-.04,.03),(.07,.08,.06)],[],[(0,1,2)])
        obj=bpy.data.objects.new('foot',me);bpy.context.scene.collection.objects.link(obj)
        obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='detail');key.data[0].co.x+=.001
        poses={s:HeelPose((.07,.05,.1),20,-.04,.03) for s in ('L','R')}
        expected=[[poses['L'](p.co) for p in k.data] for k in me.shape_keys.key_blocks]
        report=deform_mesh(obj,poses)
        self.assertEqual(len(me.vertices),3);self.assertEqual(len(me.polygons),1)
        self.assertEqual(report['deleted_vertices'],0)
        for values,k in zip(expected,me.shape_keys.key_blocks):
            for a,b in zip(values,k.data):self.assertLess((a-b.co).length,1e-7)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HeelPoseContracts))
    if not result.wasSuccessful():raise SystemExit(1)
