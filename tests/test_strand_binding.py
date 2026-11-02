"""Frame binding must reproduce rest shape and rigid head motion exactly."""
import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon'))
from animation_contact_tools.strand_binding import bind_vertices,deform_vertices,bind_rod_vertices,deform_rod_vertices

class BindingTests(unittest.TestCase):
 def setUp(self):
  t=np.linspace(0,1,31);self.guide=np.c_[.12*np.sin(t*1.7),.08*t*t,.8-.5*t]
  rng=np.random.default_rng(4);self.vertices=np.repeat(self.guide,4,axis=0)+rng.normal(size=(124,3))*.008
  self.normal=np.array([1.,0,0]);self.binding=bind_vertices(self.vertices,self.guide,self.normal)
 def test_rest_shape(self):
  np.testing.assert_allclose(deform_vertices(self.binding,self.guide,self.normal),self.vertices,atol=2e-12)
 def test_arbitrary_rigid_head_motion(self):
  axis=np.array([.3,-.4,.5]);axis/=np.linalg.norm(axis);x,y,z=axis;K=np.array([[0,-z,y],[z,0,-x],[-y,x,0]]);R=np.eye(3)+np.sin(1.2)*K+(1-np.cos(1.2))*(K@K);shift=np.array([.4,-.6,.2])
  actual=deform_vertices(self.binding,self.guide@R.T+shift,R@self.normal)
  np.testing.assert_allclose(actual,self.vertices@R.T+shift,atol=3e-12)
 def test_width_is_retained_under_translation(self):
  shift=np.array([.3,.1,-.2]);np.testing.assert_allclose(deform_vertices(self.binding,self.guide+shift,self.normal)-shift,self.vertices,atol=2e-12)
 def test_solver_quaternion_binding_rigid_invariance(self):
  angle=np.linspace(0,.5,len(self.guide));q=np.c_[np.cos(angle/2),np.zeros((len(angle),2)),np.sin(angle/2)];b=bind_rod_vertices(self.vertices,self.guide,q,self.binding['segment'],self.binding['factor'])
  np.testing.assert_allclose(deform_rod_vertices(b,self.guide,q),self.vertices,atol=3e-12)
  # Global X rotation must rotate every cross-section and the entire hairstyle.
  theta=.9;c,s=np.cos(theta/2),np.sin(theta/2);w,x,y,z=q.T;rotated=np.c_[c*w-s*x,c*x+s*w,c*y-s*z,c*z+s*y];R=np.array([[1,0,0],[0,np.cos(theta),-np.sin(theta)],[0,np.sin(theta),np.cos(theta)]]);shift=np.array([.2,.3,-.1])
  np.testing.assert_allclose(deform_rod_vertices(b,self.guide@R.T+shift,rotated),self.vertices@R.T+shift,atol=3e-12)

if __name__=='__main__':unittest.main()
