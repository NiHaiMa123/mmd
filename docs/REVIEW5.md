# REVIEW5 — 第五轮代码审查：物理代理重复性、目标权重与鞋/脚踝视觉证据

> 仓库：NiHaiMa123/mmd  
> **审查基线**：main @ **6d02ed9e9de8e7f7a8af5fbc5c3f8041359cd640**  
> 对比基线：62ca5e563e79b2e16e93469f1dff60a1d20d57fe（REVIEW4）；其后本批代码、测试、文档和三张 final24 截图均已纳入。  
> 审查范围：<code>src/dressing.py</code>、<code>src/physics_sim.py</code>、<code>src/qa.py</code>、<code>tests/test_subdivide.py</code>、<code>progress.md</code>，以及本轮消息附带的三张 final24 图片。  
> 审查方式：静态逐函数审查、构造性反例、图像观察和对用户实验记录的解释；**没有独立运行 Blender 5.2、PMX 仿真或 VMD**。  
> 写入约束：**本提交只新建 <code>docs/REVIEW5.md</code>，不修改任何源码、测试或旧 review。**

## 0. 结论与执行排序

**下一批不应立刻用“Blender 物理最差帧百分比”指导改模型。** 当前 final24 的两个独立物理 QA 结果 1.988% / 2.319% 已暴露出显著的重复性问题；而普通动作 QA 1.045% 与物理代理约 2% 反向变动，正好需要**把“骨骼求值”和“皮肤/服装蒙皮”拆开测**。

最合适的顺序：

1. **P0（很小的验证工作，优先）——针对新权重语义做冻结姿态的 2×2 实验。** 它可以直接分辨“同一组骨矩阵下新袜层蒙皮就出错”与“physics→bone handler 造成骨矩阵/求值顺序变化”，无需重新实现整套 MMD 物理。这批源码中另有一条明确的目标辅助骨权重混合漏洞（详见 §2）。
2. **P0/P1（低风险验证）——对物理代理做至少 5 次冷启动重复性实验，并定位第一帧分叉**；短期**取消物理百分比的跨模型通过/失败阈值**，只保留分布、运行质量和异常定位。
3. **P1——先补 R4-P1-07（统一坐标系）并设置不变性测试**，之后补 R4-P1-06（膝带混合后 clearance）。两者属于低层正确性，比重新扩鞋更能提升这套自动换装算法的通用性；但要以固定 final24 baseline A/B 隔离更改。
4. **P1/P2——鞋单独做“设计语义 / 前掌包络 / 可见性”分诊**。附图里的鞋**看起来是前端露趾的开放式鞋面/凉鞋结构**；不能按“封闭不透明鞋”直接把所有 B 脚趾隐藏，否则可能把本应显示的皮肤抹成空洞。先对照 A 原鞋参考、确定正确的可见趾区，再决定局部鞋帮变宽还是需要重做鞋。
5. **物理引擎 MMD 级对照**留在后续可选实验；比自己重写求解器更现实的是把正确 PMX 过滤映射成受约束的 Blender 近场 pair 禁碰，或引入支持 MMD 的现成运行时作为并行 oracle。

---

## 1. REVIEW4 修改核对：哪些真正完成了？

| 本批更改 | 源码核对结果 | 仍存风险 |
| --- | --- | --- |
| fan center UV 固定 | **已修上一轮不连续问题**，<code>src/dressing.py:1334–1363</code> 每个 fan 的 UV layer 确实只生成一个 <code>centre_uv</code> 并复用。 | **新隐患**：中心 UV 用“拆分后边界所有点”的平均，而几何中心仍用“拆分前原始角点”的平均；不一致会产生 UV 畸变，见 §3。 |
| 多层 UV、shape-key 插值 | <code>subdivide_triangles</code> 保留了此前的处理；对 PMX 三角面适用方向正确。 | 尚未覆盖所有一般 vertex/corner attributes；<code>mmd_vertex_order</code> 等离散含义不应机械插值。 |
| 外来骨分类 | <code>project_layer_on_limb</code> 已把目标皮肤真实使用的骨作为 <code>target_bones</code>，且服装骨不会让整层直接跳过；伪组不入权重归一化。 | **目标已存在的辅助骨只衰减却未取 B 的新值**；保留服装骨参与归一化可能改变其权重，见 §2。 |
| 权重覆盖率统计 | 有 <code>vertices_selected/reweighted/no_nearest/no_real_bone</code>。 | **4522/4522/0/0 仅表示尝试并找到了参考面，不代表目标权重插值精确、没有错误辅助骨或动态正确。** |
| near_differing | <code>src/physics_sim.py:224–240</code> 的 near append 已移到 <code>if near</code> 内：**确认修复。** | <code>worst_group_pairs</code> 仍按全局错误排序，<code>near_differing</code> 只是这些全局 top10 的近场子数；不是近场 top10。 |
| QA 分母 | <code>src/qa.py:326–360</code> 现有 positive/nonpositive/missing，且物理 QA 也导出同口径：**确认完成**。 | rest_sign 为负的点可能对应原本内穿、朝向不一致；它们不是“未检查但没问题”，必须单独观察；“脚部 0 命中”仅适用于 314 个 reference-positive 点的这一种 6mm 检测器。 |
| tests/test_subdivide.py 纳入版本控制 | **已确认**：189 行、构造网格、可运行而无需角色资源；相比 gitignored work/ 显著进步。 | **目前脚本失败也可能以 exit code 0 结束**；ShapeKey 测试并没有精确验证新顶点的预期 morph 位置，详见 §3。 |
| R4-P1-06/P1-07 | 尚未修：<code>project_layer_on_limb</code> 中仍是目标 mesh local BVH、世界骨轴、garment local 顶点直接互算。 | 建议先做变换不变性测试再改，不能仅因当前模型 object transforms 接近单位矩阵而视为正确。 |
| 脚踝下沿与靴口对齐 | <code>src/dressing.py:1557–1667</code> 新增了按 boot 材质边界寻找 collar 并吸附 hem 的实现。 | 当前方法是“每个 hem 顶点找到最近边界线段”，不保证左右/前后拓扑顺序、不保证动画下持续吻合；跟随靴口会制造局部超大位移，需专门验收。 |

