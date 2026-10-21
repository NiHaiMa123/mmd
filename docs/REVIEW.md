# MMD 自动换装工具链代码 Review

> 审查对象：NiHaiMa123/mmd，main，基线提交 **b803f91bcc0b57f4c8a0624241857a9236a00451**  
> 环境：Blender 5.2.1；bl_ext.blender_org.mmd_tools  
> 重点：本次提交的物理 QA、碰撞 A/B、鞋面修复、LEGWEAR_WORDS；同时追查直接影响结论的上游实现。  
> 审查方式：阅读该提交 diff、源代码、progress.md；**未运行 Blender、未取得本地 PMX/VMD/输出产物**。下文区分「由代码直接确认」「高风险待验证」「已有实验但解释不足」，不把静态审查写成实测通过。

## 0. 总结与实施顺序

**总体方向正确，但目前不能把“物理碰撞组使真实穿模减少 4.3%”视为可靠结论；鞋子的主要瓶颈也尚不能归因于 608 对 3924 的顶点数差异。**

优先级建议：

1. **P0：先修物理代理的运动学偏移和碰撞层语义；再重新跑 A/B。** 当前脚本中的 Blender 碰撞层不等价于 PMX 的 group/mask，Mode 0 刚体也被直接贴到骨头原点（丢失静置偏移和旋转）。这会直接污染物理比较。
2. **P0：修 QA 坐标空间及指标可观测性。** 网格计数的局部坐标与刚体 BVH 的世界坐标混用；6 mm 法线翻转指标只是在有限条件下有效的 proxy，不是“总穿模量”。
3. **P0：暂时关闭默认鞋面细分/最近点全投影（实验开关保留）。** 先用遮挡处理裸脚漏出；然后改为「分部件、基于足部解剖标志的形变」，而非给整片鞋子做最近点投影。
4. **P1：把零厚度漆皮类服装单独建模为 body-derived shell。** 手套、袜子、贴皮鞋面适合从目标素体表面复制对应片区并转移来源外观；靴帮、鞋底、金饰必须保留自己的部件约束。
5. **P1：修权重混合公式、形态键处理，并建立带重复实验的 QA 阈值。** 当前代码里存在与本次提交无关、但会直接使实验解释失真的逻辑错误。

### 重要判断

- 本次提交将读取原始对象改为先获取 evaluated object，再执行 to_mesh()，**方向正确**，且成功观测到非零动态结果值得肯定。不过原先的笼统断言“new_from_object 不应用修改器”并不准确：Blender API 的 new_from_object 对**原始对象**读取未变形网格，对**evaluated object**才读取最终几何（含修改器）；之前调用传入的是原始对象。问题是调用对象及求值时序，不是 API 永远不支持修改器。
- 物理后的 4347/4542 与腿区 76/76，只能称作「当前代理指标下的观测差异」。未修复物理实现之前，不能证明 PMX/MMD 本体实际碰撞收益。
- 608 顶点的单层鞋面跨过高曲率足面，**确实可能出现三角面跨越皮肤**；但“67% 目标脚点距离鞋面大于 4 mm”主要描述覆盖/形状/位置问题，不能证明“增加网格密度便可解决”。骨架语义、脚长、封闭包络、遮蔽均可能更关键。

---

## 1. 按代码位置列出的高优先级发现

### [P0-01] 物理 Mode 0 的静置刚体偏移丢失，物理 A/B 的基础不可靠

**位置：src/physics_sim.py:115–129、135–141。代码直接确认。**

现有逻辑对每个 Mode 0 刚体执行：

~~~python
m = arm.matrix_world @ arm.pose.bones[bone].matrix
r.location = m.to_translation()
r.rotation_quaternion = m.to_quaternion()
~~~

MMD 的刚体通常相对骨骼原点具有**非零静置偏移与局部转角**。以上操作把碰撞体中心移动到骨头头部，丢失刚体的初始 world/bone offset；若刚体存在 parent，直接写 location/rotation_quaternion 还可能混淆局部与世界矩阵。即使衣服在动，腿、腰、躯干碰撞代理也可能完全放错。

修法（伪代码，关键是保存静置 offset）：

~~~python
# 在任何动画/物理推进前记录：
bone_rest_world = arm.matrix_world @ arm.data.bones[bone].matrix_local
rb_rest_world = r.matrix_world.copy()
offset = bone_rest_world.inverted() @ rb_rest_world

