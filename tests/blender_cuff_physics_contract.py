"""Generated cuff particles must conserve mesh data and stay inside their model."""
import math,sys,unittest
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'));sys.path.insert(0,str(ROOT))
from mmd_outfit.cuff_physics import build,components,validate
from src import import_export as ie,physics


class CuffContracts(unittest.TestCase):
    def setUp(self):ie.ensure_mmd_tools();ie.clear_scene()
    def fixture(self):
        root=bpy.data.objects.new('cuff_root',None);bpy.context.scene.collection.objects.link(root);root.mmd_type='ROOT'
        data=bpy.data.armatures.new('cuff_arm');arm=bpy.data.objects.new('cuff_arm',data)
        bpy.context.scene.collection.objects.link(arm);arm.parent=root
        bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
        for side,sign in (('L',1),('R',-1)):
            upper=data.edit_bones.new('腕.'+side);upper.head=(sign*.1,0,1);upper.tail=(sign*.3,0,1)
            elbow=data.edit_bones.new('ひじ.'+side);elbow.head=upper.tail;elbow.tail=(sign*.5,0,1);elbow.parent=upper
            sleeve=data.edit_bones.new('袖_0_1.'+side);sleeve.head=(sign*.2,.05,.95);sleeve.tail=(sign*.2,.1,.9);sleeve.parent=upper
        bpy.ops.object.mode_set(mode='OBJECT')
        parents=[]
        for kind in ('RIGID_GRP_OBJ','JOINT_GRP_OBJ'):
            obj=bpy.data.objects.new(kind,None);bpy.context.scene.collection.objects.link(obj);obj.parent=root;obj.mmd_type=kind;parents.append(obj)
        core=physics._mmd_rigid_core();fn=core.FnRigidBody
        for side,sign in (('L',1),('R',-1)):
            for name,mode,group,location in [('腕.'+side,0,0,(sign*.2,0,1)),('袖_0_1.'+side,1,8,(sign*.2,.05,.95))]:
                obj=fn.new_rigid_body_object(bpy.context,parents[0]);mask=[True]*16;mask[0]=False
                fn.setup_rigid_body_object(obj,core.shapeType('SPHERE'),Vector(location),Vector().to_track_quat('Z','Y').to_euler(),
                    Vector((.02,0,0)),mode,collision_group_number=group,collision_group_mask=mask,bone=name,name=name)
        points=[];faces=[];mi=[];side_ids={'L':[],'R':[]}
        for material in range(2):
            for side,sign in (('L',1),('R',-1)):
                start=len(points)
                for j in range(30):
                    for k in range(8):
                        angle=k*math.tau/8;side_ids[side].append(len(points))
                        points.append((sign*(.1+j*.21/29),math.cos(angle)*.05,1+math.sin(angle)*.05))
                for j in range(29):
                    for k in range(8):
                        a=start+j*8+k;b=start+j*8+(k+1)%8;c=b+8;d=a+8
                        faces.extend([(a,b,c),(a,c,d)]);mi.extend([material]*2)
        extra=len(points);points.extend([(0,0,0),(.1,0,0),(0,.1,0)]);faces.append((extra,extra+1,extra+2));mi.append(2)
        me=bpy.data.meshes.new('cuff_cloth');me.from_pydata(points,[],faces);cloth=bpy.data.objects.new('cuff_cloth',me)
        bpy.context.scene.collection.objects.link(cloth);cloth.parent=arm
        for name in ('新規','服+jinshu','服'):me.materials.append(bpy.data.materials.new(name))
        for f,index in zip(me.polygons,mi):f.material_index=index
        for side,ids in side_ids.items():
            cloth.vertex_groups.new(name='腕.'+side).add(ids,.9,'REPLACE')
            cloth.vertex_groups.new(name='袖_0_1.'+side).add(ids,.1,'REPLACE')
        cloth.vertex_groups['腕.L'].add([extra,extra+1,extra+2],1.,'REPLACE')
        cloth.shape_key_add(name='Basis');key=cloth.shape_key_add(name='expression');key.data[0].co.z+=.001
        return root,cloth,arm,extra

    def test_components_exclude_unrelated_material_and_keep_both_layers(self):
        root,cloth,arm,extra=self.fixture();rows=components(cloth)
        self.assertEqual(len(rows),4);self.assertEqual({len(r['vertices']) for r in rows},{240})
        self.assertNotIn(extra,{i for r in rows for i in r['vertices']})

    def test_generation_preserves_geometry_morphs_and_unselected_weights(self):
        root,cloth,arm,extra=self.fixture()
        coords=[tuple(v.co) for v in cloth.data.vertices]
        keys=[[tuple(p.co) for p in k.data] for k in cloth.data.shape_keys.key_blocks]
        uv=cloth.data.uv_layers.new(name='UVMap')
        for i,loop in enumerate(uv.data):loop.uv=(i*.001,i*.002)
        original_uv=[tuple(loop.uv) for loop in uv.data]
        report=build(cloth,arm,physics)
        self.assertEqual(report['added_rigids'],16);self.assertEqual(report['added_joints'],32)
        self.assertEqual(coords,[tuple(v.co) for v in cloth.data.vertices])
        self.assertEqual(keys,[[tuple(p.co) for p in k.data] for k in cloth.data.shape_keys.key_blocks])
        self.assertEqual(original_uv,[tuple(loop.uv) for loop in cloth.data.uv_layers['UVMap'].data])
        for v in cloth.data.vertices:
            entries=[e for e in v.groups if e.weight>1e-6]
            self.assertLessEqual(len(entries),4);self.assertAlmostEqual(sum(e.weight for e in entries),1.,places=5)
        self.assertEqual([(cloth.vertex_groups[e.group].name,e.weight) for e in cloth.data.vertices[extra].groups],[('腕.L',1.)])
        self.assertFalse(validate(cloth,arm,[root,*root.children_recursive],report)['failures'])

    def test_duplicate_generation_fails_without_adding_more_bones(self):
        root,cloth,arm,extra=self.fixture();build(cloth,arm,physics);before=len(arm.data.bones)
        with self.assertRaisesRegex(ValueError,'already exist'):build(cloth,arm,physics)
        self.assertEqual(len(arm.data.bones),before)

    def test_missing_angular_support_does_not_partially_mutate_first_arm(self):
        root,cloth,arm,extra=self.fixture()
        for vertex in cloth.data.vertices:
            if vertex.co.x<0:vertex.co.y=.05;vertex.co.z=1.
        before=len(arm.data.bones)
        with self.assertRaisesRegex(ValueError,'angular support'):build(cloth,arm,physics)
        self.assertEqual(len(arm.data.bones),before)

    def test_new_physics_never_attaches_to_an_unrelated_model(self):
        root,cloth,arm,extra=self.fixture();foreign=bpy.data.objects.new('other_root',None)
        bpy.context.scene.collection.objects.link(foreign);foreign.mmd_type='ROOT'
        rg=bpy.data.objects.new('other_rigid_group',None);bpy.context.scene.collection.objects.link(rg);rg.parent=foreign;rg.mmd_type='RIGID_GRP_OBJ'
        build(cloth,arm,physics)
        self.assertEqual(list(rg.children),[])
        self.assertEqual(sum(o.mmd_type=='RIGID_BODY' for o in root.children_recursive),20)

    def test_validation_detects_unweighted_helper(self):
        root,cloth,arm,extra=self.fixture();report=build(cloth,arm,physics)
        name=report['created_bones'][0];cloth.vertex_groups[name].remove(list(range(len(cloth.data.vertices))))
        self.assertTrue(any(name in failure for failure in validate(cloth,arm,[root,*root.children_recursive],report)['failures']))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CuffContracts))
    if not result.wasSuccessful():raise SystemExit(1)
