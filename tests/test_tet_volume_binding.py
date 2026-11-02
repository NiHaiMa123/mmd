"""Contained embedding, affine reproduction, shared cells and hard attachments."""
import importlib.util,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tet_volume_binding',ROOT/'addon/animation_contact_tools/tet_volume_binding.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
vertices=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,1,1]],dtype=float)
tets=np.array([[0,1,2,3],[4,1,2,3]])
points=np.array([[.1,.2,.3],[.5,.5,.5],[1/3,1/3,1/3]])
binding=module.bind_volume(points,vertices,tets)
assert np.min(binding['weights'])>=0
np.testing.assert_allclose(module.deform_volume(binding,vertices),points,atol=1e-12)
transform=np.array([[1.1,.1,0],[0,.9,.1],[.1,0,1.03]])
translation=np.array([5.,-2.,3.])
np.testing.assert_allclose(module.deform_volume(binding,vertices@transform.T+translation),points@transform.T+translation,atol=1e-12)
permuted=module.bind_volume(points,vertices,tets[:,::-1])
np.testing.assert_allclose(module.deform_volume(permuted,vertices),points,atol=1e-12)
for outside in (np.array([[2.,2,2]]),np.array([[np.nan,0,0]])):
    try:module.bind_volume(outside,vertices,tets)
    except ValueError:pass
    else:raise AssertionError('Invalid or outside point was accepted')
fixed=np.unique(binding['vertex_indices'][:1]);deformed=vertices.copy();deformed[4]+=[.1,.2,.3];np.testing.assert_array_equal(deformed[fixed],vertices[fixed]);np.testing.assert_allclose(module.deform_volume(binding,deformed)[0],points[0],atol=1e-12)
result=dict(status='CONTAINED_EMBEDDING_AFFINE_REPRODUCTION_AND_EXACT_ROOT_PASS',reconstruction_error_m=binding['reconstruction_error_m'])
(ROOT/'outputs/tet_volume_binding_contract.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
