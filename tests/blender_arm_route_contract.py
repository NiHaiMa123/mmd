"""Compare route selection against exhaustive paths, independent of MMD."""
import itertools,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.arm_detour_planner import select_arm_route

def node(x,cost=0.,swivel=0.):return {'offset':[x,0.,0.],'cost':cost,'swivel':swivel}
frames=[0,1,3,4]
layers=[[node(0)],[node(.04,.1),node(.02,.2),node(-.03,.05)],
        [node(.07,.1),node(.03,.2),node(-.01,.01)],[node(0)]]
paths=[]
for indices in itertools.product(*(range(len(layer)) for layer in layers)):
    ns=[layer[i] for layer,i in zip(layers,indices)]
    speeds=[np.linalg.norm(np.array(b['offset'])-a['offset'])/(t-s) for a,b,s,t in zip(ns,ns[1:],frames,frames[1:])]
    cost=sum(n['cost'] for n in ns)+sum(4*v*v+.0005*(b['swivel']-a['swivel'])**2 for a,b,v in zip(ns,ns[1:],speeds))
    paths.append((max(speeds),cost,indices))
expected=min(paths);result=select_arm_route(layers,frames)
assert abs(result['min_possible_peak_correction_step_m_per_frame']-expected[0])<1e-12
assert [w['offset'] for w in result['waypoints']]==[layer[i]['offset'] for layer,i in zip(layers,expected[2])]
for bad_layers,bad_frames,ceiling in [(layers,frames,expected[0]/2),([[]],[0],None),(layers,[0,1,1,2],None),(layers,frames,-1)]:
    try:select_arm_route(bad_layers,bad_frames,ceiling)
    except (RuntimeError,ValueError):pass
    else:raise AssertionError('Invalid or infeasible route was accepted')
assert select_arm_route([[node(0)]],[1])['min_possible_peak_correction_step_m_per_frame']==0
assert result['edges_collision_validated'] is False
small_layers=[[node(0)],[node(.04),node(.02)],[node(.04),node(-.02)],[node(0)]];small_frames=[0,10,11,21]
speed_first=select_arm_route(small_layers,small_frames);offset_first=select_arm_route(small_layers,small_frames,prioritize_offset=True)
assert max(np.linalg.norm(n['offset']) for n in speed_first['waypoints'])==.04
assert offset_first['min_possible_peak_offset_m']==.02
out=ROOT/'outputs/arm_route_contract';out.mkdir(parents=True,exist_ok=True)
report={'status':'MINIMAX_ROUTE_EXHAUSTIVE_AND_STRICT_CEILING_PASS','mmd_required':False,'edge_collision_guarantee':False}
(out/'report.json').write_text(json.dumps(report),encoding='utf8');print('ARM_ROUTE_CONTRACT',json.dumps(report),flush=True)