### 当前图片实见与项目描述的区别

此次**确实收到并查看了用户上传的三张 PNG**，不是上一轮的“只能看到仓库里有文件”。

- **全身图**：右大腿/小腿的金色纹路确实清晰可见，证明至少有相关表面与材质出现；这不能独立证明几何在所有动作都贴 B 皮肤。
- **踝部侧面图**：相比项目所述旧版尖片已被修复，这张图片里仍能看到靴口上方**明显的浅白三角状/楔形区域**，边界很硬。它未必是同一个“戳出的白尖片”：可能是源腿皮/隐藏 B 皮、材质 alpha、法线或真实网格缺口。**不能仅凭图像判明材质和朝向**，但值得加材质 ID false-color 单帧验证。
- **脚部正面**：紫色鞋面前端有开口，脚趾露在紫色鞋帮前/下方，视觉上类似开放式露趾鞋/凉鞋。**露趾不一定全是错误**：必须对比 A 原鞋设计以及 B 脚趾相对鞋底前缘/鞋帮开口的实际突出量。目标仅应消除**非设计预期的多余露趾**，而不是让脚趾消失。

---

## 2. [P0] 目标辅助骨权重迁移仍存在确定性漏洞

### R5-P0-01：已存在的目标辅助骨被衰减，却没有回填目标插值权重

**位置**：<code>src/dressing.py:551–582</code>；调用来自 <code>project_layer_on_limb:1681–1704</code>。

最新代码有两套概念：

- <code>body_bones</code>：来源/目标共同映射的骨名集合；
- <code>target_bones</code>：B 的实际皮肤顶点组中、且存在于目标骨架的骨名集合。

**问题：前半段仍仅按 <code>body_bones</code> 处理“旧顶点已经有的组”，后半段只给“当前顶点**没有**的组”补 B 权重。**

~~~python
# 已有组
if name in body_bones:
    new[name] = t * blended.get(name, 0) + (1-t) * old
elif name in keep_bones:
    new[name] = old
else:
    new[name] = (1-t) * old

# B 目标权重补组
for name, weight in blended.items():
    allowed = target_bones if target_bones is not None else body_bones
    if name in allowed and name not in current[vi]:
        new[name] += t * weight
~~~

构造性反例：目标 B 的 <code>足D++.L</code> 是 skin bone、**不在 <code>body_bones</code>**，而来源换装结果某个顶点在迁移前已恰好有该名字，旧权重 0.20，B 对应位置的插值应为 0.50；t=1。前半段因未在 <code>body_bones</code>，且该名字属于 B skin bone，所以不在 <code>keep_bones</code>，被乘 (1−1)=0。后半段因 <code>name in current[vi]</code>，也不补 0.50。**B 的真实辅助骨 influence 静默丢失**，最终再将剩余权重归一化掩盖了错误。

本次实验确实新增了目标辅助骨权重，这条 bug 不是“一定造成 final24 2%”的证明，但与症状高度相关，且可以用一个 3 顶点 fixture 独立确证。

**正确的权重更新必须以“骨骼语义”而不是“旧顶点是否已拥有这个组”决定**。推荐 per-vertex 先拆成三个互斥集合：

- target_skin_bones：B 真实蒙皮骨；目标权重以 <code>blended[name]</code> 为准（t=1 完整替代）；
- preserve_garment_bones：必须保留的衣服专用骨/chain；明确是否参与归一化与保留多少预算；
- pseudo/meta：<code>mmd_edge_scale</code>、<code>mmd_vertex_order</code> 等，完全独立保存，不参与普通骨骼求和。

建议直接先做：</br>
<code>new[name] = t*blended[name] + (1-t)*old[name]</code>，对**所有 target_skin_bones**（而非仅 body_bones）统一执行；补缺失目标组时不再依赖 <code>name not in current</code> 的歧义分支。存在 garment bone 时明确分配 <code>garment_budget</code>、<code>skin_budget=1-garment_budget</code>，再单独归一化，不要把保留组和替代组一起无意缩放。

**验收要求**：

1. 造 <code>足D++.L</code> 等辅助骨“旧组已存在 / 尚不存在”的两个顶点，保证 t=1 后二者都等于同一目标 B 插值权重（误差≤1e−5，归一化前后明确）。
2. 再测带 source garment bone 的 1 个混合顶点，检查是否按预算保持专用骨语义。
3. 输出变化分布：每个袖/腿局部的 L1 权重差、已存在 B 辅助骨的丢失数、归一化前/后骨重总和、没有合法骨权重的顶点、目标辅助骨 Top20 权重/空间坐标直方图。
4. 对穿越膝/踝的几根真实骨做 5 个关键姿态的袜层→目标皮肤对应点距离图；**不允许只凭 <code>vertices_reweighted=4522</code> 判定成功**。