# 在每一帧：
bone_pose_world = arm.matrix_world @ arm.pose.bones[bone].matrix
desired_rb_world = bone_pose_world @ offset
r.matrix_world = desired_rb_world  # 若有 parent，应将其换算为 parent local
~~~

需要同时处理：
- Mode 1 的「刚体世界变换 → 骨骼姿态」必须去掉 **bone-to-rigid rest offset**，否则把骨骼也吸到刚体中心。
- Mode 2 **不能简单等价于 Mode 1**：应按 MMD 语义区分物理旋转与骨骼位置，不得将完整刚体矩阵直接写给骨骼。
- 将 Blender 自带刚体模拟与 MMD 的物理后骨骼计算视作近似；逐帧改变 pose bones 时必须检查 depsgraph 刷新与 frame_change_post 写回的先后顺序，避免 1 帧延迟/反馈。

**验证**：站立/抬腿 2 姿势，每个 Mode 0 刚体中心到对应骨骼的局部位移应保持不变；关节连接后 Mode 1 骨骼不应突跳。对各帧输出 RB-to-bone 局部相对矩阵的最大误差。

### [P0-02] Blender collision_collections 不是 PMX 双向 group/mask 的无损翻译

**位置：src/physics_sim.py:80–106、src/qa.py:572–595。代码直接确认。**

目前每个刚体按「它的 allowed mask 里有哪些群组」设置 Blender collision_collections。Blender 两个刚体通常在**共享至少一层碰撞 collection**时可以互相碰撞；PMX/Bullet 的群组过滤则要求：
- A 的 group 位包含在 B 的 mask 中；
- **并且** B 的 group 位包含在 A 的 mask 中。

简单反例：

~~~text
A：group=6，允许 {0, 3}
B：group=1，允许 {0, 3}
~~~

Blender 当前编码两者共享 0/3，可能相撞；PMX 中 A 不允许 group 1、B 不允许 group 6，**本不应相撞**。因此注释“two bodies collide exactly when MMD says they do”不成立。

建议：
1. 先建立显式的 **rigid-body pair contact matrix**：allowed(A,B) = maskA[groupB] AND maskB[groupA]；group 为 0–15。
2. 把当前 Blender 20-layer 模拟标为 **approximate physics QA**，不能作为 MMD 物理准确性验收。
3. 若仍使用 Blender 物理，可对接触矩阵做有限层编码/成对禁碰约束，**必须以矩阵逐对比对实际实现的接触对**；20 层未必足够精确表示任意矩阵，不能无条件承诺等价。
4. 真实发布验收另跑 MMD/MikuMikuMoving 或经基准校准的 PMX/Bullet 运行时。

这点优先级高于调节阻尼、质量或 spring。

### [P0-03] cloth_in_body 的坐标混用；指标名称也过强

**位置：src/qa.py:232–282、474–512。代码直接确认。**

_rigid_bvh 使用 r.matrix_world @ v.co 构造**世界坐标** BVH；_cloth_inside_colliders 却用 cloth_me.vertices[i].co 直接测试（**网格对象局部坐标**）。如果导入后网格恰好 matrix_world 为单位矩阵，测试可能偶然成立，但这不是跨 Blender/MMD 模型的稳定契约。

修复两种之一：
- 全部变成世界坐标：cloth_world = gmesh.matrix_world @ evaluated_vertex.co；若要稳定使用 evaluated object 的变换，应取相应 evaluated.matrix_world；
- 或将刚体世界 BVH 变换到 garment local（不推荐，容易遗漏缩放/法线处理）。

增加强制断言/记录：garment.mesh_world_matrix、body.mesh_world_matrix、rigid.matrix_world、模型尺度与非单位缩放；针对平移/旋转后的同一模型，穿模计数应不变。

更重要的是：**“服装顶点落入身体碰撞体” ≠ “服装顶点进入真实皮肤”**。碰撞体是宽松/稀疏的近似代理；服装进入代理也不必然可见穿模，没进入代理也不能证明没有穿皮。请把字段命名为 proxy_inside_body / proxy_inside_leg，与真实 mesh penetration 分开。

补充：脚本只用首次匹配的碰撞体把点归到一个 bone，结果依赖刚体遍历顺序；多个代理重叠时，应按每个代理分别统计，并单独提供 any-proxy 去重指标。

### [P0-04] sign flip + 6 mm 不是可靠的“总穿模量”

**位置：src/motion.py:250–305；src/qa.py:342–351、439–452。代码直接确认。**

当前指标要求：静置 nearest cloth 相对 body normal 的点积 > 0.001，动作中反向 < -0.001，且最近距离 < 0.006 Blender 单位。问题：

