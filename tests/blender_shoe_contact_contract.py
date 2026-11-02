import sys,unittest
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.shoe_contact import inward_surface,fit_layers


def mesh_object(name,points,faces):
    me=bpy.data.meshes.new(name);me.from_pydata(points,[],faces)
    ob=bpy.data.objects.new(name,me);bpy.context.scene.collection.objects.link(ob)
    me.materials.append(bpy.data.materials.new('lining'))
    return ob


class ContactContracts(unittest.TestCase):
    def setUp(self):bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_shared_layer_move_preserves_morphs_seams_and_rigid_shoe(self):
        shoe=mesh_object('shoe',[(.065,-.2,0),(.065,.2,0),(.065,0,.4)],[(0,1,2)])
        surface=inward_surface(shoe,lambda name,n,c:True)
        points=[(.060,.02,.05),(.060,.04,.05),(.060,.03,.07),(.060,.02,.05)]
        body=mesh_object('body',points,[(0,1,2),(3,2,1)])
        sock=mesh_object('stocking',[(x-.0015,y,z) for x,y,z in points],[(0,1,2),(3,2,1)])
        for obj in (body,sock):
            obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='toe_detail');key.data[1].co.y+=.001
        before=[[p.co.copy() for p in key.data] for key in body.data.shape_keys.key_blocks]
        shoe_before=[tuple(v.co) for v in shoe.data.vertices]
        report=fit_layers(body,sock,list(zip(range(4),range(4))),{'L':[surface],'R':[surface]},passes=5,toe_forward=0)
        self.assertGreater(report['max_displacement_m'],.006)
        self.assertEqual((len(body.data.vertices),len(body.data.polygons)),(4,2))
        self.assertEqual(shoe_before,[tuple(v.co) for v in shoe.data.vertices])
        self.assertLess((body.data.vertices[0].co-body.data.vertices[3].co).length,1e-7)
        for bi,ci in zip(body.data.vertices,sock.data.vertices):
            self.assertGreaterEqual(ci.co.x,.06619)
            self.assertLess(((bi.co-ci.co)-Vector((.0015,0,0))).length,1e-7)
        for i in range(4):
            old=before[1][i]-before[0][i]
            new=body.data.shape_keys.key_blocks[1].data[i].co-body.data.shape_keys.key_blocks[0].data[i].co
            self.assertLess((old-new).length,1e-7)

    def test_mirrored_inner_normal_keeps_its_cavity_orientation(self):
        shoe=mesh_object('shoe',[(.065,-.2,0),(.065,.2,0),(.065,0,.4)],[(0,1,2)])
        shoe.matrix_world=Matrix.Diagonal((-1,1,1,1))
        tree=inward_surface(shoe,lambda name,n,c:True)
        hit,normal,index,distance=tree.find_nearest(Vector((-.07,0,.05)))
        self.assertLess(normal.x,-.999)
        self.assertGreater((Vector((-.07,0,.05))-hit).dot(normal),0)

    def test_open_rim_does_not_pull_uncovered_skin_into_a_cap(self):
        shoe=mesh_object('shoe',[(.065,-.2,0),(.065,.2,0),(.065,0,.1)],[(0,1,2)])
        tree=inward_surface(shoe,lambda name,n,c:True)
        points=[(.06,0,.15),(.061,0,.15),(.06,.001,.15)]
        body=mesh_object('body',points,[(0,1,2)]);sock=mesh_object('stocking',points,[(0,1,2)])
        fit_layers(body,sock,list(zip(range(3),range(3))),{'L':[tree],'R':[tree]},passes=3,toe_forward=0)
        self.assertEqual([tuple(v.co) for v in body.data.vertices],[tuple(Vector(p)) for p in points])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContactContracts))
    if not result.wasSuccessful():raise SystemExit(1)
