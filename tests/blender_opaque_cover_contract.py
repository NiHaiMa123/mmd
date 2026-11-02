"""Conservative opaque-only masking and recoverable target mesh contracts."""
from pathlib import Path
import sys
import unittest
import tempfile
import bpy
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'addon')]
from mmd_outfit.opaque_cover import opaque_faces,back_up_covered_skin
from mmd_outfit.service import engine
from src.garment import _copy_mesh_subset


class OpaqueCoverContracts(unittest.TestCase):
    def fixture(self):
        me=bpy.data.meshes.new('cover_fixture')
        me.from_pydata([(0,0,0),(1,0,0),(0,1,0),(2,0,0),(3,0,0),(2,1,0)],[],[(0,1,2),(3,4,5)])
        body=bpy.data.objects.new('cover_body',me); bpy.context.scene.collection.objects.link(body)
        skin=bpy.data.materials.new('cover_skin'); me.materials.append(skin)
        body.vertex_groups.new(name='hand').add(list(range(6)),1,'REPLACE')
        body.shape_key_add(name='Basis'); morph=body.shape_key_add(name='Bend'); morph.data[0].co.z=.2
        uv=me.uv_layers.new(name='UVMap')
        for i,datum in enumerate(uv.data): datum.uv=(.2,.2) if i<3 else (.8,.8)
        patch,_=_copy_mesh_subset(body,[0,1],'cover_patch')
        material=bpy.data.materials.new('opaque_fixture'); material.use_nodes=True
        patch.data.materials.clear(); patch.data.materials.append(material)
        nodes=material.node_tree.nodes
        shader=nodes.new('ShaderNodeGroup'); shader.name='mmd_shader'
        group=bpy.data.node_groups.new('MMDShaderDev_cover','ShaderNodeTree'); shader.node_tree=group
        for name in ('Alpha','Base Alpha','Toon Alpha','Sphere Alpha'):
            group.interface.new_socket(name=name,in_out='INPUT',socket_type='NodeSocketFloat').default_value=1
            shader.inputs[name].default_value=1
        base=nodes.new('ShaderNodeTexImage'); base.name='mmd_base_tex'
        base.image=bpy.data.images.new('cover_alpha',width=16,height=16,alpha=True)
        base.image.pixels[:]=[1.]*1024
        material.node_tree.links.new(base.outputs['Alpha'],shader.inputs['Base Alpha'])
        mapper=nodes.new('ShaderNodeGroup'); mapper.name='mmd_tex_uv'
        uv_group=bpy.data.node_groups.new('MMDTexUV_cover','ShaderNodeTree'); mapper.node_tree=uv_group
        uv_group.interface.new_socket(name='Base UV',in_out='OUTPUT',socket_type='NodeSocketVector')
        coord=uv_group.nodes.new('ShaderNodeTexCoord'); output=uv_group.nodes.new('NodeGroupOutput')
        uv_group.links.new(coord.outputs['UV'],output.inputs['Base UV'])
        material.node_tree.links.new(mapper.outputs['Base UV'],base.inputs['Vector'])
        return body,patch,base,shader

    def test_only_fully_opaque_regions_are_eligible(self):
        body,patch,base,shader=self.fixture()
        covered,report=opaque_faces(patch,engine)
        self.assertEqual(covered,[0,1],report)
        pixels=np.ones((16,16,4),dtype=np.float32); pixels[12,12,3]=.5
        base.image.pixels.foreach_set(pixels.ravel())
        self.assertEqual(opaque_faces(patch,engine)[0],[0])
        shader.inputs['Alpha'].default_value=.5
        self.assertEqual(opaque_faces(patch,engine)[0],[])

    def test_unknown_mapping_and_interpolation_never_remove_skin(self):
        body,patch,base,shader=self.fixture()
        base.interpolation='Cubic'
        self.assertEqual(opaque_faces(patch,engine)[0],[])
        base.interpolation='Linear'
        for layer in list(patch.data.uv_layers): patch.data.uv_layers.remove(layer)
        self.assertEqual(opaque_faces(patch,engine)[0],[])

    def test_backup_preserves_weights_morphs_and_uncovered_surface(self):
        body,patch,base,shader=self.fixture()
        pixels=np.ones((16,16,4),dtype=np.float32); pixels[12,12,3]=0
        base.image.pixels.foreach_set(pixels.ravel())
        report=back_up_covered_skin(body,patch,[0,1],_copy_mesh_subset,'hands',engine)
        self.assertEqual(report['masked_skin_faces'],1)
        self.assertEqual(len(body.data.polygons),1)
        self.assertEqual(len(patch.data.polygons),2)
        backup=bpy.data.objects[report['backup_object']]
        self.assertIsNone(backup.parent)
        self.assertTrue(backup.hide_render)
        self.assertTrue(backup['outfit_backup'])
        self.assertEqual(list(backup['original_face_ids']),[0])
        self.assertEqual(list(backup['original_vertex_ids']),[0,1,2])
        self.assertAlmostEqual(backup.data.shape_keys.key_blocks['Bend'].data[0].co.z,.2)
        self.assertAlmostEqual(backup.data.vertices[0].groups[0].weight,1)
        self.assertAlmostEqual(body.data.vertices[0].co.x,2)

    def test_translucent_cloth_keeps_skin_and_creates_no_backup(self):
        body,patch,base,shader=self.fixture()
        pixels=np.ones((16,16,4),dtype=np.float32); pixels[:,:,3]=.8
        base.image.pixels.foreach_set(pixels.ravel())
        report=back_up_covered_skin(body,patch,[0,1],_copy_mesh_subset,'hands',engine)
        self.assertEqual(report['masked_skin_faces'],0)
        self.assertIsNone(report['backup_object'])
        self.assertEqual(len(body.data.polygons),2)

    def test_unloaded_file_toon_is_read_before_opacity_decision(self):
        body,patch,base,shader=self.fixture()
        with tempfile.TemporaryDirectory(dir=ROOT/'outputs') as directory:
            path=Path(directory)/'toon.png'
            image=bpy.data.images.new('toon_file_fixture',width=4,height=4,alpha=True)
            image.pixels[:]=[1.]*64
            image.filepath_raw=str(path); image.file_format='PNG'; image.save()
            node=patch.data.materials[0].node_tree.nodes.new('ShaderNodeTexImage')
            node.image=bpy.data.images.load(str(path),check_existing=False)
            patch.data.materials[0].node_tree.links.new(node.outputs['Alpha'],shader.inputs['Toon Alpha'])
            self.assertEqual(opaque_faces(patch,engine)[0],[0,1])


result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OpaqueCoverContracts))
if not result.wasSuccessful(): raise RuntimeError('Opaque cover contracts failed')