1. 对于漆皮层（来源/目标表面接近重合）及 4–5 mm 间隙，静态 rest_sign 可能落入排除区；以后再严重穿透也不计。
2. 正面穿得很深（>6 mm）的顶点反而不计；鞋子最远偏差达约 20 mm，正落在盲区之外。
3. 最近表面可能跳到相邻手指、另一块裙褶或袖口；法线判据会随最近三角面切换而抖动。
4. 法线近垂直、反向面、双层透明叠层、初始交叠也会导致误判/漏判。
5. 使用顶点数而非表面积加权，细分鞋面后计数将不可直接比较；删除/隐藏身体面也会降低分母，导致数字“改善”。

建议指标分层：

| 指标 | 用途 | 要求 |
|---|---|---|
| ray/triangle intersection count（带位置） | 真正表面交叉位置 | 建立部件级最近对应，避免相邻件串扰 |
| signed distance / penetration depth（mm） | 深度与严重度 | 仅对能确定内外的封闭区域有效；开口用局部定向面或局部包络 |
| body skin visibly uncovered | 手/脚/袜子是否露皮 | **单独在可见性渲染/深度图验证**，不是穿透点计数 |
| mesh self-intersection、degenerate faces | 鞋帮撕裂/金饰拉长 | 输出坏三角形、拉伸率、翻转面 |
| garment vertex inside body proxy | 碰撞代理泄漏 | 明确标注 proxy，不等同可见穿模 |
| silhouette / surface coverage | 鞋头不够长等 | 足部覆盖率、鞋头余量、鞋帮开口高度 |

保留旧 sign-flip 值作回归 proxy，但不要作为唯一 pass/fail 指标。

### [P0-05] 鞋面细分的选择范围错误，且不能默认保证 UV/权重/Morph 保真

**位置：src/dressing.py:650–702、749–810、1940–1945。代码直接确认 + 实测尚未通过。**

subdivide_shoe 按 dominant_bone 的基础名字选面：若 ≥50% 顶点主导骨是 足先EX，就将该面的全部边加入待细分边集。此前 progress.md 已证实裙摆下摆可能绑在足首D；类似风险对鞋面与其装饰也存在。**这里没有材质过滤、没有连通分量过滤，也没有脚左右/鞋帮分区**。

已记录的一轮数据显示 vertices 276→1990，faces 315→342。无法据此断言“bmesh.ops.subdivide_edges 在 Blender 5.2 对所有三角面只加点不拆面”；更可能需排查选中的边是否属于预期鞋面、其 link_faces 的数量、原面是三角面还是 n-gon，以及参数 use_grid_fill=False 的分割行为。最直接的 QA：

- 细分前保存「真正鞋面」三角形数、边数和连通分量；打印被选中 edge 所属 faces 的材质分布。
- 细分后检查**原表面上生成的三角/四边面数**是否实质提高，而不是只看顶点数。
- 检查是否出现 T-junction、退化面、开口、非流形边、孤立顶点和旧材质边界的 UV seams。
- 用非零 shape keys、非零 UV、双骨权重测试 subdivision 的插值与 Blender→PMX 再导入。不要仅凭 bm.from_mesh/to_mesh 假设各图层仍一致。

对于选中的三角形，**可先显式三角化并做拓扑保持的 1→4 midpoint split**（共享边只建立一个中点，并在相邻未选面切边以避免 T-junction）；UV 在 face-corner/loop 上按各自 UV 岛插值，顶点组做归一化线性插值，各 shape key 须独立插值。优先采用 Blender 内置、可复现且经上述断言验证的细分方案；纯粹增加顶点不算通过。

无论哪种实现，**只允许对确认为鞋面漆皮的连通分量加密**，不能因骨骼名称把裙摆/饰品/靴筒一起切碎。

### [P0-06] 脚部最近点贴合会把鞋当皮肤，破坏鞋头/鞋底/金饰

**位置：src/dressing.py:713–810、2003–2013。代码直接确认。**

当前 foot_bvh 以踝到趾的线段为轴，允许半径 0.13 Blender 单位。此阈值在当前 0.08 导入标度下大致是 13 cm，**并不天然排除小腿或另一只脚的几何**；它也不是按目标脚的脚背、脚底、趾端语义选面。

lay_shoe_on_foot 将 dominant_bone 完全匹配 足先EX.L/R 的顶点全部投影到目标脚最近面 + 4 mm。随后 3 环邻接扩散，把形变传给邻接的靴筒、鞋带、金属线——与 progress.md 的“靴面撕裂、金饰变竖条”高度吻合。

