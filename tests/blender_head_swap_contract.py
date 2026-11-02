import sys,unittest,math
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.head_swap import clipped_subset,opening,connect_necks,repair_neck_alpha
engine('import_export').ensure_mmd_tools()


def tube(name,material,z0,z1,n=8):
    points=[(.02*math.cos(2*math.pi*i/n),.02*math.sin(2*math.pi*i/n),z) for z in (z0,z1) for i in range(n)]
    faces=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    me=bpy.data.meshes.new(name);me.from_pydata(points,[],faces)
    obj=bpy.data.objects.new(name,me);bpy.context.scene.collection.objects.link(obj)
    mat=bpy.data.materials.new(material);mat.mmd_material.name_j=material;me.materials.append(mat)
    for layer_name,factor in [('UVMap',1.),('UV1',2.)]:
        uv=me.uv_layers.new(name=layer_name)
        for loop in me.loops:uv.data[loop.index].uv=(loop.vertex_index%n/n,me.vertices[loop.vertex_index].co.z*factor)
    obj.vertex_groups.new(name='首').add(list(range(n)),1.,'REPLACE');obj.vertex_groups.new(name='頭').add(list(range(n,n*2)),1.,'REPLACE')
    obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='detail');key.value=0.
    for i in range(n,n*2):key.data[i].co.x+=.004
    return obj


class HeadSwapContracts(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        engine('import_export').ensure_mmd_tools()

    def test_clipping_interpolates_weights_uv_layers_and_morphs(self):
        source=tube('source','肌',0,.04)
        result,prov=clipped_subset(source,range(8),'clipped',clip_material='肌',plane_z=.02,above=True)
        ring,center=opening(result,.02)
        self.assertEqual(len(ring),8);self.assertEqual(list(result.data.uv_layers.keys()),['UVMap','UV1'])
        key=result.data.shape_keys.key_blocks['detail'];self.assertEqual(key.value,0.)
        for i in ring:
            self.assertAlmostEqual(result.vertex_groups['首'].weight(i),.5,places=6)
            self.assertAlmostEqual(result.vertex_groups['頭'].weight(i),.5,places=6)
            self.assertAlmostEqual((key.data[i].co-result.data.vertices[i].co).x,.002,places=6)
        for li,loop in enumerate(result.data.loops):
            if loop.vertex_index in ring:self.assertAlmostEqual(result.data.uv_layers['UV1'].data[li].uv.y,.04,places=6)

    def test_neck_bridge_uses_existing_rings_and_keeps_neutral_values(self):
        lower=tube('body','Body',0,.02,8);upper=tube('head','肌',.024,.05,12)
        low,center=opening(lower,.02);high,center=opening(upper,.024)
        result,report=connect_necks(lower,upper,low,high,'combined')
        self.assertEqual(report['bridge_faces'],20)
        self.assertEqual(len(result.data.vertices),len(lower.data.vertices)+len(upper.data.vertices))
        self.assertEqual(list(result.data.uv_layers.keys()),['UVMap','UV1'])
        self.assertEqual(result.data.shape_keys.key_blocks['detail'].value,0.)
        self.assertTrue(all(len(set(f.vertices))==3 for f in list(result.data.polygons)[-20:]))

    def test_opaque_neck_texture_does_not_modify_the_source_atlas(self):
        lower=tube('body','Body',0,.02,8);upper=tube('head','肌',.024,.05,12)
        low,center=opening(lower,.02);high,center=opening(upper,.024)
        obj,report=connect_necks(lower,upper,low,high,'combined')
        originals=[]
        for material,color in [(lower.data.materials[0],(1,.85,.8)),(upper.data.materials[0],(.9,.8,.7))]:
            material.use_nodes=True;image=bpy.data.images.new(material.name+'_fixture',16,16,alpha=True)
            values=[c for i in range(256) for c in (*color,0. if i==4 else 1.)];image.pixels.foreach_set(values)
            node=material.node_tree.nodes.new('ShaderNodeTexImage');node.name='mmd_base_tex';node.image=image
            originals.append((image,list(image.pixels)))
        directory=ROOT/'outputs/head_contracts';directory.mkdir(parents=True,exist_ok=True)
        result=repair_neck_alpha(obj,.02,directory/'neck.png')
        self.assertEqual(result['method'],'opaque_neck_gradient')
        for image,values in originals:self.assertEqual(values,list(image.pixels))
        material=obj.data.materials[-1];image=material.node_tree.nodes['mmd_base_tex'].image
        self.assertTrue(all(a==1. for a in list(image.pixels)[3::4]))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HeadSwapContracts))
    if not result.wasSuccessful():raise SystemExit(1)