### R5-P1-02：<code>keep_bones</code> 并不等于“绝对权重不变”

在 <code>transfer_target_weights()</code> 中 <code>keep_bones</code> 旧权重被放入 <code>new</code> 后，<code>total</code> 把它算进去，并**对所有非伪组统一归一化**。所以“保留”只是保留影响项而非固定原权重数值。例如保留服装骨 0.20、target B skin 权重按 t=1 转来总和为 1.0，归一化后服装骨约变为 0.167，B 权重 0.833。并不意味着这一定错误，但需要**明确谁占骨重预算**，否则后续姿态输出可能出乎预期。

### R5-P1-03：目标辅助骨名称的出现 ≠ 它必然由 IK 直接驱动

PMX 不会根据名字来决定驱动方式。<code>ひざ回転.L</code>、<code>足回転+.L</code>、<code>足D++.L</code>、<code>腰+.L</code> 可能是：

- 直接 IK solver 的 link / target / effector；
- 从 IK 骨**继承（append/grant）**变换的辅助骨；
- 依父子层级/变形顺序计算的骨；
- 带“物理后变形”标志、受到物理驱动祖先影响的骨；
- 普通动画、约束或驱动控制骨。

它们**不全等于 IK 骨**。必须从导出/重导入 PMX **按 bone index**读取 <code>is_ik / ik_links / grant parent+ratio / transform_order / after_physics / rigid-body driving-bone</code>，再对照 Blender 的 PoseBone constraints、driver、矩阵结果。名字像调整骨没有证据价值。

目标 skin 上确实可能存在 <code>LabiaMajora</code>、<code>Pussy</code> 等骨，它们是角色自定义骨名；是否说明袜层发生**错误最近面映射**，取决于它们被分配到袜层的**具体 3D 顶点位置及权重大小**，不能仅因名字就认定非法。例如如果这些 influence 出现在小腿中段，就是高度可疑；在裆/大腿根部若最近面确实属于目标皮肤，则需继续按空间域确认。

**目前新代码 <code>domains=False</code>**（<code>src/dressing.py:1700–1704</code>），意味着即使目标有手指/腿部域区分，袜层权重仍是**在完整 B 身体皮肤 BVH 上最近面查找**，然后最多过滤骨名。建议至少限制 L/R 同侧、thigh/shin/ankle 分段与骨骼/连通组件，输出袜顶点→B 目标三角形所属区域。一个靠近大腿根的顶点非常容易找到错误区域却仍落在 <code>max_dist=0.05</code> 以内。

---

## 3. [P1] 细分修复已消除 UV 断裂，但测试存在两个缺陷

### R5-P1-04：fan 的 UV 中心与几何中心并不严格对应

当前 <code>src/dressing.py:1263–1273</code> 中的几何中心是**原始 n 个角点坐标平均**，而 <code>src/dressing.py:1334–1350</code> 中的 UV 中心是**扇形外围 seq 的所有点（含插入的边中点）的平均**。当有部分边被拆、有部分边保留时，UV 中心会朝“拆得多的边”偏移。中心 UV 只有一个、相邻面连续是正确的；但**不意味着不改变原来的 UV 线性映射**。

对于原始三角面，正确的 barycentric 中心 UV 应为**原始三个 loop UV 的平均**，对应 original corner coordinates 的几何重心；对四边面需按几何中心的插值规则选择相应算法（简单仿射 UV 对非共面四边形不一定准确）。

建议：中心 UV 用 <code>original_corner_uvs</code> 平均而不是 <code>seq_uv</code> 平均；或把 geometry centre 与 UV centre 都统一用相同的重心权重。别再次误修回“每个 fan face 一个中心 UV”。

### R5-P1-05：<code>tests/test_subdivide.py</code> 并非可靠的 CI 通过/失败闸门

**代码确有两个问题**：

1. 最后仅调用 <code>main()</code>（<code>tests/test_subdivide.py:188</code>），内部打印 <code>RESULT: OK/PROBLEM</code>，**但没有 raise 或 <code>sys.exit(1)</code>**。因此如果断言不成立，只要 Blender/Python 没抛异常，shell 仍可能得到退出码 **0**，自动化会把失败当成功。
2. <code>test_fan_centre()</code> 只验证中心 UV 的**不同取值数=1**，没有验证该值是否等于预期原面重心 UV；ShapeKey 检查“原始顶点 Z 没变”和“Z 数组长度等于新顶点数”，不能证明新顶点 Morph 位置做了正确插值。

另外当前测试构造一个 UV layer、一个 Morph，不覆盖双 UV layer、跨 UV seam、离散 mmd_vertex_order，以及“既有 B 辅助骨”的权重混合情况；可补最小 fixture，而不需要整套模型。推荐改测试入口为 <code>if not main(): raise SystemExit(1)</code>，并添加精确数值断言。

以上都是**测试覆盖/质量**问题，不推翻本轮“11 项基本测试已移入仓库”的进步。

---

## 4. [P0] 物理代理不重复：该如何定性、如何报告？

### 4.1 数据事实与不能过度推断的部分