即使网格变密，此做法仍有根本风险：目标脚的**底部、侧面和局部三角面**可能变成鞋面的最近点；鞋面投影可能翻面、折回到脚底或穿过鞋壳。也没有鞋楦容积约束。

建议将 subdivide_shoe、lay_shoe_on_foot 的默认值从 True/2 改为**明确实验功能开关**，待完成新算法验证再开启。先实施第 3 节的低成本路径。

### [P1-07] 目标权重插值在已有骨骼上被加了两遍

**位置：src/dressing.py:530–539。代码直接确认。**

当前对于原有 body bone：

~~~python
new[name] = t * blended.get(name, 0.0) + (1.0 - t) * weight
~~~

之后又执行：

~~~python
new[name] = new.get(name, 0.0) + t * weight
~~~

后面的 weight 是 blended[name]，使重叠的目标骨骼项从目标权重 **t 变为 2t**（只有后面 normalization 把总和压回 1）。例如原权重和目标权重均为 {A:1}，虽然归一化最终仍为 1，但对多个交叉骨骼，会产生偏差。以前“权重转移有害/0.3 与 0.8 完全一样”的实验解释还曾被 BVH face-index bug 污染；应再补一次干净的独立单测。

替代写法：

~~~python
keys = set(current[vi]) | set(blended)
new = {
    name: (1 - t) * current[vi].get(name, 0.0)
          + t * blended.get(name, 0.0)
    for name in keys
}
# 服装专属骨骼按意图保留/抑制后再重新归一化
~~~

注意：target weight 只应覆盖选定 body-bone 权重；对裙摆、金饰、鞋底等类别必须有独立掩码。_bvh_with_faces 已修复子集面索引映射，但 transfer_target_weights:514 的查询点是 garment **local**，BVH 构建为 target **world**，仍有空间混用风险。

### [P1-08] Shape Key 不是“每个键都加同一个位移”即可完整重定向

**位置：src/dressing.py:235–267，细分路径及 reskin。代码直接确认。**

apply_positions 将 Basis 和所有 shape keys 加上同一个 delta，能在平移场近似下保持原 morph 差值，但**不是非刚性体型变形的正确一般解**。如果原 Basis 为 v、键为 v+δ，重定向函数为 F，理想键应为 F(v+δ)，而不是 F(v)+δ；对骨骼旋转/缩放的最简单情况，键向量也应乘对应的变换 Jacobian。

建议：
- 纯仿射区域：对 morph displacement 做相同骨骼加权线性变换。
- 非线性 surface-fit 区域：复用同一连续形变场/局部 cage，对每个 shape key 求新键坐标；无法保证时明确标为待处理。
- 细分后检验 KeyBlock.data 顶点数与 Mesh vertices 一致、关键表情/服装 Morph 的正负值可用，并 roundtrip PMX。
- 若 Morph 涉及鞋子/袜子，可先设置「锁定/不适用」规则，避免无人发现时带坏 Morph 出口。

### [P1-09] 其他需要加闸门的边界

- **src/physics.py:113–129、184–194**：_fresh_groups 用递增找空组，不限制 0–15；PMX 只有 16 组。若超出，new_mask[fresh[s]] 可能越界。应显式拒绝而非自动写坏。
- **src/physics.py:254–285**：tgt_body_rb 只取每骨骼遇到的第一个刚体；同骨多碰撞体可能遗漏。源→目标的自动“所有全开 mask 的组”不能证明是腿部 collider，应按骨骼/部位标签选。
- **src/physics.py:329–355**：复制关节数值并不证明 constraint 的 type、use_limit_*、angular spring、disable_collisions、局部约束轴全都一致。建议字段级 diff/re-import 单测；不能只以 399 个 joint / 0 个悬空端点判定物理等价。
- **src/dressing.py:76–110、270–307**：head_local/tail_local 属于 armature local，v.co 属于 garment object local；只有矩阵关系受控时，骨骼差矩阵才可直接乘 v.co。建立 source/target armature/mesh world transforms 的统一坐标空间及单测。
- **src/qa.py:152–179**：新的 evaluated.to_mesh() + copy() 比旧代码合理，但还要保证 evaluated mesh 的**拓扑索引**与原始 material split 一致。若任何 modifier 改变顶点或多边形数，split_faces 的原始 polygon index 将失效；应跳过或通过 original index/correspondence 对应。
- **src/qa.py:546–597**：--break-collision 根据 outfit_groups 与 body_groups 切换掩码，组独占时概念上是“删除 outfit↔body 关系”；实际 Blender layer 实现仍可能出现多余/遗漏接触。更准确名称是 **no-outfit-body-contact counterfactual**，并非逐字复现“迁移前”PMX 的原始状态。
- **src/qa.py:627–639**：motion WARNING 最后仍汇总为 report.status="OK"；脚部指标也未纳入总验收。建议区分 pass/warn/fail/unknown，关键指标缺失必须是 UNKNOWN/FAILED，不能“错得很稳定”再发生。
- **scripts/blender_runner.py:244–254**：即使 qa.run_qa 报错/跳过，外层 result["ok"]=True；CLI exit code 0 不能当 QA 通过。
- **src/dressing.py:1813–1816**：配置只更新 fit/body_mask/motion，遗漏 physics 子配置；目前 physics 只有 enabled，已经足以制造“改配置却没生效”的隐式问题。
- **src/extraction.py:45、170–179**：LEGWEAR_WORDS 放在 SKIN_WORDS 后对“腿肌肤”有保护，但“腿”是非常宽泛的词，“大腿”也可能只是裸皮。只在刻晴测试模型上观察到正确分类，不能写成所有 PMX 通用规则。

