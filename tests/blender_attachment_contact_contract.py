"""Signed attachment derivative on a closed, independently defined cube."""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.attachment_contact import attachment_contacts,attachment_linear_gap
co=np.array([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)],dtype=float)
faces=[(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(3,7,6),(3,6,2),(0,4,7),(0,7,3),(1,2,6),(1,6,5)]
points=np.array([(1.05,.1,.2),(.95,.1,.2)])
c=attachment_contacts(co,np.arange(8),faces,points,.1);np.testing.assert_allclose(c['distance'],[.05,-.05],atol=1e-6)
move=co+np.array([.01,0,0]);linear=attachment_linear_gap(move,c);actual=attachment_contacts(move,np.arange(8),faces,points,.1)['distance'];np.testing.assert_allclose(linear,actual,atol=1e-6)
reverse=attachment_contacts(co,np.arange(8),[tuple(reversed(f)) for f in faces],points,.1);np.testing.assert_allclose(reverse['distance'],c['distance'],atol=1e-6)
out=ROOT/'outputs/attachment_contact_contract';out.mkdir(parents=True,exist_ok=True);report={'status':'SIGNED_ATTACHMENT_DERIVATIVE_AND_REVERSED_WINDING_PASS','linear_gap':linear.tolist(),'actual_gap':actual.tolist()};(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('ATTACHMENT_CONTACT_CONTRACT',json.dumps(report),flush=True)