| 模型 | 同一流程两次结果（最差帧 sign-flip proxy） | 两次差距 |
| --- | --- | --- |
| final22 | 1.156%、1.156% | 当前精度一致；不代表所有运行完全相同 |
| final23 | 1.153%、1.172% | 0.019 个百分点 |
| **final24** | **1.988%、2.319%** | **0.331 个百分点**，相对较小值约 **+16.7%** |

这能证明：**final24 当前整个 Blender 物理 QA 流程的“最差帧”聚合指标，在两次运行之间不稳定。** 两次样本尚不足以证明根因就是 Bullet 多线程数值随机性，也不能证明每个物理刚体轨迹都不同。

其它可能来源包括：

- setup 每次运行的**两遍“已经求解后再写 Mode0 keyframes”**，第二遍开始前仅把 <code>point_cache.frame_start</code> 来回拨，非明示 clean restart；
- <code>frame_change_post</code> 中写入 PoseBone matrix 并立即 <code>bpy.context.view_layer.update()</code>，与 frame_set/depsgraph 同帧求值顺序/IK/constraint 竞争；
- 物理接触轨迹对细小初始条件/solver/线程/对象迭代顺序敏感，用户看到的漂移可能被复杂物理链放大；
- **即使物理刚体状态完全一致**，final24 的袜层新 skinning、蒙皮权重/形态键、参考符号和 BVH 查找也可能导致 sign-flip **分类在 1mm 阈值附近翻转**；
- <code>max_ratio</code> 是有限离散采样帧中的 **最大值**，比 per-frame 平均值更敏感，且只比较这个数字不能判断“是哪一帧”以及“哪些点”分叉。

**“同代码重跑 final22 仍逐位等于 1.156%”**证明它在这一测试条件下稳定，不构成“新 QA/physics_sim 必不引入变化”的严格证明：final24 可能恰好激活了不同的辅助骨/几何/时序分支。差异也可能来自**测量输入模型结构改变**，而不是 Bullet 仿真本体变了。

### 4.2 立即采用的统计政策

**推荐：N=5 个真正独立冷启动进程作为初筛**。如果跨度不明显，可以不增加；如果存在大跨度，再对 final24 和待比较版各做 N=10 次以看区间是否稳定。所有运行固定 Blender build、插件版本、CPU/线程、world settings、VMD、frame range、fps/substeps、solver iterations、对象顺序、初始场景和素材 hash，保存每次全部 per-frame 数字。

不能把同一 Blender 进程按两遍缓存反复跳帧的结果当 N 次独立仿真。

**目前的 QA 级别**：

- <code>physics_proxy_execution=OBSERVED</code>：执行过，求值网格/刚体确有非零活动；
- <code>physics_proxy_reproducibility=UNSTABLE</code>（对 final24）；
- <code>physics_proxy_comparative_acceptance=DISABLED</code>：**不得因为 1.988% 比 1.156% 大就自动判 fail，也不得因均值较小就判 pass**；
- <code>pmx_logic_validation</code> 与 <code>ordinary_motion_qa</code> 保留独立结论；
- <code>mmd_runtime_validation=UNKNOWN</code>。

报告每版单独给出 <code>N、min、median、max、p95</code>、max_ratio 的 run-to-run range、最坏帧 ID 的分布、按帧 median/范围、腰/腿/躯干相同帧 ID 的差异；N=5 的 p95 非稳健推断，宜注明其只是在样本中接近最大值，**不要把它包装成统计置信区间**。如果两个版本的单次值差异比本身重复运行跨度还小，标为 <code>INDETERMINATE</code>。

独立于比例指标，仍保留“rigid 静置偏移发散、NaN、姿态异常、穿透/身体移出视野”等硬失败条件：**重现不了的性能比较应禁用，明显物理数值灾难仍可拦截**。

建议增加：

~~~json
{
  "measure": "blender_signflip_proxy_6mm",
  "model": "final24",
  "engine": "Blender Bullet approximation",
  "independent_runs": 2,
  "observations_percent": [1.988, 2.319],
  "run_to_run_range_percentage_points": 0.331,
  "reproducibility": "UNSTABLE",
  "proxy_for_mmd_fidelity": false,
  "comparative_gate": "DISABLED",
  "mmd_runtime_validated": false
}
~~~

### 4.3 更重要的是定位：第一处不一致出现在哪里？

在没有发现首个分叉层之前，无法知道“Blender 物理不稳定”还是“骨骼回写/蒙皮/测量不稳定”。

按**相同具体帧号、相同稳定 rigid ID、稳定 bone ID、稳定顶点 ID**比较两次：

~~~text
Stage 0：导入静置的 rigid 参数 + world / joint 参数 + bone 初始矩阵 hash 是否相等？
Stage 1：setup 两遍扫描结束后的 kinematic Mode0 曲线 hash 是否相等？
Stage 2：每帧 Mode1/2 刚体 evaluated world matrix 是否相等？
Stage 3：handler 写回前后 bone matrices、IK/append/after-physics 骨是否相等？
Stage 4：同一帧下目标 B 皮肤与 A 腿皮的 evaluated vertex positions 是否相等？
Stage 5：相同顶点的最近服装面、距离、side sign、6mm 判定是否相等？
~~~

最早出现分叉的 Stage 决定下一步；严禁只看末尾 <code>max_ratio</code> 去推断根因。