---

## 2. 为什么 b803f91 的物理实验不足以决定方案

progress.md 最新表格：

| 指标 | fixed | break-collision | 原记录差值 |
|---|---:|---:|---:|
| 旧 sign-flip 总点数 | 4347 | 4542 | −195（−4.3%） |
| 躯干 | 1608 | 1851 | −243 |
| 腰 | 717 | 700 | +17 |
| 腿 | 76 | 76 | 0 |
| 服装点在腿部刚体代理内 | 1378 | 1408 | −30（约 −2.1%） |

**可以说的：** 在本次 Blender 代理仿真和当前取样口径下，打开 garment↔body mask 对旧 sign-flip 指标有小幅改善，且不集中在腿区。作者如实承认“裙子不再穿腿未得到证明”是正确的。

**现在不能说的：** MMD 实际裙摆穿透总量改善 4.3%；翻译修好了裙子穿腿；“腿区没变化”证明腿部物理完全没效果。旧 proxy 与 proxy_inside_collider 不同，且原先已有静态、动态、物理、网格覆盖相互混用的问题。

重做 A/B 的严格条件：

1. 每次从同一个 PMX、VMD、配置重新起进程；frame start、substeps、solver iterations、FPS、cache 清理、初始姿态完全相同。
2. **只改一个变量**：允许或禁止 outfit↔body 配对碰撞；先比对导出后的 per-pair contact matrix，再运行物理。服装内部、身体内部不变。
3. 不允许在 setup 循环已预先模拟/填充缓存之后仅改 mask 就复用 point_cache；明确重建世界/清理缓存。
4. 每帧分别保存：bone/rb pose hashes，碰撞 pair 数，裙摆关键点轨迹，proxy overlap，真实衣/身 mesh 相交，皮肤可见露出；保留分母。
5. 报告 paired per-frame 差值、分区改善与退化；帧之间高度相关，不能把 80 帧×顶点数当成独立样本给“显著性”。
6. 至少三种动作：站立→大腿抬起、双腿交叉、急转身/坐下；额外做一次真实 MMD 对照。
7. 若 fixed 与 broken 的 Mode 0 代理位置、刚体静置 offset 不一致，整组 A/B 作废。

---

## 3. 脚部修复：放弃“整只靴子最近点包到脚上”

### 3.1 先确定真的需要保留哪些几何

刻晴的来源脚主要由单个 足先EX（约 8.15 cm）驱动；达妮娅是 足首D → 足D → 足先EX（约 4.71 cm）→ 多根脚趾骨，且同名 つま先 的方向差约 61.6°。**这是解剖语义不同，不是普通同比缩放。**

把脚区按材质 + 连通分量 + 表面朝向 + 局部位置 + UV 岛划为：

- A：漆皮脚面（贴皮涂装、单层、需要覆盖 B 的脚背/足趾）。
- B：有立体轮廓的鞋头、鞋帮/靴筒（应保留外形）。
- C：鞋底、鞋跟（应保持厚度、地面接触平面与硬度）。
- D：金饰/花纹/带扣（应随**B/C 的变形场**或单独刚性锚点运动，不能直接贴到皮肤）。
- E：过膝袜（应归入下一节的「目标腿壳」策略）。

