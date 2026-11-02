from pathlib import Path
code=Path(__file__).with_name('solve_full_hair_root_feedback.py').read_text('utf-8-sig');exec(code.split('for iteration in range(a.iterations):')[0])
state=min(states,key=lambda st:abs(st['frame']-235.25));co=activate(state,coeff);sets,minimum=contacts(co,state['roots']);q=min(sets,key=lambda q:q['distance'].min());index=int(q['distance'].argmin());values=[]
for j in range(solver.n):
 x=np.zeros(solver.n);x[j]=.001;solver.apply(x);nc=coords(m);surface=np.einsum('si,sij->sj',q['weights'],limb_points(nc,q['limb'])[q['triangles']]);J=-np.einsum('ij,ij->i',surface-q['surface'],q['normal'])/.001;values.append(float(J[index]))
print('WORST_ROOT_JACOBIAN',minimum,values,flush=True);j=int(np.abs(values).argmax());x=np.zeros(solver.n);x[j]=np.sign(values[j])*np.radians(5);solver.apply(x);new=coords(m);_,minimum_after=contacts(new,state['roots']);print('FIVE_DEGREE_PROBE',state['frame'],j,minimum,minimum_after,flush=True)