**低成本用例**：final24 连续 5 次，逐帧输出足D++、ひざ回転、足回転+、腰+ 等 10 根骨矩阵和 10 个同位置左右相应刚体矩阵。若 rigid 第一分叉发生在第 340 帧且 Mode0 keyframes 已不一致，优先查双遍 cache；若 rigid 全同而 skin 顶点有不同，优先查 depsgraph/armature；若所有 geometry 坐标全同而 hits 不同，优先查 BVH/排序/比较阈值/索引生命周期。

---

## 5. [P0] 为什么“普通 QA 改善、物理 QA 变差”？最小 2×2 实验

### 5.1 可以成立的机制，但现在都不是已证明根因

普通 QA：只有 VMD 驱动骨姿态、没有本工程 physics_sim 的重定位写回；新 target-weight 对齐 B，贴皮层相对 B 更稳定 → 指标改善（1.323%→1.045%，腿区 553→385）是合理现象。

物理 QA：在 setup 的 <code>frame_change_post</code> 中，**Mode1/2 rigid 当前物理矩阵会直接覆盖同名 PoseBone 的 world pose**（<code>src/physics_sim.py:420–427</code>），同时 Blender 重新求值 IK、append、约束和 armature modifiers。目标 B 的辅助骨可能经由 IK / grant / 层级间接依赖这些被覆盖的骨；新袜层对它们赋予了与以前不同的 skin weights，可能放大它们在 post-physics 状态下的动作。

但这**不自动意味着**“袜层与 B 皮肤的同名骨不同步”——如果 B 皮肤与袜层在相同帧都使用相同最终骨矩阵、同样的 normalized bone weights、相同绑定空间与蒙皮类型，则它们应由相同的骨变换驱动；相互错位更可能来自：
- **权重值/域映射不一致**（见 R5-P0-01、<code>domains=False</code>）；
- B 原生皮肤与 A 迁移层的 BDEF/SDEF、shape key 或 bind-space 处理不同；
- frame_change_post 写回原始 pose 后、某一 mesh 被 evaluated 得过早/迟；
- 初始几何并未严格处于目标 B 皮肤同一法线偏移；
- 物理 rigid 轨迹本身就变化，使不同 frame 的几何位移放大。

### 5.2 **最小验证：两种权重 × 两种骨骼轨迹，不必改 solver**

从同一份目标 B 骨架和同一个 final24 的几何出发，只准备两套**相同顶点/拓扑**的袜层 skin weights：

- **W_old**：final23（旧权重白名单）；如果两版顶点索引因细分不同，必须基于 final24 几何**重新生成旧权重**，不能按旧 mesh 顶点编号硬拷；
- **W_new**：final24（接受 B 皮肤辅助骨的新版）。

再准备两条骨轨迹：

- **M_anim**：仅 VMD 动画的每帧**最终 evaluated bone matrices**（不要只记 action F-curves，IK/append 结果可能不同）；
- **M_phys**：从**一次指定的 final24 物理代理运行**逐帧记录 **physics→bone handler 后的最终 evaluated bone matrices**；把结果缓存为纯矩阵，之后**禁用 Bullet 和 handler**回放它，确保 W_old/W_new 用的是**完全同一份**轨迹。

构造 2×2：

| | M_anim：无物理骨矩阵轨迹 | M_phys：固定回放一次物理骨矩阵轨迹 |
| --- | --- | --- |
| **W_old** | A：旧权重 + 普通骨轨迹 | B：旧权重 + 固定物理骨轨迹 |
| **W_new** | C：新权重 + 普通骨轨迹 | D：新权重 + 固定物理骨轨迹 |

**同时读取 B 目标皮肤与 A 漆皮层的最终 evaluated 顶点位置**，以相同目标皮肤 patch 的表面距离、法线偏移和 sign-flip hits 为指标。

解释：
- C 好于 A、D 坏于 B，同时 M_phys 完全固定 → **权重×物理姿态有交互**，物理数值随机性不是必需解释；继续查某些骨的权重与位移贡献。
- D 与 B 差不多，但真实重新运行 physics 模拟结果波动 → 优先查 cache、动态求解和 handler。
- D 在全新权重和相同骨矩阵下仍稳定偏离 B 皮肤 → 权重映射 / bind-space / SDEF 有问题。
- A/C 的差异与原普通 QA 不同 → 你的 weight-only fixture 没有真正隔离材质、遮蔽、mesh、动作或形态键。

**不需一次把 633 根骨全部 dump**：先记录所有**实际影响这 4522 个袜层顶点的骨**、其祖先与 grant/IK 链，按稳定 bone index 和矩阵保存；先测造成最高局部差值的 5 个帧，再扩大到 6 帧或完整 340–420。

### 5.3 进一步收缩到一根骨的“去除/保留”消融试验

对 final24 的袜层单独构造：

- 保留全部 target-weight（baseline）；
- 将**某一组**（例如 <code>足D++.L</code>）对这些袜层顶点的 influence 置 0，**只在该局部片区重新归一化其余真实骨权重**；
- 保持 B 皮肤、rigid、joint、VMD、frame 和 physics 回放矩阵不变；
- 对每个候选 bone 做 one-at-a-time 消融，输出影响顶点数量、受影响区域（具体上/下腿与左右）、权重和、相对 B 皮肤的距离变化。

这只能作为**定位**，不能自动证明从成品删除该骨是正确修复；如果 B 皮肤实际需要它，最终修复仍要恢复正确 target mapping/求值序列。