对识别结果有疑义时，输出分色预览，允许用户只做一次选区确认，并缓存到可复用的部件 manifest。**不要用“主导骨=足先EX”取代鞋面语义分区**。

### 3.2 最省事的第一版（推荐优先落地）

如果鞋是不透明的：**先遮掉会露出的目标裸脚表面**（仅鞋子实际覆盖且远离开口的目标脚面），保留鞋的整体轮廓。这样可以很快减少裸脚“从鞋里面顶出来”的可见问题，同时不会把金饰拉坏。

实现要点：

1. 使用真实目标脚的 bone/材质/空间标识做脚部 semantic mask；**不是**直接删除“足”骨影响的全部面。
2. 在鞋头前缘内、鞋帮内的目标脚面，单独设不可见 skin material（或仅在稳定不可见区域删面）。
3. 保留鞋口/踝部过渡，并做 1–2 圈边界安全带；对透明鞋、镂空鞋、高分辨率近景不能靠隐藏兜底。
4. 同时检查「鞋头长度是否包住目标脚」「外观是否仍像原鞋」。如果靴子比目标脚实际短 2 cm，仅隐藏脚无法使其成为合理的鞋，应继续做 3.3 的几何变形。

这一步是**可见性工程补救**，报告里须标注“occlusion-fixed”，不得误写成真正几何包裹成功。

### 3.3 真正的几何解法：以脚踝/脚跟/趾尖构建鞋楦变形

不要按同名 足先EX → 足先EX 建一个单一比例变换。建立来源/目标局部解剖锚点：

~~~text
ankle: 踝关节中心
heel: 后跟底部/鞋跟中心
metatarsal: 跖趾根部
toe_tip: 最前脚趾的末端
sole_plane: 地面/鞋底参考平面
foot_axis: heel -> toe_tip
side_axis: 左右脚宽方向
up_axis: 足背方向
~~~

从来源鞋模型的位置 u（后跟到鞋头的归一化参数）、v（横向）、w（高度）出发，建立连续但**分部件约束**的 deformation field：

- 鞋头：沿 foot_axis 延长至 B 的 toe_tip + 安全余量；扩大鞋头宽、高，使鞋楦能包含目标前足体积。
- 鞋帮/靴筒：通过 ankle 和开口环位置过渡；不把靴筒上的点吸到脚表面。
- 鞋底：在局部 u,v 域拉长/展宽，但保持鞋底平面、鞋跟高度、局部边缘厚度。
- 金饰：从鞋面 barycentric/cage anchor 跟随变形，或保留完整局部刚性变换；禁止逐点最近皮肤投影。
- 权重：鞋头可主要跟随目标足部骨链中稳定的足/踝骨，鞋底不必逐根复制九根脚趾权重；**封闭鞋头不会像裸脚九趾一样独立弯曲**。脚趾外露鞋/袜则单独处理脚趾分区。
- 若是纯单层「涂层鞋面」，可以直接从目标脚生成 patch，再施加厚度/法线间隙并转移 UV/材质；不能把这个做法传播到鞋底/靴筒。

附加局部优化：对 B 前足的所有测试顶点，确保其在鞋楦包络内部且留有预期间隙；同时惩罚鞋的边长拉伸、法线翻转、UV 密度变化、自相交与装饰位移。优化目标不是单纯最近点距离最小。

### 3.4 什么时候才应该细分

只有当新增几何能**保持既有外形**、且某些三角面跨度大到无法表达足背/指缝形状时才细分。推荐按局部曲率、目标脚包络偏差、自相交风险自适应分区细分（每次有预算上限），不是简单比较 608 vs 3924 顶点。

验收：
- 原鞋面 patch 的三角形数/边长分布明显改善；
- UV seam、顶点组权重和、形态键、材质分区、金饰位置保持；
- 静态与脚尖屈伸等 5–8 种动作：裸脚可见面积接近 0，鞋头多角度无破洞，面翻转数 0，装饰不拉成条；
- 关闭 body mask 的工程复核模式仍能显示真实穿透/内部间隙。

---

## 4. 通用的「漆皮层」解决方案：body-derived shell

贴皮手套、涂层鞋、丝袜/过膝袜来自**来源身体的外表面本身**，其零厚度表面不应被当成“需要保留原体积的普通衣服”。

建议引入一个新的 garment archetype：

~~~text
shell_on_body
  target_surface_region
  source_appearance_uv
  clearance_mm
  surface_offset_policy
  boundary_policy
  deformation_policy
~~~

推荐处理：

