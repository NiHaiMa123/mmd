"""Case wrapper: choose a route from cached final-skin feasible IK nodes."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.arm_detour_planner import select_arm_route
out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/hair_arm_feedback_20261028/planned_route'
data=json.loads((out/'candidate_layers.json').read_text('utf8'))
result=select_arm_route(data['layers'],data['frames'])
result.update(status='MINIMAX_SPEED_ROUTE_REQUIRES_SUBFRAME_VALIDATION',
              max_offset_m=max(np.linalg.norm(n['offset']) for n in result['waypoints']),
              original_actions_edited=False,hair_accepted=False)
(out/'planned_route.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('CACHED_ARM_ROUTE',json.dumps({k:v for k,v in result.items() if k!='waypoints'}),flush=True)