### 5.4 需要核实的骨骼计算顺序

对于每个疑似骨，从 PMX 原始数据/导入对象导出完整诊断：

~~~text
bone_name / index / parent_index / transform_order
is_ik, ik_target, ik_links
append_rotation, append_translation, grant_parent, grant_ratio
transform_after_physics
rigid_mode and physics-driven bone mapping
Blender pose constraints / drivers
VMD-only world matrix (f)
physics handler pre-write world matrix (f)
physics handler post-write world matrix (f)
final evaluated world matrix (f)
~~~

PMX 存在 IK、append/grant 和“物理后变形”概念，不能把所有 <code>回転</code>、<code>D++</code> 辅助骨泛称 IK。没有这些元数据，不应对 MMD 原版实际求值阶段下定论。

外部参考：<https://github.com/dskjal/OpenMMD/blob/main/docs/specification/pmx2.1-specification.md>、<https://noname0310.github.io/babylon-mmd/docs/reference/understanding-mmd-behaviour/introduction-to-pmx-and-pmd/>。

---

## 6. [P1] 本轮源码中还有几个易漏问题

### R5-P1-06：脚踝 collar snap 是纯空间最近，不是拓扑同点约束

<code>project_layer_on_limb()</code> 用材质筛出靴口单独壳体的边界线段，然后每个 hem 顶点吸到最近 segment：<code>src/dressing.py:1557–1624</code>。

优点是可直接消除静置“片区下沿伸出靴口”，且不会像把所有腿皮顶点拉低一样产生尖刺。但风险：
- **没有稳定的一一环对应**：近距离另一侧边/鞋跟后侧可能成为最近 segment；
- 不约束环上顶点顺序/切向，因此可能发生局部翻面、边缩短或相邻连接交叉；
- collar 查询在 pose 之前做，源腿皮和靴筒的骨骼权重可能不同，静置对齐**不等于踝弯曲动作对齐**；
- <code>hem_to_boot</code> 匹配靠材料名、上下 z 范围，其他同材质开放边也可能误中；
- snap 下沿最多 2.5 cm 位移是重要尺度，建议用 edge-length/triangle aspect/inversion 测试是否拉出细薄扇形。

建议在工具中标记真实“源腿片区 hem loop ↔ 靴口 collar loop”的有序对应（可依原模型 UV/空间弧长建立），并检查 **pose1–pose5 同一对边的最大 gap 和是否自交**。别把 source 编号映射直接当 target 完全匹配，尤其在面序重排后。

### R5-P1-07：R4-P1-07 世界/局部空间混用仍是实体级错误

<code>src/dressing.py:1446–1470、1492–1505、1625–1644</code> 同时用 B mesh-local BVH、world-space bone axes 和 A garment-local 顶点。建议**先做变换不变性失败复现**：

- 以 final24 输入复制一个世界整体平移和 Z=90° 旋转版本（以及单独旋转衣服/骨架的等价协调变换），比较**回转到 canonical-space 后**的 projected vertices、ray hits、weight transfer；
- 第一轮只统一 BVH/射线/位移为同一个 world 坐标系，再写回 garment local；
- 第二轮才做膝带两个投射结果混合之后的 clearance 恢复；否则同时改坐标和几何约束很难归因。

修复一项不得显著退化现有 final24 普通 QA 或引入新脚踝尖片，必须有截图和数值 baseline。

### R5-P1-08：物理 near-field 的代理边界

<code>src/physics_sim.py:105–123</code> 使用刚体对象**显示 mesh 顶点的外接球半径**估计 Bullet 碰撞形状的包围球半径。如果刚体 collision_shape、scale、margin 与显示网格不一致，该半径不一定是真实保守包围；即使半径合理，未旋转 AABB/swept interval 也可能遗漏高速碰撞。<code>dynamic_near_field</code> 在 15 帧间隔取样，不是连续 swept collision。

当前用于**提示哪些潜在错误 pair 值得看**足够；不应声称“全程实际近场 FP/FN 完整”，更不能将 potential pair 当真实发生碰撞的次数。

### R5-P1-09：qa 的 denominator 仍不是“已测试穿透”的完全分母

<code>reference_positive</code> 是满足静置 <code>rest_sign>1mm</code> 的点数；实际穿透判定还要求**当前最近衣服距离 <=6mm 和当前 side <−1mm**。这份分母比过去准确，但不是“对所有脚趾表面覆盖的有效检测”；特别是鞋靴开口处可能完全没有邻近服装面，且原本有意露趾。要输出 **per-frame active-distance-eligible** 以及渲染像素/鞋楦几何判定，保持“脚趾自然可见”与“脚趾异常突出”分开的语义。

---

## 7. 鞋：如何决定“局部透明遮蔽”还是重建？

### 7.1 附图提示：首先确认来源鞋的真实设计

在附图中，紫色鞋面**没有完整覆盖脚趾尖端**，前缘更像刻意的开放式露趾设计。鞋的表现更接近开口凉鞋/舞鞋，而不是传统“封闭鞋楦包住整只脚”。

因此从**成品视觉语义**上要区分：