1. **拓扑/语义匹配**：按目标身体部位（左右手、各指、左右腿、脚）确定需要覆盖的目标三角片。来源漆皮只用来确定**覆盖范围、外观、UV/装饰对应**，不强行沿用其低密度三角形位置。
2. **生成目标皮肤副本**：复制 B 对应片区几何和骨骼权重/绑定拓扑；外移很小的物理间隙，或在不透明条件下贴合原皮肤并隐藏下层皮肤。这样弯曲时两层天然更一致。
3. **转移来源 UV/外观**：优先根据部位参数化（手指纵向 u / 环向 θ、腿骨纵向 + 截面、脚背参数）；局部最近三角面 + 重心坐标只是外观映射候选，必须有 domain 限制和映射置信度；避免把中指 UV 转给食指。
4. **边界拼接**：按手套口、袜口、靴口的 boundary loops 自动建立平滑环带；如果 patch 与衣服主体不共边，可允许小量视觉遮挡或生成 bridge strip，不强制跨远距离的 mesh adjacency 做三环扩散。
5. **装饰独立**：半透明高光层、金属饰边可复用源几何，但位置取 shell 上的面锚点，法线方向和切线跟随 shell。透明双层须考虑 z-fighting、排序和原 MMD 材质特性。
6. **多姿态补正**：如果粗细差 1.4 倍/关节紧绷，单靠贴 B 皮肤仍不足以防止厚手套穿模；只对确实需要的外层做 pose-corrective morph 或局部安全间隙。

这个架构特别适合此项目「固定素体 B、不同成品 A 拆衣」：**target shell 可以缓存一次、多件衣服复用**。这是比反复改善来源模型上的投影更省力的长期架构。

注意：覆盖范围与 UV 迁移不是全自动能永远正确。材质名“腿”只能提供低置信度候选，首次建议显示预览供确认；确认结果按来源模型 hash 缓存。

---

## 5. QA 设计：新增可解释且不会被“删面”刷分的指标

### 5.1 明确三类问题，不能合计成一个“穿模率”

**A. 视觉覆盖问题**：裸脚/露手指/露腿、鞋头不足。用多个相机的 depth pass + object/material ID 或皮肤可见像素面积（百分比、mm² 代理）验证。注意透明材质另测。

**B. 几何交叉问题**：目标身体与服装表面真实相交、非封闭壳的局部 signed side、面翻转、破洞。按 garment semantic parts 输出相交三角形对、最大/95 分位穿透深度与接触区面积估计；开口处不能使用普通封闭 inside 判断。

**C. 物理代理问题**：哪些刚体对理论上允许/禁止碰撞、实际 Bullet 接触和裙摆在 leg proxy 内的数量；它是物理诊断而不是最终视觉指标。

### 5.2 确定性、分母与抗作弊

- 所有长度明确记录 **Blender world units** 与转为 mm 的 conversion（当前导入 PMX scale=0.08，导出=12.5；但不应脱离 scene/unit/object transforms 自称“毫米”）。
- 结果带：基线 git SHA、Blender 版本、mmd_tools 版本、PMX/VMD SHA256、配置 hash、帧列表、physics solver 参数、mesh face/vertex 数、body mask 的隐藏/删除数量。
- 优先比较同一**未被遮盖的 ground-truth body mesh**，而不是已经被模型修复过程删掉 10,272 面后的可见残余皮肤。
- 统计比例用原始 body 区域的固定采样点、相同帧与面积权重；细分后旧顶点数量不可作为直接可比的质量指标。
- 对于低密度鞋面，必须采样 triangle interior（边中点、质心乃至自适应分层采样），不能只数顶点。
- 出现 0 穿模时也检查骨骼/裙摆实际每帧位移范围、非零 pose hash；**0 + 无运动 = QA FAILED/UNKNOWN**。
- 报告带 fail-fast：没有模型 split、face index 不合法、没有真实 physics advancement、BVH 空集、cache 未重建、导出重导入数据不匹配，均不得写 OK。

### 5.3 推荐最低回归门槛

