import fs from 'node:fs';
import path from 'node:path';
import {NullEngine} from '@babylonjs/core/Engines/nullEngine.js';
import {Scene} from '@babylonjs/core/scene.js';
import {Vector3,Matrix,Quaternion} from '@babylonjs/core/Maths/math.vector.js';
import {PmxLoader} from 'babylon-mmd/esm/Loader/pmxLoader';
import {VmdLoader} from 'babylon-mmd/esm/Loader/vmdLoader';
import 'babylon-mmd/esm/Runtime/Animation/mmdRuntimeModelAnimation';
import {MmdRuntime} from 'babylon-mmd/esm/Runtime/mmdRuntime';
import {GetMmdWasmInstance} from 'babylon-mmd/esm/Runtime/Optimized/mmdWasmInstance';
import * as SPR from 'babylon-mmd/esm/Runtime/Optimized/wasm/spr/index';
import {MultiPhysicsRuntime} from 'babylon-mmd/esm/Runtime/Optimized/Physics/Bind/Impl/multiPhysicsRuntime';
import {MmdBulletPhysics} from 'babylon-mmd/esm/Runtime/Optimized/Physics/mmdBulletPhysics';
const root=path.resolve(process.argv[2]);
const maxFrame=Number(process.argv[3]??479);
const out=path.join(root,process.argv[4]??'run');fs.mkdirSync(out,{recursive:true});
const status=(s)=>{fs.writeFileSync(path.join(out,'status.json'),JSON.stringify(s,null,2));console.log(JSON.stringify(s));};
try {
  status({stage:'LOADING'});
  const engine=new NullEngine();const scene=new Scene(engine);
  const loader=new PmxLoader({materialBuilder:null,useSdef:false,buildMorph:false,optimizeSubmeshes:false,optimizeSingleMaterialModel:false});
  const pmx=new Uint8Array(fs.readFileSync(path.join(root,'input/character_calibrated.pmx')));
  const state=await new Promise(resolve=>loader.loadFile(scene,pmx,'',resolve,null,true));
  const assets=await loader.loadAssetContainerAsync(scene,state,'');assets.addAllToScene();
  const mesh=assets.meshes[0];
  const metadata=mesh.metadata;
  fs.writeFileSync(path.join(out,'physics_metadata.json'),JSON.stringify({rigidBodies:metadata.rigidBodies,joints:metadata.joints}));
  if(process.argv[5]==='repair-pivots') {
    metadata.skeleton.prepare();
    const repairs=[];
    for(const joint of metadata.joints) {
      const rb=metadata.rigidBodies[joint.rigidbodyIndexB];
      if(!rb || rb.boneIndex<0)throw Error('Unmapped child joint');
      const pivot=metadata.skeleton.bones[rb.boneIndex].getAbsoluteInverseBindMatrix().clone().invert().getTranslation().asArray();
      repairs.push({joint:joint.name,old:joint.position,new:pivot});joint.position=pivot;
    }
    fs.writeFileSync(path.join(out,'joint_pivot_calibration.json'),JSON.stringify({method:'PMX joint pivot at calibrated child bone head; original limit axes, stiffness, mass and collision masks preserved',repairs},null,2));
  }
  const wasmBytes=fs.readFileSync(new URL('./node_modules/babylon-mmd/esm/Runtime/Optimized/wasm/spr/index_bg.wasm',import.meta.url));
  const wasm=await GetMmdWasmInstance({getWasmInstanceInner:()=>({...SPR,default:()=>SPR.default({module_or_path:wasmBytes})})},1);
  const physics=new MultiPhysicsRuntime(wasm);physics.evaluationType=0;
  physics.setGravity(new Vector3(0,-98,0));physics.useDeltaForWorldStep=false;physics.timeStep=1/240;physics.fixedTimeStep=1/240;physics.maxSubSteps=1;
  const runtime=new MmdRuntime(scene,new MmdBulletPhysics(physics));
  const model=runtime.createMmdModel(mesh,{materialProxyConstructor:null,trimMetadata:false,buildPhysics:{disableOffsetForConstraintFrame:true}});
  const vmd=fs.readFileSync(path.join(root,'input/corrected_body_fk.vmd'));
  const animation=await new VmdLoader(scene).loadFromBufferAsync('body_fk',vmd.buffer.slice(vmd.byteOffset,vmd.byteOffset+vmd.byteLength));
  model.setRuntimeAnimation(model.createRuntimeAnimation(animation));
  const names=model.runtimeBones.map(b=>b.name);
  const physical=new Set(metadata.rigidBodies.filter(b=>b.physicsMode!==0).map(b=>b.boneIndex));
  fs.writeFileSync(path.join(out,'bones.json'),JSON.stringify({names,physical:[...physical],metadata:metadata.bones.map((b,i)=>({name:b.name,parentBoneIndex:b.parentBoneIndex,restLocal:Array.from(model.skeleton.bones[i].getRestMatrix().m)})),settings:{gravity:[0,-98,0],fps:30,substeps:8,disableOffsetForConstraintFrame:true}},null,2));
  model.beforePhysics(0);model.initializePhysics();model.afterPhysics();
  const initial=Array.from(model.worldTransformMatrices);
  fs.writeFileSync(path.join(out,'initial_world.f32'),Buffer.from(model.worldTransformMatrices.buffer,model.worldTransformMatrices.byteOffset,model.worldTransformMatrices.byteLength));
  const fd=fs.openSync(path.join(out,'world_matrices.f32'),'wx');
  const started=Date.now();
  for(let sample=0;sample<=maxFrame*8;sample++) {
    const frame=sample/8;
    model.beforePhysics(frame);
    if(process.argv.includes('--legal-start') && sample<=240)model.initializePhysics();
    else physics.afterAnimations(1000/240);
    model.afterPhysics();
    if(!model.worldTransformMatrices.every(Number.isFinite))throw Error(`Nonfinite matrix at ${frame}`);
    fs.writeSync(fd,Buffer.from(model.worldTransformMatrices.buffer,model.worldTransformMatrices.byteOffset,model.worldTransformMatrices.byteLength));
    if(sample%240===0)status({stage:'SIMULATING',frame,sample,totalSamples:maxFrame*8+1,bones:names.length,physicalBones:physical.size,enabledRigidBodies:Array.from(model.rigidBodyStates).filter(x=>x!==0).length,elapsed_s:(Date.now()-started)/1000});
  }
  fs.closeSync(fd);status({stage:'COMPLETE_REQUIRES_GEOMETRY_AND_VISUAL_QA',frames:maxFrame+1,samples:maxFrame*8+1,bones:names.length,elapsed_s:(Date.now()-started)/1000});
  process.exit(0);
} catch(error){status({stage:'FAILED',error:String(error),stack:error.stack});process.exit(1);}