1. **设计应露出的脚趾**：不能隐藏；如果当前已经符合 A 原鞋设计，保留。
2. **超出鞋底前缘/侧边、在鞋帮之外异常外溢的脚趾**：应通过鞋楦/局部形变或脚掌目标绑定处理，而不是整体 mask。
3. **穿透紫色鞋面、与鞋帮三角面相互交叉的脚趾**：可在鞋面**本应不透明的遮挡区域**局部隐藏被遮蔽的 B 皮肤，但必须保留本应从开口可见的 B 趾。
4. **黑色鞋底或鞋前掌面积不足**：脚趾伸出鞋底之外时，仅隐藏皮肤会造成“没有脚/没有鞋底”的假象；需要改鞋底/前掌设计或明确判定鞋型不兼容。

**所以：对于这张图，不能直接套用“封闭不透明鞋隐藏趾区”作为整体 fallback。** 只能用“根据来源原鞋可见域的局部遮蔽”，并严格测试从前/侧/下方可见的真实趾区。

### 7.2 不再跑旧失败的三条路线，先用“可观测宽度”定性

已经失败：
- 最近面贴附整个鞋面（靴面撕开/饰品变形）；
- capped 径向膨胀（对源鞋局部横截面不足）；
- 前向长度拉伸 factor=1（长度不是当前主要缺陷）。

但“目标脚宽 30% 以上”应由 **同一 heel→ball→toe 横向剖面数据**确认，而不是从算法 factor 上限直接推出。对 left/right 分别测：
- B 目标趾尖与鞋**鞋底最前缘**的实际沿脚轴伸出长度；
- B 各趾外缘与来源 A 设计鞋帮/脚底边界距离；
- 脚掌 ball 处鞋面宽、B 脚宽、鞋底宽、高度；
- 实际需要遮住的皮肤区域与来源原鞋允许露出的区域（可以使用来源角色设计截图作为 oracle）。

若 A 原设计是 open-toe，就优先 **保留脚趾+局部扩大鞋底前掌/鞋帮侧缘**；若来源其实是 closed-toe，只是模型被截断/重组出开口，再考虑补 toe cap 或局部鞋面。

### 7.3 可执行的最小鞋 POC

不用从零建鞋，也不需要让 5 根脚趾都用鞋皮单独覆盖：

1. 按材料+连通组件+沿 heel-ball-toe landmark 把 **鞋底/鞋帮/鞋头边/跟/金饰**标注；
2. 仅对鞋前掌可变形区用平滑**绝对位移**满足目标趾外缘和鞋底/鞋帮边界约束，不改固定鞋跟与上方靴筒；
3. 金饰随锚点/表面贴附变动，不直接参与同一径向膨胀；
4. 下游检查鞋面的边界 loop 是否仍保持 open-toe 设计、鞋底是否托住该露出的 B 脚趾，UV/法线/权重是否损坏；
5. 若几何无法满足所需包络且明显失真，正式把这双鞋标为“需要人工适配/更换鞋”是工程上合理结果；不要继续给失败旧算法增加新倍率。

---

## 8. 能否把 Blender 改成“更接近 MMD 的 oracle”？

### 8.1 能改善，但不建议立刻重写完整 Bullet + MMD runtime

**MMD 物理一致性**涉及的不只是碰撞 mask：
- PMX group/deny-list 的**每刚体 pair filter**；
- Mode0 骨骼追踪，Mode1 物理驱动，Mode2 的骨骼/物理组合行为；
- VMD、IK、append/grant、deform order、post-physics bones 的**求值顺序**；
- joint limits、spring、solver step、重力、形状、质量、速度、摩擦、碰撞 margin、坐标尺度；
- SDEF/BDEF 等蒙皮变形和变形后再求值语义。

即使在 Blender 中“自己把 mode 0/1/2 各写一个 handler”，也**不会自动拥有 MMD 的同帧求值图**；现有两遍/point_cache 问题反而可能扩大。

### 8.2 最现实的三级改进路线

**级别 1：不动 solver，只改可验证的观测（推荐立刻做）**

PMX 双向 pair matrix 保持档 A 独立验证；Blender 只记录虚拟 near-field + rigid matrices + skin matrices；通过 §5 固定骨轨迹回放，使得 geometry QA 自身可以**完全可重复**。这一步成本最低、诊断价值最高。

**级别 2：在 Blender 中纠正关键 pair filter（小 POC）**

对 MMD 禁止而 Blender 共享层误允许的**近场** rigid pair，尝试通过 Blender Rigid Body Constraint / disable-collisions 处理（或检查 mmd_tools 现有 non-collision constraints 生成路线是否可安全复用）。先用两球+裙摆短链 fixture 验证：
- 能阻止指定 pair；
- 不附加额外锁轴或弹簧；
- 不破坏已有关节；
- 与 Blender 5.2 collision_collections 叠加后有效；
- 性能可接受，且不能为了近场裁剪而漏掉动作中新相遇的 pair。

**重要：Blender 的 constraint 不能随便造**。错误创建的 fixed/generic 限制可能把刚体强行拴在一起；如果没有验证为“纯禁碰”，不如保持明确近似。禁止所有非目标 pair 的极大约束图可能不可扩展；需要可预测的 pair 筛选和完整遗漏报告。

**级别 3：使用已有 MMD runtime 作为参考求值器（未来）**

可以研究 <https://noname0310.github.io/babylon-mmd/>（PMX/VMD 与 MMD 行为的专门实现）或其他可脚本驱动的 MMD runtime，比较相同 PMX/VMD 下骨矩阵和某几个 frame 的几何表现。它们也可能**并非官方 MMD 的完全等价实现**，但比在 Blender 的 frame_change_post 上重新创造 MMD IK/物理排序更容易得到可重复的外部 oracle。

