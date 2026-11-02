"""Conservative face replacement must cover source triangles and preserve input."""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.spatial import ConvexHull
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'outputs';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='collider_contract_',dir=out) as tmp:
    tmp=Path(tmp);src=tmp/'source';dst=tmp/'result';src.mkdir()
    body=np.array([[[0,0,0],[.06,0,0],[.06,.00001,0],[1,0,0],[1.1,0,0],[1,.1,0]]])
    angle=.03;R=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
    body=np.concatenate((body,body@R.T+np.array([.01,-.02,.03])),axis=0)
    faces=np.array([[0,1,2],[3,4,5]])
    np.savez_compressed(src/'trajectories.npz',body=body,body_faces=faces,cloth=np.zeros((2,3,3)))
    (src/'manifest.json').write_text('{}',encoding='utf8')
    before=hashlib.sha256((src/'trajectories.npz').read_bytes()).hexdigest()
    subprocess.run([sys.executable,str(ROOT/'scripts/condition_ppf_collision_triangles.py'),'--input',str(src),'--out',str(dst)],check=True,capture_output=True)
    result=np.load(dst/'trajectories.npz');receipt=json.loads((dst/'collider_conditioning.json').read_text())
    assert receipt['replaced_faces']==1 and receipt['all_original_faces_represented']
    np.testing.assert_array_equal(result['body'][:,:6],body)
    assert hashlib.sha256((src/'trajectories.npz').read_bytes()).hexdigest()==before
    assert result['body_faces'].shape==(13,3)
    new_faces=result['body_faces'][1:]-6
    edges=Counter(tuple(sorted((int(a),int(b)))) for f in new_faces for a,b in zip(f,np.roll(f,-1)))
    assert all(count==2 for count in edges.values())
    maximum=-float('inf')
    for t in (0,.125,.5,.875,1):
        box=result['body'][0,6:]*(1-t)+result['body'][1,6:]*t
        triangle=body[0,:3]*(1-t)+body[1,:3]*t
        hull=ConvexHull(box)
        violation=triangle@hull.equations[:,:3].T+hull.equations[:,3]
        maximum=max(maximum,float(violation.max()))
        assert violation.max()<=1e-9
        tri=box[new_faces];volume=np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()/6
        assert volume>0
    summary=dict(status='CONSERVATIVE_ANIMATED_COLLIDER_COVERAGE_AND_SOURCE_PRESERVATION_PASS',maximum_halfspace_violation_m=maximum)
    result.close()
    # A nearly zero-area face changes normal through a fold. The auxiliary box
    # must keep its corner correspondence and cover the prescribed triangle.
    folded=tmp/'folded';folded.mkdir();fold_out=tmp/'fold_result';motion=np.repeat(body[:1],3,axis=0);motion[1,2,1]=0.;motion[2,2,1]=-.00001
    np.savez_compressed(folded/'trajectories.npz',body=motion,body_faces=faces,cloth=np.zeros((3,3,3)))
    np.savez_compressed(folded/'volume_binding.npz',ids=np.arange(3));binding_hash=hashlib.sha256((folded/'volume_binding.npz').read_bytes()).hexdigest();(folded/'manifest.json').write_text('{}',encoding='utf8')
    subprocess.run([sys.executable,str(ROOT/'scripts/condition_ppf_collision_triangles.py'),'--input',str(folded),'--out',str(fold_out)],check=True,capture_output=True)
    receipt2=json.loads((fold_out/'collider_conditioning.json').read_text());assert receipt2['transported_frame_faces']==[0];assert receipt2['minimum_frame_axis_dot']>.99
    assert hashlib.sha256((fold_out/'volume_binding.npz').read_bytes()).hexdigest()==binding_hash
    with np.load(fold_out/'trajectories.npz') as data2:
        for interval in (0,1):
            for t in (0,.125,.5,.875,1):
                box=data2['body'][interval,6:]*(1-t)+data2['body'][interval+1,6:]*t;triangle=motion[interval,:3]*(1-t)+motion[interval+1,:3]*t;hull=ConvexHull(box);assert (triangle@hull.equations[:,:3].T+hull.equations[:,3]).max()<=1e-9
    summary.update(folding_normal_frame_transport_pass=True,volume_binding_preserved=True)
    (out/'ppf_collider_conditioning_contract.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary))
