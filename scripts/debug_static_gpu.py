exec(open(str(__import__('pathlib').Path(__file__).with_name('smoke_full_hair_gpu.py')),encoding='utf-8-sig').read().split("start=time.monotonic();solver.project")[0])
ci=solver.ci.numpy();cb=solver.cb.numpy();samples=np.einsum('si,sij->sj',cb,initial[ci]);sd,_=solver.distances(samples);print('SAMPLE_SDF',float(sd.min()),int((sd<0).sum()),int((sd<.00049).sum()),flush=True)
np.savez_compressed(out/'gpu_sdf_probe.npz',points=samples,distance=sd)
solver.project(iterations=8,margin=.0005,lo=.9,hi=1.1,triangles=False,max_displacement=.02);wp.synchronize();print('NO_TRI',float(np.abs(solver.positions()-initial).max()),solver.metrics(),flush=True)