1. 纯净物理：静止 100 帧 Mode 0 代理不漂移，关节不爆炸；服装骨骼真实变化且数值有限。
2. 网格求值：同一 deform modifier 模型，pose A/B 的 evaluated 顶点位置不同；换 Blender 5.2 的 new_from_object(evaluated_obj) 应与 evaluated_obj.to_mesh() 在顶点/坐标/法线容差内一致（在拓扑不变时）。
3. 变换不变性：对整组人物施加平移/旋转/统一缩放后，在换算到相同物理单位的条件下碰撞结果一致。
4. 一次“故意把脚伸出鞋 20 mm”的坏例子必须被检测为重大漏出，不能因 6 mm 阈值报 0。
5. 细分后对比 mesh 拓扑、UV、权重、所有形态键和 PMX roundtrip；任何不一致则自动回退。
6. A/B 至少逐帧保存 paired diff，不只汇总整段点数。
7. 过膝袜/材质“腿”既有应选例，也必须有裸腿错误选中的反例。

---

## 6. 建议的更轻量架构

不建议再堆一套通用「所有衣服顶点往最近皮肤投影」分支。将 pipeline 按**服装类型**分配算法，复用已稳定的工具：

~~~text
[来源材质/连通件识别 + 一次人工确认]
                    |
             garment manifest
                    |
     +--------------+----------------+-------------------+
     |              |                |                   |
 body-derived     fitted_shell     rigid/semi-rigid    loose cloth
 手套/袜/漆皮      鞋楦/鞋头         鞋底/装饰/护甲       裙摆/袖子
 B 表面复用         cage + anchors    rigid anchors      原骨骼+物理
     |              |                |                   |
     +--------------+----------------+-------------------+
                    |
           骨架与权重语义层
                    |
       静态/动态/物理分级 QA
                    |
         失败定位与局部修复
                    |
           PMX export/roundtrip
~~~

**推荐的下一批实现计划（可直接交给执行 Agent）：**

- **R0 / P0**：修 physics_sim 的 rest offset 和 mode2；构建 contact matrix，对碰撞 collection 编码写单元测试；独立保存 body collider 轨迹；重跑 4347/4542 比较并在结果中区分真实/代理。
- **R1 / P0**：全面统一 BVH 世界坐标，修 QA 的 6 mm 指标盲区，新增露皮可见性与 mesh 相交检测；测试位移不变性。
- **R2 / P0**：禁用默认鞋面最近点修复；鞋分区（漆皮、鞋头/帮、底、金饰）和初版「隐藏目标脚遮盖区」，立即检查外观。
- **R3 / P1**：实现 foot anatomical cage、鞋头体积包络和装饰锚点；只对确需密度的鞋面拓扑做经 UV/weight/Morph 验证的自适应细分。
- **R4 / P1**：从 B 的体表生成 glove/stocking/painted-shoe shell，转移来源 UV 和材质；完成边界/指缝 QA。
- **R5 / P1**：修 transfer_target_weights 双重混合，建立 morph-compatible warp；加入输出验收阈值和自动回滚。

**避免防御性过度设计**：只针对「固定 B」缓存一次解剖标志、皮肤分区、shell 和权重；来源 A 只保留材质分区配置及局部 anchor 映射。先为刻晴→达妮娅建立金标准的 3 个小测试（手套、鞋、袜），跑通后再扩展衣服类别。

---

## 7. 结论

1. **b803f91 的 evaluated.to_mesh() 修复方向是对的**；但 new_from_object 的 API 注释需精确化，物理位移非零不等于真实 MMD 动力学已经对齐。
2. **当前最大可靠性风险不是 Blender 5.2 API，而是 physics_sim 的骨骼–刚体静置 offset、collision_collections 与 PMX group/mask 的不等价，以及 QA 的 local/world 混用。** 这些优先于解释 4.3%。
3. **鞋子的优先处理策略应是语义拆件 + B 表面派生漆皮 + 鞋楦尺度适配 + 必要的隐藏露脚皮肤**；盲目细分和投影可能加剧鞋帮断裂及金饰拉伸。
4. **608/3924 是风险线索，不是充分根因证明**。要以目标脚相对鞋楦的体积覆盖、可见露皮、局部面交叉和运动姿态来判定真实改善。
5. **零厚度服装单独走 body-derived shell** 最符合“固定素体、多来源成品模型拆衣”的长期需求，也能减少重复处理成本。

### 本审查使用的资料

- 仓库：NiHaiMa123/mmd，基线 b803f91（本文件所有代码位置指该提交的行号）。
- progress.md：截至本提交记录的腿/鞋/物理实测数据；本审查没有独立复跑。
- Blender Python API： https://docs.blender.org/api/current/bpy.types.BlendDataMeshes.html （new_from_object，原始对象与 evaluated object 区别）；https://docs.blender.org/api/current/bpy.types.Object.html （evaluated_get / to_mesh）；https://docs.blender.org/api/current/bmesh.ops.html （subdivide_edges）。
