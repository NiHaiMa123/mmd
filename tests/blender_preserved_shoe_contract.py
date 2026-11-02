"""Run with Blender: closed-shoe boundary, mesh replacement and motion guards."""
import sys
import unittest
import tempfile
import json
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT))
from mmd_outfit.preserved_shoe import CollarField, _boundary, replace_mesh, rim_position, lock_vertex_morphs, vertex_morph_report
from src.garment import _copy_mesh_subset
from mmd_outfit import service


class ClosedShoeContracts(unittest.TestCase):
    def test_shoe_lock_cannot_change_other_vertices_or_basis(self):
        me=bpy.data.meshes.new('shoe_morph_lock')
        me.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
        obj=bpy.data.objects.new('shoe_morph_lock',me);bpy.context.scene.collection.objects.link(obj)
        basis=obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='FacialMorph')
        key.data[0].co.z=.002;key.data[1].co.z=.003
        report=lock_vertex_morphs(obj,[0])
        self.assertEqual(report['changed_keys'],1)
        self.assertEqual(report['affected_vertices'],1)
        self.assertAlmostEqual(key.data[0].co.z,0)
        self.assertAlmostEqual(key.data[1].co.z,.003)
        self.assertAlmostEqual(basis.data[0].co.z,0)
        self.assertEqual(vertex_morph_report(obj,[0])['changed_keys'],[])
        self.assertEqual(vertex_morph_report(obj,[1])['changed_keys'],['FacialMorph'])
    def test_withdrawn_shoe_method_and_legacy_conflicts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pmx = root / 'fixture.pmx'
            pmx.write_bytes(b'checksum fixture')
            record = {'path': str(pmx), 'sha256': service.digest(pmx)}
            profile = {'schema_version': 1, 'kind': 'mmd_outfit_pair', 'source': record, 'target': record,
                       'selected_materials': ['shoe', 'collar'], 'materials': [{'material': n} for n in ('shoe', 'collar')],
                       'target_materials': ['Body'], 'shoe_fit': {'method': 'anatomical_foot_last'}}
            path = root / 'profile.json'
            path.write_text(json.dumps(profile))
            with self.assertRaises(service.OutfitError) as caught:
                service.load_profile(path)
            self.assertEqual(caught.exception.code, 'SHOE_METHOD_WITHDRAWN')
            profile['shoe_fit'] = {'method': 'preserved_closed_shoe', 'materials': ['shoe'], 'collar_material': 'collar',
                                  'skin_materials': ['Body'], 'scale': 1.2, 'body_lift': .012,
                                  'mask_depth': .006, 'ankle_rim_scale': .75}
            fit = {'fit_limbs': False, 'fit_limb_ends': False, 'subdivide_shoe': 0,
                   'lay_shoe_on_foot': False, 'fit_shoe_radius': False}
            profile['native_config'] = {'fit': fit}
            path.write_text(json.dumps(profile))
            self.assertEqual(service.load_profile(path)['shoe_fit']['scale'], 1.2)
            fit['subdivide_shoe'] = 1
            path.write_text(json.dumps(profile))
            with self.assertRaises(service.OutfitError) as caught:
                service.load_profile(path)
            self.assertEqual(caught.exception.code, 'CONFIG_SCHEMA')

    def test_ankle_rim_taper_is_bounded_and_leaves_leg_unchanged(self):
        ankle = Vector((.08, .05, .1))
        upper = Vector((.1, .06, .15))
        self.assertLess((rim_position(upper, ankle, .75) - upper).length, 1e-8)
        point = Vector((.1, .06, .08))
        changed = rim_position(point, ankle, .75)
        self.assertAlmostEqual(changed.z, point.z)
        self.assertAlmostEqual(changed.x, .095)
        distant = Vector((.4, .05, .08))
        self.assertLess((rim_position(distant, ankle, .75) - distant).length, 1e-8)

    def mesh(self, vertices, faces):
        data = bpy.data.meshes.new("fixture")
        data.from_pydata(vertices, [], faces)
        data.materials.append(bpy.data.materials.get("collar") or bpy.data.materials.new("collar"))
        obj = bpy.data.objects.new("fixture", data)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def test_collar_boundary_ignores_split_uv_seam(self):
        obj = self.mesh([(0, 0, 0), (1, 0, 0), (1, 1, 0),
                         (0, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2), (3, 4, 5)])
        self.assertEqual(_boundary(obj, "collar", 1), {(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)})
        # Shared seam's endpoints are also outer corners; inspect a seam-only center.
        obj = self.mesh([(0, 0, 0), (1, 0, 0), (.5, .5, 0),
                         (1, 0, 0), (1, 1, 0), (.5, .5, 0),
                         (1, 1, 0), (0, 1, 0), (.5, .5, 0),
                         (0, 1, 0), (0, 0, 0), (.5, .5, 0)],
                        [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11)])
        self.assertNotIn((.5, .5, 0), _boundary(obj, "collar", 1))

    def test_sloped_collar_and_degenerate_controls(self):
        points = [(x, y, .1 + .2*x - .3*y) for x, y in
                  [(-.03, -.03), (0, -.03), (.03, -.03), (.03, .03), (0, .03), (-.03, .03)]]
        field = CollarField(points, .006)
        self.assertAlmostEqual(field.height(Vector((.01, .02, 0))), .090, places=6)
        with self.assertRaises(ValueError):
            CollarField([(0, 0, .1)] * 6, .006)

    def test_replacement_preserves_weights_uv_and_morph(self):
        obj = self.mesh([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], [(0, 1, 2), (0, 1, 3)])
        obj.vertex_groups.new(name="unused")
        obj.vertex_groups.new(name="ankle").add([0, 1, 2, 3], 1, 'REPLACE')
        obj.shape_key_add(name="Basis")
        obj.shape_key_add(name="test").data[2].co.z = .2
        uv = obj.data.uv_layers.new(name="UVMap")
        uv.data[1].uv = (.3, .7)
        retained, _ = _copy_mesh_subset(obj, [0], "retained")
        replace_mesh(obj, retained)
        self.assertEqual([g.name for g in obj.vertex_groups], ["ankle"])
        self.assertAlmostEqual(obj.data.vertices[0].groups[0].weight, 1)
        self.assertAlmostEqual(obj.data.shape_keys.key_blocks["test"].data[2].co.z, .2)
        self.assertAlmostEqual(obj.data.uv_layers[0].data[1].uv.y, .7)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClosedShoeContracts))
if not result.wasSuccessful():
    raise RuntimeError("Closed shoe contracts failed")