如果你今后真要实现 mode2：从独立 2-body PMX fixture 验证其动画/物理拆分方式，然后逐层接入，不要“mode2=mode1”时却把测试口径描述成 MMD 兼容。**只实现 mode2 不能修好 Mode0 同帧 feedback / IK/grant 排序 / 每 pair contact filter**。

**停止条件**：本轮直到普通 QA、权重映射、坐标不变性和最小物理重放诊断稳定之前，不启动“自写完整 MMD 物理”的大工程。

---

## 9. 下一批给执行 Agent 的具体任务与验收

### R5-0：纯诊断与数据闸门（第一优先，尽量不改变成品）

1. [ ] 针对 <code>transfer_target_weights</code> 已存在的目标辅助骨，构造 t=1 反例；修复目标辅助骨的“已有组不回填”的分支，分开 target_skin/garment/pseudo 权重预算。
2. [ ] 把 <code>tests/test_subdivide.py</code> 变为真正失败返回非 0 的 CI 脚本；补精确 center UV 和 ShapeKey 插值值断言。
3. [ ] 给 final24 与 final23 记录**每帧前/后 handler 骨矩阵 + evaluated 关键 rigid transforms + 袜/皮肤顶点坐标**，找出第一次分叉帧；不要只打印最终 max_ratio。
4. [ ] 做 §5 的 W_old/W_new × M_anim/M_phys 2×2 **固定骨轨迹重放**，证明差异来自权重/蒙皮还是求解历史。保存原始 pose/bone 数据、网格 hash 和 4 组结果。

**通过条件**：权重重建的 t=1 辅助骨样例精确匹配目标插值；同一固定骨轨迹输入下几何坐标和 sign-flip 结果完全可复现（给定可接受的数值 ε，而非只比到 3 位小数）。

### R5-1：物理代理重复性量化

1. [ ] final22/final23/final24 各自 N=5 完整冷启动；对存在较大跨度的 final24 与对照追加至 N=10；
2. [ ] 报告每次 model/Blender/plugin/VMD/scene hash、stage0–5 首次分叉帧、每帧 hits、min/median/max；不要用 2 次样本产生置信区间；
3. [ ] 将 Blender 物理 proxy 默认标记为 <code>diagnostic_only</code>，不作为跨 final 版本的自动通过判据，直至获得明确 repeatability 与可信 filter 覆盖；
4. [ ] 仍保留数值灾难、静止未模拟等功能性硬失败。

**通过条件**：能明确指出不一致首次出现于 rigid state、骨回写、evaluated skin、还是 sign-flip 分类其中一层；如果不能定位，保留 NOT_REPRODUCIBLE/UNKNOWN，不能给“物理改善/恶化”结论。

### R5-2：几何正确性

1. [ ] R4-P1-07：统一 world/local，先做整体平移+旋转不变性 fixture；结果失败再改算法。  
2. [ ] R4-P1-06：膝带两命中点混合后做 final clearance 检查与 bounded correction；报告 knee min clearance / ray miss / self intersection。  
3. [ ] 检查 collar snap 后 191 顶点的相邻顺序、triangle inversion、4 种踝动作接缝最大值。
4. [ ] 用原始来源鞋设计对照 final24 开口处脚趾；明确可见区后再做最小前掌鞋帮/鞋底 POC。

**通过条件**：在同一 final24 基线下，静置与多姿态均无新增 UV seam/靴口尖片/膝盖穿透；模型空间变换前后 canonical 结果一致；报告具体局部几何距离和截图。

### R5-3：最后再决定物理引擎是否升级

1. [ ] 先使用固定 bones/rigids replay 成功验证可重复性；  
2. [ ] 如确有必要，选 3–10 个**实际可能接触的错误 pair** 测试禁碰 constraint 方案；  
3. [ ] 再比较独立 MMD runtime 的几帧骨矩阵，而不是一次性重构全部 355 刚体/399 关节。

---

## 10. Review 可靠性声明与链接

**真实查看了当前源码**：<code>src/dressing.py:451–606、1140–1373、1376–1707</code>，<code>src/physics_sim.py:105–275、363–520</code>，<code>src/qa.py:326–360、479–694</code>，<code>tests/test_subdivide.py</code>，<code>progress.md:17–100</code>。

**真实查看了当前对话的三张图片**：<code>final24_full_front.png</code>、<code>final24_foot_ankle.png</code>、<code>final24_foot_front.png</code>。基于像素可辨认白色楔形区和前端外露脚趾，但其 exact material/mesh ID、是否属于来源原始鞋的设计和“消除了上一版哪片几何”都需要配套 A/B 与 ID pass 才能证实。

**未获得**：本地 Blender 5.2 实际求值轨迹、两次独立运行的逐帧矩阵、final23/final24 实际 PMX 二进制、原始 A 鞋近景模型。因而本报告明确区分了“代码可构造反例”“用户实测”与“待验证因果假设”。

**本轮最关键的结论**：不应因为普通 QA 改善就忽略动态风险，也不应因为不可重复的 Blender proxy 变差就推翻正确的几何修复。先修已经可由源码确定的辅助骨权重分支，再通过**固定物理骨矩阵回放**把问题切为“模拟器/回写/蒙皮/检测器”四层，随后统一几何空间，最后独立攻鞋。
