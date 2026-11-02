"""Run in a clean Blender process: extraction, UI and config regression tests."""
from pathlib import Path
import sys
import tempfile
import unittest
import json

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))
import mmd_outfit
from src import dressing, garment
from mmd_outfit import service
from mmd_outfit.surface_fit import correct
from mmd_outfit.deformation import RadialEnvelopeField
from mmd_outfit.skin_patch import rebuild, seam_safe_offsets
import numpy as np
from types import SimpleNamespace
from unittest.mock import patch
from src import qa
from src.physics import translate_exclusions
from src import physics_sim


class BlenderContracts(unittest.TestCase):
    def test_uv_domain_tie_keeps_hand_fallback_in_any_vertex_order(self):
        from itertools import permutations
        from types import SimpleNamespace
        from mmd_outfit.skin_patch import face_domain
        face=SimpleNamespace(vertices=(0,1,2))
        for values in permutations(('palm','thumb','index')):
            self.assertIsNone(face_domain(face,values))
        self.assertIsNone(face_domain(face,('palm','thumb',None)))

    def test_uv_domain_preserves_unique_majority_and_rejects_sparse_support(self):
        from types import SimpleNamespace
        from mmd_outfit.skin_patch import face_domain
        face=SimpleNamespace(vertices=(0,1,2))
        self.assertEqual(face_domain(face,('palm','thumb','palm')),'palm')
        self.assertEqual(face_domain(face,('palm',None,'palm')),'palm')
        self.assertIsNone(face_domain(face,('palm',None,None)))
    def test_transparent_contact_filter_wraps_and_keeps_bilinear_neighbours(self):
        from src.visibility import rectangle_is_zero
        alpha=np.zeros((8,8),dtype=np.float32)
        self.assertTrue(rectangle_is_zero(alpha,[(.4,.4),(.5,.5)]))
        alpha[3,3]=1
        self.assertFalse(rectangle_is_zero(alpha,[(.4,.4),(.5,.5)]))
        self.assertTrue(rectangle_is_zero(alpha,[(.8,.8),(.9,.9)]))
        alpha[0,7]=1
        self.assertFalse(rectangle_is_zero(alpha,[(0,0),(.01,.01)]))
        self.assertFalse(rectangle_is_zero(alpha,[(float('nan'),0)]))

    def test_transparent_contact_filter_keeps_geometry_and_unknown_mapping(self):
        from src.visibility import visible_garment_faces
        me=bpy.data.meshes.new('alpha_fixture')
        me.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
        obj=bpy.data.objects.new('alpha_fixture',me)
        bpy.context.scene.collection.objects.link(obj)
        uv=me.uv_layers.new(name='UVMap')
        for v in uv.data:
            v.uv=(.5,.5)
        mat=bpy.data.materials.new('alpha_fixture')
        mat.use_nodes=True
        me.materials.append(mat)
        nodes=mat.node_tree.nodes
        base=nodes.new('ShaderNodeTexImage'); base.name='mmd_base_tex'
        base.image=bpy.data.images.new('transparent_fixture',width=4,height=4,alpha=True)
        base.image.pixels[:]=[0.]*64
        group=bpy.data.node_groups.new('MMDShaderDev_fixture','ShaderNodeTree')
        group.interface.new_socket(name='Base Alpha',in_out='INPUT',socket_type='NodeSocketFloat')
        shader=nodes.new('ShaderNodeGroup'); shader.name='mmd_shader'; shader.node_tree=group
        mat.node_tree.links.new(base.outputs['Alpha'],shader.inputs['Base Alpha'])
        uvgroup=bpy.data.node_groups.new('MMDTexUV_fixture','ShaderNodeTree')
        uvgroup.interface.new_socket(name='Base UV',in_out='OUTPUT',socket_type='NodeSocketVector')
        coord=uvgroup.nodes.new('ShaderNodeTexCoord')
        output=uvgroup.nodes.new('NodeGroupOutput')
        uvgroup.links.new(coord.outputs['UV'],output.inputs['Base UV'])
        mapper=nodes.new('ShaderNodeGroup'); mapper.name='mmd_tex_uv'; mapper.node_tree=uvgroup
        mat.node_tree.links.new(mapper.outputs['Base UV'],base.inputs['Vector'])
        kept,report=visible_garment_faces(obj,[0])
        self.assertEqual(kept,[])
        self.assertEqual(report['transparent_faces'],1)
        self.assertEqual(len(me.polygons),1)
        base.image.pixels[:]=[1.]*64
        self.assertEqual(visible_garment_faces(obj,[0])[0],[0])
        base.image.pixels[:]=[0.]*64
        base.interpolation='Cubic'
        self.assertEqual(visible_garment_faces(obj,[0])[0],[0])
        base.interpolation='Linear'
        uvgroup.links.clear()
        self.assertEqual(visible_garment_faces(obj,[0])[0],[0])
        uvgroup.links.new(coord.outputs['UV'],output.inputs['Base UV'])
        from src.import_export import ensure_mmd_tools
        ensure_mmd_tools()
        root=bpy.data.objects.new('alpha_root',None)
        bpy.context.scene.collection.objects.link(root)
        root.mmd_type='ROOT'; obj.parent=root
        morph=root.mmd_root.uv_morphs.add(); morph.uv_index=0
        offset=morph.data.add(); offset.index=0; offset.offset=(.5,0,0,0)
        self.assertEqual(visible_garment_faces(obj,[0])[0],[0])

    def test_contact_comparison_uses_separate_rest_references(self):
        def mesh(name,points,faces):
            me=bpy.data.meshes.new(name); me.from_pydata(points,[],faces); me.update()
            return me
        skin=mesh('contact_skin',[(0,0,0),(1,0,0),(0,1,0)],[(0,1,2)])
        cloth=mesh('contact_cloth',[(0,0,-.0015),(1,0,-.0015),(0,1,-.0015),
                                   (0,0,.002),(1,0,.002),(0,1,.002)],[(0,1,2),(3,4,5)])
        with patch('src.visibility.visible_garment_faces',return_value=([1],{'transparent_faces':1})):
            probe=qa._ContactProbe(None,[0,1],skin,cloth,[0],['hand']*3,1)
        for v in skin.vertices:
            v.co.z=.004
        skin.update()
        pierced,checked,hits=probe.sample(skin,cloth,[0],1,1,['hand']*3)
        self.assertEqual((pierced,checked),(3,3))
        self.assertEqual(probe.report()['raw_geometry']['max_ratio'],0)
        self.assertGreater(probe.reference[0],0)
        self.assertLess(probe.raw_reference[0],0)

    def test_exact_exclusion_scale_includes_distant_forbidden_pairs(self):
        def rigid(x,group,excluded):
            mask=[False]*16; mask[excluded]=True
            return SimpleNamespace(location=Vector((x,0,0)),
                bound_box=[(-.5,-.5,-.5)]*6+[(.5,.5,.5)],
                mmd_rigid=SimpleNamespace(collision_group_number=group,collision_group_mask=mask))
        a,b=rigid(0,0,1),rigid(100,1,0)
        scale=physics_sim.complete_exclusion_scale([a,b])
        self.assertGreater(scale,100/(3**.5))
        a.mmd_rigid.collision_group_mask=[False]*16
        b.mmd_rigid.collision_group_mask=[False]*16
        self.assertEqual(physics_sim.complete_exclusion_scale([a,b]),1.5)

    def test_explicit_uv_split_duplicates_weights_morphs_and_keeps_normals(self):
        me=bpy.data.meshes.new('uv_split_fixture')
        me.from_pydata([(0,0,0),(1,0,0),(0,1,0),(1,1,0)],[],[(0,1,2),(1,3,2)])
        obj=bpy.data.objects.new('uv_split_fixture',me)
        bpy.context.scene.collection.objects.link(obj)
        obj.vertex_groups.new(name='test_bone').add([0,1,2,3],1,'REPLACE')
        obj.shape_key_add(name='Basis')
        key=obj.shape_key_add(name='bend')
        for p in key.data:
            p.co.z=.2
        uv=me.uv_layers.new(name='UVMap')
        for i,p in enumerate(uv.data):
            p.uv=(0,0) if i<3 else (1,1)
        result=garment.split_uv_vertices(obj)
        self.assertEqual(result['added_vertices'],2)
        self.assertEqual(len(obj.data.vertices),6)
        for v in obj.data.vertices:
            self.assertAlmostEqual(v.groups[0].weight,1)
        for p in obj.data.shape_keys.key_blocks['bend'].data:
            self.assertAlmostEqual(p.co.z,.2)
        self.assertLess((obj.data.vertices[1].co-obj.data.vertices[3].co).length,1e-8)
        self.assertTrue(all(n.vector.z>.999 for n in obj.data.corner_normals))

    def test_glove_uv_cannot_jump_to_a_nearer_adjacent_digit(self):
        fabric=bpy.data.materials.new('digit_fabric')
        skin=bpy.data.materials.new('digit_skin')
        def obj(name, points, faces, material):
            me=bpy.data.meshes.new(name)
            me.from_pydata(points,[],faces)
            me.materials.append(material)
            ob=bpy.data.objects.new(name,me)
            bpy.context.scene.collection.objects.link(ob)
            return ob
        cloth=obj('digit_source',[(.1,0,0),(.2,0,0),(.1,0,.1),(.1,.001,0),(.2,.001,0),(.1,.001,.1)],[(0,1,2),(3,4,5)],fabric)
        cloth.vertex_groups.new(name='人指１.L').add([0,1,2],1,'REPLACE')
        cloth.vertex_groups.new(name='親指１.L').add([3,4,5],1,'REPLACE')
        uv=cloth.data.uv_layers.new(name='UVMap')
        for i,p in enumerate(uv.data):
            p.uv=(0,0) if i<3 else (1,1)
        body=obj('digit_target',[(.1,.0009,0),(.2,.0009,0),(.1,.0009,.1)],[(0,1,2)],skin)
        body.vertex_groups.new(name='人指１.L').add([0,1,2],1,'REPLACE')
        arm=bpy.data.objects.new('digit_arm',bpy.data.armatures.new('digit_arm'))
        bpy.context.scene.collection.objects.link(arm)
        for ob in bpy.context.selected_objects:
            ob.select_set(False)
        arm.select_set(True)
        bpy.context.view_layer.objects.active=arm
        bpy.ops.object.mode_set(mode='EDIT')
        for name,x in [('手首.L',0),('中指１.L',.1)]:
            b=arm.data.edit_bones.new(name)
            b.head=(x,0,0)
            b.tail=(x+.01,0,0)
        bpy.ops.object.mode_set(mode='OBJECT')
        report=rebuild(cloth,body,arm,{'region':'hands','material':fabric.name,'skin_material':skin.name,'margin':.001},garment._copy_mesh_subset)
        self.assertEqual(report['uv_domain_fallback_faces'],0)
        self.assertTrue(all(p.uv.length<1e-6 for p in cloth.data.uv_layers.active.data))

    def test_mmd_tools_true_mask_excludes_collision(self):
        mask = [False] * 16
        mask[4] = True
        result = translate_exclusions(mask, {4: 6}, {0: {0}, 1: {0}, 2: {3}})
        self.assertTrue(result[6])
        self.assertFalse(result[0])
        self.assertFalse(result[3])
        self.assertTrue(result[10])
        body_a = SimpleNamespace(mmd_rigid=SimpleNamespace(collision_group_number=0, collision_group_mask=[False]*16))
        groups = {0:[False]*16, 6:[False]*16}
        self.assertTrue(physics_sim.collision_slots(body_a, {0:0,6:1}, groups)[1])
        body_a.mmd_rigid.collision_group_mask[6] = True
        self.assertFalse(physics_sim.collision_slots(body_a, {0:0,6:1}, groups)[1])
        body_a.mmd_rigid.collision_group_mask[6] = False
        groups[6][0] = True
        self.assertFalse(physics_sim.collision_slots(body_a, {0:0,6:1}, groups)[1])

    def test_patch_offset_keeps_split_uv_seam_closed(self):
        mesh = bpy.data.meshes.new('split_seam')
        mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0),
                          (0,0,0),(1,0,0),(0,0,-1)], [], [(0,1,2),(3,4,5)])
        obj = bpy.data.objects.new('split_seam',mesh)
        bpy.context.scene.collection.objects.link(obj)
        mesh.update()
        offsets, report = seam_safe_offsets(obj,[0,1],.0015)
        self.assertLess((offsets[0]-offsets[3]).length,1e-8)
        self.assertLess((offsets[1]-offsets[4]).length,1e-8)
        self.assertGreater(report['max_previous_offset_gap_m'],.002)
        for i in (0,3):
            self.assertGreaterEqual(offsets[i].dot(mesh.vertices[i].normal),.00149)
        self.assertEqual(len(mesh.vertices),6)

    def test_radial_binning_cannot_reduce_required_clearance(self):
        angles=[.001,.039,.041]
        heights=[.001,.0059,.007]
        amounts=[.02,.06,.03]
        field=RadialEnvelopeField(angles,heights,amounts)
        actual=field.evaluate(angles,heights)
        self.assertTrue(np.all(actual >= np.asarray(amounts)-1e-10))

    def test_exploding_mesh_fails_even_when_piercing_ratio_is_zero(self):
        vertices = [SimpleNamespace(co=Vector((0, 0, 0))), SimpleNamespace(co=Vector((1, 0, 0)))]
        stretch = qa._edge_stretch([(0, 1, .01)], vertices)
        self.assertEqual(stretch["severe_edges"], 1)
        motion = {"max_ratio": 0., "deformation": {"max_severe_edges": 1, "max_large_edges": 1}}
        with patch.object(qa, "motion_check", return_value=motion):
            report = qa.run_qa([], motions="fixture.vmd")
        self.assertEqual(report["status"], "FAILED")

    def test_rig_mapping_retains_unweighted_ancestors_of_weighted_cloth(self):
        hips = SimpleNamespace(name="hips", parent=None)
        bridge = SimpleNamespace(name="unweighted_bridge", parent=hips)
        tip = SimpleNamespace(name="weighted_tip", parent=bridge)
        unused = SimpleNamespace(name="unused_hair", parent=hips)
        source = SimpleNamespace(data=SimpleNamespace(bones=[hips, bridge, tip, unused]))
        target = SimpleNamespace(data=SimpleNamespace(bones=[hips]))
        report = dressing.build_rig_map(source, target, {"weighted_tip"})
        self.assertEqual(report["garment_bones"], ["unweighted_bridge", "weighted_tip"])
        self.assertEqual(report["dropped_bones"], ["unused_hair"])

    def test_radial_order_keeps_layer_spacing_and_leaves_distant_cloth(self):
        mesh = bpy.data.meshes.new("layer_body")
        mesh.from_pydata([(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)], [], [(0, 1, 2, 3)])
        mesh.materials.append(bpy.data.materials.new("layer_skin"))
        body = bpy.data.objects.new("layer_body", mesh)
        cloth_mesh = bpy.data.meshes.new("layers")
        cloth_mesh.from_pydata([(0, .97, 0), (0, .972, 0), (0, .2, 0)], [], [])
        cloth = bpy.data.objects.new("layers", cloth_mesh)
        positions, report = correct(cloth, body, [0, 1, 2], ["layer_skin"], radial_order=True,
            radial_axis=(Vector((0, 0, -1)), Vector((0, 0, 1))))
        self.assertAlmostEqual(positions[1].y - positions[0].y, .002, places=5)
        self.assertGreater(positions[0].y, 1.)
        self.assertAlmostEqual(positions[2].y, .2)
        self.assertEqual(report["after"]["unavailable_vertices"], 1)

    def test_radial_field_wraps_angles_and_keeps_coincident_layers(self):
        field = RadialEnvelopeField([np.pi - .005], [.5], [.04])
        values = field.evaluate([np.pi - .005, -np.pi + .005, np.pi - .005], [.5, .5, .5])
        self.assertAlmostEqual(values[0], values[2])
        self.assertGreater(values[1], .039)
        self.assertTrue(np.isfinite(values).all())
        zero = RadialEnvelopeField([0], [0], [0]).evaluate([1], [2])
        self.assertEqual(float(zero[0]), 0)
        with self.assertRaises(ValueError):
            RadialEnvelopeField([0], [0], [float("nan")])

    def test_target_patch_preserves_target_morphs_weights_and_source_uv(self):
        self._target_patch_contract(True)

    def test_target_patch_adds_morphs_when_source_has_none(self):
        self._target_patch_contract(False)

    def _target_patch_contract(self, source_morphs):
        def mesh_object(name, points, faces, material):
            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata(points, [], faces)
            mesh.materials.append(material)
            obj = bpy.data.objects.new(name, mesh)
            bpy.context.scene.collection.objects.link(obj)
            return obj
        skin = bpy.data.materials.new("patch_skin")
        fabric = bpy.data.materials.new("patch_stocking")
        body = mesh_object("patch_target", [(0, 0, .2), (.1, 0, .2), (0, 0, .3)], [(0, 1, 2)], skin)
        body.vertex_groups.new(name="足D.L").add([0, 1, 2], 1., "REPLACE")
        body.shape_key_add(name="Basis")
        morph = body.shape_key_add(name="TargetMorph")
        morph.value = 0
        morph.data[0].co.x += .02
        cloth = mesh_object("patch_clothing", [(0, -.01, .2), (.1, -.01, .2), (0, -.01, .3),
            (0, 0, .8), (.1, 0, .8), (0, 0, .9)], [(0, 1, 2), (3, 4, 5)], fabric)
        cloth.vertex_groups.new(name="足D.L").add([0, 1, 2], 1., "REPLACE")
        cloth.vertex_groups.new(name="Torso").add([3, 4, 5], 1., "REPLACE")
        if source_morphs:
            cloth.shape_key_add(name="Basis")
        uv = cloth.data.uv_layers.new(name="UVMap")
        for i, value in enumerate(((0, 0), (1, 0), (0, 1))):
            uv.data[i].uv = value
        arm = bpy.data.objects.new("patch_arm", bpy.data.armatures.new("patch_arm"))
        bpy.context.scene.collection.objects.link(arm)
        report = rebuild(cloth, body, arm, {"region": "legs", "material": fabric.name,
            "skin_material": skin.name, "margin": .001}, garment._copy_mesh_subset)
        self.assertEqual(report["removed_faces"], 1)
        self.assertEqual(report["patch_faces"], 1)
        self.assertEqual(len(cloth.data.polygons), 2)
        self.assertIn("TargetMorph", cloth.data.shape_keys.key_blocks)
        key = cloth.data.shape_keys.key_blocks["TargetMorph"]
        # Joined target patch follows its target weight and morph, not source.
        patch_ids = list(cloth.data.polygons[-1].vertices)
        self.assertAlmostEqual(key.data[patch_ids[0]].co.x - cloth.data.shape_keys.key_blocks["Basis"].data[patch_ids[0]].co.x, .02, places=5)
        self.assertAlmostEqual(cloth.data.uv_layers.active.data[-2].uv.x, 1., places=5)
        for index in patch_ids:
            names = {cloth.vertex_groups[e.group].name: e.weight for e in cloth.data.vertices[index].groups}
            self.assertAlmostEqual(names["足D.L"], 1.)

    def test_position_updates_reach_evaluated_shape_keys_once(self):
        mesh = bpy.data.meshes.new("position_keys")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        obj = bpy.data.objects.new("position_keys", mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.shape_key_add(name="Basis")
        morph = obj.shape_key_add(name="Morph")
        morph.value = 0.0
        morph.data[0].co.z = 0.4
        dressing.apply_positions(mesh, [vertex.co + Vector((0, 0, 0.1)) for vertex in mesh.vertices])
        self.assertAlmostEqual(mesh.shape_keys.key_blocks["Basis"].data[0].co.z, 0.1)
        self.assertAlmostEqual(morph.data[0].co.z, 0.5)
        bpy.context.view_layer.update()
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        evaluated_mesh = evaluated.to_mesh()
        try:
            self.assertAlmostEqual(evaluated_mesh.vertices[0].co.z, 0.1)
        finally:
            evaluated.to_mesh_clear()

    def test_radial_clearance_uses_outer_surface_with_inverted_normals(self):
        mesh = bpy.data.meshes.new("inverted_surface")
        mesh.from_pydata([(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)], [], [(3, 2, 1, 0)])
        mesh.materials.append(bpy.data.materials.new("radial_skin"))
        body = bpy.data.objects.new("inverted_surface", mesh)
        cloth_mesh = bpy.data.meshes.new("radial_cloth")
        cloth_mesh.from_pydata([(0, 0.97, 0)], [], [])
        cloth = bpy.data.objects.new("radial_cloth", cloth_mesh)
        bpy.context.scene.collection.objects.link(body)
        bpy.context.scene.collection.objects.link(cloth)
        positions, report = correct(cloth, body, [0], ["radial_skin"],
            radial_axis=(Vector((0, 0, -1)), Vector((0, 0, 1))))
        self.assertAlmostEqual(positions[0].y, 1.003, places=5)
        self.assertEqual(report["after"]["violating_vertices"], 0)

    def test_clearance_moves_only_selected_vertices_and_preserves_topology(self):
        body_mesh = bpy.data.meshes.new("clearance_body")
        body_mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (0, 1, 0)], [], [(0, 1, 2)])
        body_mesh.materials.append(bpy.data.materials.new("test_surface"))
        body = bpy.data.objects.new("clearance_body", body_mesh)
        cloth_mesh = bpy.data.meshes.new("clearance_cloth")
        cloth_mesh.from_pydata([(0, 0, -0.03), (0.1, 0, -0.03), (0, 0.1, -0.03)], [], [(0, 1, 2)])
        cloth = bpy.data.objects.new("clearance_cloth", cloth_mesh)
        bpy.context.scene.collection.objects.link(body)
        bpy.context.scene.collection.objects.link(cloth)
        positions, report = correct(cloth, body, [0], ["test_surface"], clearance=0.003)
        self.assertAlmostEqual(positions[0].z, 0.003, places=5)
        self.assertAlmostEqual(positions[1].z, -0.03, places=5)
        self.assertEqual(report["before"]["violating_vertices"], 1)
        self.assertEqual(report["after"]["violating_vertices"], 0)
        self.assertEqual(len(cloth_mesh.polygons), 1)

    def test_target_exclusion_preserves_skin_weights_and_morphs(self):
        mesh = bpy.data.meshes.new("target_layers")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0),
                          (0, 0, 1), (1, 0, 1), (0, 1, 1)], [], [(0, 1, 2), (3, 4, 5)])
        for name in ("test_skin", "test_old_cloth"):
            mesh.materials.append(bpy.data.materials.new(name))
        mesh.polygons[1].material_index = 1
        obj = bpy.data.objects.new("target_layers", mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.shape_key_add(name="Basis")
        key = obj.shape_key_add(name="Morph")
        key.data[0].co.x = 0.1
        obj.vertex_groups.new(name="BoneA").add(list(range(6)), 0.7, "REPLACE")
        obj.vertex_groups.new(name="BoneB").add(list(range(6)), 0.3, "REPLACE")
        report = service.prepare_target(obj, ["test_old_cloth"])
        self.assertEqual(report["faces_removed"], 1)
        self.assertEqual(len(obj.data.vertices), 3)
        self.assertAlmostEqual(sum(g.weight for g in obj.data.vertices[0].groups), 1.0)
        self.assertEqual([g.name for g in obj.vertex_groups], ["BoneA", "BoneB"])
        self.assertAlmostEqual(obj.data.shape_keys.key_blocks["Morph"].data[0].co.x, 0.1)

    def test_ui_register_does_not_clear_scene(self):
        sentinel = bpy.data.objects.new("UserSceneSentinel", None)
        bpy.context.scene.collection.objects.link(sentinel)
        mmd_outfit.register()
        self.assertIn("UserSceneSentinel", bpy.data.objects)
        self.assertTrue(hasattr(bpy.context.scene, "mmd_outfit"))
        mmd_outfit.unregister()
        self.assertIn("UserSceneSentinel", bpy.data.objects)

    def test_extract_preserves_basis_relative_morphs_and_two_uv_layers(self):
        mesh = bpy.data.meshes.new("source")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        mesh.materials.append(bpy.data.materials.new("cloth"))
        obj = bpy.data.objects.new("source", mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.shape_key_add(name="Basis")
        first = obj.shape_key_add(name="FirstMorph")
        first.data[0].co.z = 0.4
        second = obj.shape_key_add(name="SecondMorph")
        second.relative_key = first
        second.data[0].co.z = 0.7
        for name, value in (("UVMap", 0.2), ("Lightmap", 0.6)):
            uv = mesh.uv_layers.new(name=name)
            for datum in uv.data:
                datum.uv = (value, value)
        extracted, _ = garment._copy_mesh_subset(obj, [0], "test_cloth")
        keys = extracted.data.shape_keys.key_blocks
        self.assertEqual([key.name for key in keys], ["Basis", "FirstMorph", "SecondMorph"])
        self.assertAlmostEqual(keys[0].data[0].co.z, 0)
        self.assertAlmostEqual(keys[1].data[0].co.z, 0.4)
        self.assertEqual(keys[2].relative_key.name, "FirstMorph")
        self.assertEqual(len(extracted.data.uv_layers), 2)
        self.assertAlmostEqual(extracted.data.uv_layers[1].data[0].uv.x, 0.6)

    def test_missing_config_fails_and_physics_override_is_honored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                dressing._load_config(str(path))
            path.write_text('{"physics": {"enabled": false}}')
            self.assertFalse(dressing._load_config(str(path))["physics"]["enabled"])

    def test_unknown_config_and_enabled_inplace_motion_are_rejected(self):
        with self.assertRaises(service.OutfitError):
            service._validate_config({"fit": {"ofset": 1}})
        with self.assertRaises(service.OutfitError):
            service._validate_config({"motion": {"enabled": True}})
        with self.assertRaises(service.OutfitError):
            service._validate_config({"body_mask": {"enabled": "false"}})

    def test_profile_refuses_changed_input_and_unknown_material(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / "source.pmx"
            source.write_bytes(b"fixture - no PMX parser needed for checksum check")
            record = {"path": str(source), "sha256": service.digest(source)}
            profile = {"schema_version": 1, "kind": "mmd_outfit_pair",
                       "source": record, "target": record,
                       "selected_materials": ["not_present"],
                       "materials": [{"material": "cloth"}]}
            config = path / "profile.json"
            config.write_text(json.dumps(profile))
            with self.assertRaises(service.OutfitError) as caught:
                service.load_profile(config)
            self.assertEqual(caught.exception.code, "UNKNOWN_MATERIAL")
            source.write_bytes(b"changed")
            with self.assertRaises(service.OutfitError) as caught:
                service.load_profile(config)
            self.assertEqual(caught.exception.code, "PROFILE_INPUT_CHANGED")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BlenderContracts)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Blender contract tests failed")
