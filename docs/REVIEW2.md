# MMD 第二轮 Review：物理 A/B、漆皮层与鞋楦

**仓库**：NiHaiMa123/mmd  
**基线**：main @ 5d8884b50a32b812ce03e22fe75cc7445586e36e  
**比较起点**：d40d181d761a8b53bcac75a4c900bf30f0282299（上一轮 REVIEW.md 提交）  
**审查文件**：src/physics_sim.py、src/qa.py、src/dressing.py、progress.md，以及关联的 src/physics.py、src/motion.py、scripts/blender_runner.py。  
**审查边界**：阅读了仓库当前源码和实测记录，但没有本地 Blender 5.2.1、final9 PMX/VMD，**本轮不声称复跑成功**。按「静态确认」「有构造性反例」「必须实测」区分结论。

## 0. 结论与优先级

上轮的几项实质性 bug 确已修复：Mode 0 刚体开始保存静置偏移；目标权重插值不再把目标骨项重复加两次；qa 的 proxy_in_body 改为世界坐标；Blender 5.x 中 HASHED 误判透明导致遮蔽空操作的问题已定位；脚部前缀误分类已有针对性修正。17,530 面被隐藏、鞋中裸脚不可见，是一项有实际视觉收益的修复。

但仍有 **三个阻断物理正确性验收的 P0 问题**：

1. collision_slots 当前不是 PMX 双向 group/mask 的精确编码，即使组内 mask 相同也有反例；355 个刚体中 105 个混合组 mask 更直接违反了「group 第一条决定整个组」假设。
2. physics_sim.setup 的两遍扫描在 physics→bones handler 安装前执行；Mode 1/2 offset 又在扫描结束后才抓取，可能把**模拟末帧**的刚体位置当静置偏移；不能靠两遍扫描和修改 cache.frame_start 保证重新模拟的真实性。
3. --break-collision 在 setup 已经运行两遍之后才更改碰撞，并借助非精确 collision_slots 再编码；目前 fixed/broken 尚未证明只改变衣服↔身体接触，因而 6383 vs 5278 只能称为「代理 QA 读数变化」，不是“翻译有效/无效”的结论。

**用户可见的下一优先事项不是继续让鞋面径向扩大 4×，而是从目标素体的腿表面生成过膝袜小腿片区，再转移来源袜的材质与纹理。** 手套、鞋面漆皮适用同类技术；真正的鞋帮、鞋底、金饰不能当漆皮层。

---

## 1. 代码 review：物理路径

### [P0-01] collision_slots 的「双向收窄」仍然不是正确的 pair filter

**代码**：src/physics_sim.py:62–102、132–154；src/qa.py:593–610。**静态确认。**

当前：对刚体 A 的 mask 指向的组 B，检查组 B 的**第一个刚体**是否也允许 A 所在组；两者都允许时，把 B 的 group 对应的 Blender layer 加入 A 的 collision_collections。

PMX 关系的真值应由每**一对刚体**计算：

~~~python
def contact_allowed(a, b):
    return bool(a.mask[b.group] and b.mask[a.group])
~~~

但 Blender collision_collections 的 layer bit 是两刚体的共享位，不是「我允许谁的组号」。即便所有同组 mask 相同，也有构造性反例：

~~~text
A: group=6, allowed_mask={0}
B: group=0, allowed_mask={6}
PMX: A、B 双向允许，应该相撞
现有编码: A 的 layer={0}；B 的 layer={6}
两者无共享 layer，可能完全不相撞
~~~

反方向也可能错误：两个本不该相撞的物体因为允许某个第三组而共享 layer，发生误碰撞。

你在 Blender 5.2.1 测得“一侧开启也可能碰撞”，证明不能直接映射群组 mask，但**不证明这次修改就精确**。另外 105/355 条不同于组内第一个的 mask 使函数里 group_masks 的假设在真实数据上明确不成立。

**建议先不改求解器，而是建可测试的双矩阵：**

~~~python
expected[a,b] = a.mask[b.group] and b.mask[a.group]
effective[a,b] = blender_contact_filter(a.layers, b.layers)
# effective 规则须由最小刚体实测确定，不要假设
false_positive = effective and not expected
false_negative = expected and not effective
~~~

报告必须统计 garment↔leg、garment↔pelvis、garment↔garment、body↔body 的 FP/FN，以及错误 pair 的名称/组/mask/layers。新增 3 个单元样例：互允但层不相交；同组不同 mask；第三方 layer 导致多余接触。把「等价性失败」做成 QA blocker，而不是只写 mixed_group_masks=105。

**架构取舍**：Blender 仅有 20 个共享 layer，不能保证无损编码 355 刚体任意 pair 矩阵。不建议继续堆 group 特判；要精确验证就使用有自定义 pair filter 的 Bullet/PMX 运行时，或至少明确 Blender 只是可量化误差的代理。

### [P0-02] 两遍 setup、point cache 与 Mode 1/2 offset 是新的主要风险

**代码**：src/physics_sim.py:163–250，src/qa.py:473–500。**顺序错误可由代码直接确认；缓存刷新表现需运行验证。**

当前过程：

~~~text
setup：建 world / collision layers / kinematic
       ↓
       保存 Mode0 offset
       ↓
       pass 1：逐帧 frame_set + 写 Mode0 keyframe
       ↓
       改 point_cache.frame_start 为 first_frame-1，再改回
       ↓
       pass 2：逐帧 frame_set + 重写 Mode0 keyframe
       ↓
       用 r.matrix_world（此时可能已经动态模拟）记 Mode1/2 offset
       ↓
       安装 physics→bones 的 frame_change_post handler
qa：    [可选] break_collision
       ↓
       再从起点逐帧模拟、测量
~~~

两个实质问题：

- **双 pass 期间 handler 尚未安装**。第二遍不会按预期做 physics→bone→kinematic 的动态闭环，因此“第一遍落后一帧、第二遍修掉”缺少因果保证；即使数值看似更好，也可能只是缓存/求值时机改变。
- Mode 1/2 使用 <code>offset = r.matrix_world.inverted() @ bone_rest[bone]</code>，而 offset **直到双 pass 之后才保存**。如果 r.matrix_world 是动画末帧的刚体结果，所谓静置偏移就已经污染。必须在真正开始任何 Bullet 求解之前记录 rest offset。

附带风险：仅拨动 point_cache.frame_start 不能严格当作「清空并重建所有仿真状态」API；setup 里已执行动态，再切换 ON/OFF 掩码可能保留历史状态。max_follow_error 在覆写 r.matrix_world 前读取，既可能包含上一帧姿态也可能包含缓存状态，不足以证明刚体 offset 没漂移。

**更省事的重构（按阶段，而非继续加 pass）：**

1. PREPARE：静置模型，记录 Mode0/Mode1/Mode2 的 bone_rest_world 和 rigid_rest_world，计算并冻结 offsets；构建期望接触矩阵。
2. KINEMATIC_BAKE：不开活动刚体反馈，仅由 VMD 骨动画生成 Mode0 世界轨迹，保留完整 offset；不要在这里读取任何活动刚体作为“静置”。
3. SIMULATE：**接触 ON/OFF 条件在仿真开始之前确定**；全新场景与冷缓存，安装合法的物理→骨骼写回，然后从起始帧顺序推进一次，记录轨迹和每帧评估状态。
4. MEASURE：读取已冻结的同一时点骨骼/刚体/网格轨迹，生成穿模和可见性报告，不修改动力学条件。

最稳且简单的 A/B 隔离办法：每条件单独启动一次 Blender 后台进程，导入同一个 PMX/VMD，设置不同 contact matrix，再 simulate。若必须同一进程，需显式执行清缓存/重建 world，并验证起始状态和时间轨迹 hash；修改 frame_start 两次不能替代这种验证。Blender 官方提供 ptcache 的 bake/free_bake 接口，但未烘焙内存缓存的正确失效仍应通过场景级测试确认。

建议最小 fixture：一个骨骼、偏移 3 cm 的 Mode0 胶囊、一个 Joint+Mode1 摆锤。检查站立和连续旋转时 Mode0 到骨的局部变换恒定、Mode1 初始化不跳、重复独立运行一致。然后才测试 355 刚体。

### [P0-03] Mode 1/2 写回深度排序合理，但仍非完整 MMD 语义

**代码**：src/physics_sim.py:213–250。**部分正确，高风险待验证。**

按父子深度排序可以减少写子骨后父骨改动导致的错位；但这不解决：
- 同骨局部约束、inherit rotation/translation、IK 与「物理后变形」依赖；
- 直接写 pose_bone.matrix 可能与依赖图求值/handler 顺序形成 1-frame lag 或循环；
- **Mode 2** 不应和 Mode 1 完全一样把刚体的世界位置与旋转都写给骨骼。应保留 Mode2 预期的骨骼位置、按原 MMD 语义只使用物理相关的旋转/部分变换；
- 每帧用于骨骼的刚体矩阵必须与 evaluated depsgraph 同步，记录 raw/evaluated 差异和跳变。

这些问题未处理时，不能用“骨骼在动”证明 MMD 物理完全复刻。

### [P0-04] --break-collision 目前不满足「只改一层」的要求

**代码**：src/qa.py:473–479、557–611。**静态确认。**

break 在 setup 后调用，此时 setup 的两遍扫描已经让仿真运行过；然后清除了对方的 group mask，再用不等价的 collision_slots 重算。即使 MMD mask 层面只删 outfit↔body，**Blender 的 effective pair matrix 也可能连 garment↔garment/body↔body 一并改变**（共享层编码产生串扰）。

正确的反事实定义：

~~~python
ON = full_expected_matrix
OFF = copy(ON)
for a,b in all_pairs:
    if (a in outfit and b in body) or (b in outfit and a in body):
        OFF[a,b] = OFF[b,a] = False
assert ON[within_outfit_pairs] == OFF[within_outfit_pairs]
assert ON[within_body_pairs] == OFF[within_body_pairs]
~~~

使用 **effective matrix** 在启动前检查上述断言；两条件都各自 cold-start，不应使用 setup 完成后的临时 mask 变更。真实 A/B 是「启用/禁用跨部件接触」，不应再叫“原始迁移前 PMX 物理的完全复现”。

### [P1-05] qa 的刚体代理和网格时序需同帧核验

**代码**：src/qa.py:232–288、503–537。世界坐标修复方向正确，但剩余风险待验证。

衣服顶点已乘 gmesh.matrix_world，代理 BVH 仍以原始刚体的 r.matrix_world 构建；带 Bullet 时应对照 r.evaluated_get(depsgraph).matrix_world，确保刚体与 evaluated.to_mesh 的时刻一致。Collider 的可视几何不一定完全等于实际 Bullet sphere/capsule 的形状和 margin，所以 proxy_in_leg 指标只能代表**代理体几何包含关系**，不能命名为精确物理接触或真实皮肤穿透。

另外多个重叠 collider 只按第一个命中的 bone 分类（src/qa.py:281–287），依赖迭代顺序；应单独保留按 body region 的去重值和 per-collider 值。

---

## 2. QA 分区、遮蔽与已有 A/B 数据

### [P1-06] 脚部误分区修了一部分，但实现并非精确匹配

**代码**：src/qa.py:291–313。**直接确认。**

代码仍使用 <code>base.startswith(prefix)</code>。只是把 foot 的 “足” 广义前缀收窄到 足先EX、足親指、つま先 等较明确前缀；这能避免把 足D 和 足回転+ 算进脚，属于有效修复，但不是逐骨 ID 的精确匹配。分区最好由固定 B 的语义 skin-face 区域 + 骨影响、空间位置一次性标注，不要由一个“最大权重骨”的名字代替解剖位置。

**脚区 0** 只能读作：「当前 sign-flip 6 mm、该分区当前采样的命中数为 0」。严重穿透可能大于 6 mm而不计；皮肤被藏后虽然仍有几何却不可见；真正脚面可能被踝骨权重主导。必须另报 foot 候选总数、实际测试数、跳过数、裸脚可见像素。

### [P1-07] 身体遮蔽恢复是实质进展，但无条件并集有误遮风险

**代码**：src/dressing.py:1828–1955、2380–2431。**代码可确认、外观来自 progress 实测。**

排除 HASHED 作“所有材质透明”的通用判据是对的；但 HASHED 也不能反过来证明所有贴图的 alpha 永远为 1。真实 PMX 材质透明度需结合 mmd_material.alpha、节点 alpha、纹理 alpha、alpha-test/cutout 情况验证。

<code>source_coverage</code> 与 <code>mask_by_garment</code> 取 **set union**：一种算法错误遮住的皮肤，不会被另一种算法否决。source 阶段对半透明服装处理不够严格；direct 阶段只看最近三角形，可能被发丝、装饰或另一层材质干扰。建议按 face 输出 source/direct/both 原因与置信度，对 source-only/direct-only 应进行局部可见性复检。

17,530 是**被赋透明材质的面数**，不是 17,530 个真正可见穿模被修复；也不能把「藏掉皮肤后 sign-flip 变少」视为几何改善。QA 应保存不被修改的 B 原始皮肤真值网格来做穿透，另用渲染像素来做可见性。

**额外遗留风险**：src/dressing.py:1655–1744 的 source_coverage 注释说明“inside/封闭壳”，实际判断仍偏向最近面/法线前方；启用 margin>0 的旧面邻接腐蚀循环没有建立真正邻接，未来容易暗中失效。

### [P1-08] 结果状态仍可能误报 OK

**代码**：src/qa.py:652–653、scripts/blender_runner.py:244–254。**直接确认。**

qa.run_qa 只要没有 FAILED 条目即总状态 OK，但当前只制造 OK/WARNING/SKIPPED；外层 runner 即使 QA 自己 skipped/error 也可能 result.ok=True。物理 QA 要求：
- 有效 eval 顶点随动作发生变化；
- 姿态、代理矩阵与 cache 确实推进；
- contact pair 校验有效；
- 数据采样范围与导入 VMD 重叠；
- 关键指标缺失时 UNKNOWN/FAILED，而不是「穿模=0 所以 OK」。

### 当前数字应该如何解读

progress.md 的本轮记录：fixed 6383、broken 5278（旧 sign-flip，固定后多约 21%）；腿部 proxy_in_leg 2035 vs 1972；final9 靴中裸脚不可见，VMD 最差帧 1.42%。

这些**不能**证明「碰撞组翻译使真实 MMD 穿模增加 21%」，理由是物理过滤近似、offset/两遍扫描可能污染初始化、指标漏掉 >6 mm 穿透且不直接等于可见裸皮。实测裙摆代理离腿更远可说明轨迹受影响，但若没有实际 contact pair、最小表面间隙/接触冲量或准确的 PMX 播放器验证，也不能单凭距离证明翻译逻辑正确。

---

## 3. 通用漆皮换装：固定 B 的 target-derived patch

### 3.1 选择这一策略的原因

刻晴手套/鞋面/过膝袜是**来源身体自身的绘制层**，没有独立的服装体积。对固定达妮娅 B，应该把“服装表面几何/权重”从 B 派生，来源 A 只决定 **覆盖区域、UV、材质、纹理、装饰**。这个方案能自然解决 A 手指较细、B 手指约 1.4 倍粗、目标脚多趾骨的问题；套用原 A 的低密度皮肤并做骨骼拉伸反而需要反复修补。

最小可交付的模块接口：

~~~yaml
part_type: body_derived_patch
source_material: 腿
source_component: selected_connected_component
target_body_region: left_lower_leg
proximal_boundary: stocking_top
distal_boundary: under_boot_top
opacity: opaque | cutout | translucent
uv_strategy: anatomical_parameterization | texture_bake
boundary_policy: overlap_or_bridge
clearance_world_units: adjustable
~~~

### 3.2 先做过膝袜小腿段：具体实现

1. **固定标注 B 的腿部面集**：左/右分别记录 face ID/骨影响，覆盖小腿、膝过渡、袜顶区域。过渡面不能只按主导骨精确名称筛掉，否则踝/膝会留破缝；记录边界 loops。
2. **来源袜范围识别**：材质「腿」为候选，结合连通分量、袜顶环高度、靴口位置确定对应上下界。来源没有皮肤面下层不是错误，而是识别 paint layer 的依据。
3. **复制 B 皮肤对应三角面成为 sock patch**，顶点几何、骨骼权重来自 B；轻微法向偏移（参数化）或同位贴合并隐藏原下层。这样 B 动态屈膝与袜片的蒙皮非常接近。
4. **外观迁移**：按 B 的局部小腿 longitudinal u（踝→膝→袜顶）和截面环向 θ 建 UV；寻找来源对应 u/θ 的 UV 或把来源漫反射/alpha 纹理 bake 到 B 新 UV。不能直接用相同顶点索引拷 UV，源、目标拓扑不同。支持镜像/左右侧 UV 岛与袜纹方向。
5. **袜口连接**：在靴筒内轻度几何重叠，或沿袜口桥接一条平滑 rim band；来源袜边缘饰带单独 rigid/cage anchor，不能与目标整条小腿做最近点投影。
6. **可见性**：不透明袜遮住底层 B 皮肤；透明/网眼袜必须保留目标肤色，或者合成成单层材质，防止 alpha 双层排序、z-fighting。用 PMX 重导入截图确认。
7. **QA**：静止、屈膝、蹲下、踮脚、踝旋转；4 视角渲染，记录 body skin visible pixels、袜口 gap、网格自交与纹理伸长。

针对「小腿露目标肤色」，不要先盲目增加径向 max_factor。先通过只看 B、只看袜、显示遮蔽蒙版、叠加三者四张图确定：
- 该段 **没有袜几何** → 直接从 B 补 patch；
- 袜在 B 皮肤内 → 派生 patch 更直接；
- 袜覆盖但 B 未被遮住 → 修局部遮蔽；
- 袜材质本来半透明 → 可能属于正常视觉设计而非穿模。

### 3.3 fit_paint_layer 的具体新坑

**代码**：src/dressing.py:847–965。**静态确认。**

- 截面角用 <code>atan2(radial.y, radial.x)</code>，**不是垂直于骨轴的二维基底**。骨轴倾斜后角度不对，radial.z 被丢掉；应每个 bone 构建正交 tangent1/tangent2，再在该平面求 atan2。
- layer/ref 顶点按主导骨 exact name 抽取，混合权重区域会断层、漏袜口/踝过渡。
- 按目标骨长把 source 位置分桶，B 与 A 的腿长/骨结构不同，桶对应关系并不可靠；某个桶没有目标顶点就变成无意义的 margin/have。
- 92 分位与离散采样密度有关，不代表封闭安全包络；单独按桶调整会使边缘出现台阶。
- max_factor=1.35 只能限幅，**不能证明目标肤色不再露出**。提高它反而会使袜口和装饰变形恶化。

保持默认关闭；真正全自动优先 body-derived patch。

---

## 4. 鞋楦：4× 爆值不应靠再设一个倍率上限解决

**代码**：src/dressing.py:819–844、968–1087。**代码直接确认。**

现在 fit_shoe_to_foot 的样本包含「ひざ」等小腿骨，而且任意一个 polygon 顶点属于 ref_bones 就整面加入；对整只靴鞋做“来源和目标在相同 target ankle→toe 轴分桶”的径向比值。三个直接问题：

1. **源/目标纵向没有先对齐**。A 的 足先EX 踝→趾 8.15 cm，B 的 足先EX 4.71 cm 且有 9 根独立趾骨；同名坐标不构成同一解剖区间。某个 source bin 到了尖端，source radial→0，而 B 还在前足，导致 want/have→4×甚至更大。
2. **径向标量把鞋宽、鞋面高度、鞋底厚度混在一起**。鞋本来需要补长 2 cm 的问题，radial 再扩大也补不了最前方的 toe cap。
3. **鞋底/金饰不该作为软壳拉伸**。即使把 max_factor 限制 1.3，也不会让鞋楦包住 B 脚；4× 只会破坏鞋结构。608 个鞋面顶点和 3924 个目标脚顶点仅说明分辨率不同，不是需要 4× 缩放的证明。

**推荐替代：解剖 landmark 的长宽高分离变形。**

对 A/B 各自定位：heel rear、ankle center、ball/metatarsal、real toe tip、sole plane、forefoot lateral width、instep height。由 heel→toe 的几何方向建立局部纵轴，脚左右方向为横轴，足底法线/鞋底为竖轴。不要用世界 -Y 的假设，且 つま先 骨 61.6° 的差异提示该骨不能直接配对。

先将 A 的 heel→ball→toe 三个纵向分段，以单调光滑函数映射到 B 对应区间，补足**绝对长度差**；再在每一纵向截面分别调 width、height，满足鞋楦内部对 B 的包络约束：

~~~text
target_foot_width(u) + clearance <= shoe_inner_width(u)
target_instep_height(u) + clearance <= shoe_roof_height(u)
shoe_toe_end >= target_real_toe_tip + clearance
shoe_sole_plane stays planar
~~~

有限步长的**绝对位移（mm）**约束比 want/have 相对放大稳；必要时局部补鞋头 cap。金饰通过三角面 barycentric anchor 或局部刚体跟随，鞋底与鞋跟锁定接触形状。**只有最大三角弦误差不达标才细分**，无需追平 3924 顶点数量。

### 推荐小成本顺序

- 保留 final9 已解决的「不透明鞋遮脚」作为外观基线，暂时不破坏它。
- 先把鞋面/鞋帮/鞋底/金饰按材质+连通分量分出可复用 selection manifest（一次预览确认）。
- 修补鞋头纵向长度，再补足前足宽度、足背高度；不要全靴最近点皮肤投影。
- 若来源就是 B 脚表面涂装鞋，直接 target-derived foot patch；但靴帮和鞋底仍是各自的硬/半硬几何，不可照抄脚趾权重。
- 量化「是否包络 B」、鞋口破缝、可见露皮、三角面翻转、金饰边长变化，动作下复测；隐藏裸脚仅满足视觉 fallback，不代表几何容纳成功。

---

## 5. A/B 怎么算“证明翻译有效”？

严格拆成三层，不得用 6383/5278 取代。

### A. 翻译逻辑正确：无须物理模拟

对 355 个刚体生成完整**按 pair 而不是按 group**的 contact matrix。证明新增 garment↔leg/body 接触对是预期的，且 garment↔garment、body↔body 的有效矩阵完全保持原样；检查所有 mask/组号 0–15，joint 端点和禁碰标志。报告 ON/OFF 的矩阵 hash、TP/FP/FN 与错误 pair。

**最小验收：pairwise FP=FN=0（限定宣称精确的对象子集）**。若 Blender 20 layers 无法表示，必须如实声明“代理近似”，不能说 PMX 物理完全等价。

### B. 确实产生有效的碰撞响应：控制实验

选一个可控测试模型：一条裙摆刚体链、一枚 Mode0 大腿 collider、已知 Joint、没有初始互穿。ON 有预期接触/分离响应；OFF 不发生该对碰撞。记录刚体每帧 world transform、最低距离、实际 contact/manifold（如果可获取）、物理误差和是否发生爆炸。没有真实接触接口就只能写 **contact proxy**，不可编造冲量。

### C. 交付外观变好：多动作对比

单独从相同 PMX/VMD/配置启动两个 Blender 进程，**在第一次 frame_set 前**设置 ON/OFF；不得复用 setup 双遍扫描的 cache。固定 FPS、frame range、substeps/iterations、重力、scene unit、形状 margin、random setting、相同采样帧，分别复测抬腿、交叉腿、转身、蹲下、行走。记录：
- 腿/腰/躯干**真实网格交叉三角对**、P95 和最大穿透深度；
- 皮肤露出像素、袜口/鞋口可见缝隙；
- proxy_in_leg、真实 pair contact、裙摆轨迹及运动异常；
- 旧 6 mm sign-flip proxy（仅回归指标、注明 >6 mm 会漏判）。

比对每段**动作的成对结果**，不能把同一动作的数万顶点×80 帧当独立统计样本。最后在原版 MMD 中对输出 PMX 做关键动作目视/截图检验，避免 Blender 近似判定替代目标播放器。

**三个分别标识的结论**：
- <code>translation_logically_valid</code>（预期碰撞关系翻译准确）
- <code>blender_proxy_valid</code>（接触及动态实现经验证）
- <code>visual_improvement</code>（实际可见穿模/破损减少）

当前的 6383 vs 5278 **仅说明一个物理近似条件下旧 sign-flip 指标上升约 21%**，不足以给上述任一命题下肯定结论。裙摆轨迹被推开不一定使其他区的穿模下降，也不自动证明映射错或对。

---

## 6. 其他遗留但值得立即加闸门

- **src/dressing.py:236–268**：Shape Keys 目前仍向所有键加同一 Basis 位移。非刚性体型变化下理想 F(Basis + morph) ≠ F(Basis) + morph；target-derived patch 需要重新构造对应 morph 或显式不适用。
- **src/dressing.py:2110–2121**：_load_config 未 merge physics 配置节，用户指定 physics.enabled=false 可能静默无效；建议补齐。
- **src/physics.py:113–129**：新碰撞组通过递增分配，可能越过 PMX 0–15 的合法上限，需拒绝并报告。
- **src/dressing.py:361–370**：BVH 若只纳入 face 子集，find_nearest 返回的子集索引必须与原 polygons 做映射（这轮 mask_by_garment 使用全服装 BVH 尚不会触发）。
- **src/dressing.py:1828–1858**：HASHED 不能代表半透明，也不能代表完全不透明；真正包含 alpha 的贴图和 cutout 需自检。source/direct union 应输出每个被遮蔽面的原因，尤其要复核透明裙、袜口。
- **src/qa.py:652–653 与 scripts/blender_runner.py:244–254**：status=OK、result.ok=True 仍不能证明 QA 真通过。没有有效帧、物理状态未推进、pair filter 有错误应返回 UNKNOWN/FAILED。
- **src/qa.py:291–313**：分区仍使用 startswith，并非严格名字集合；建议固定 B 的语义面区来测。
- **src/dressing.py:1655–1744**：source_coverage 内的 margin 腐蚀分支未实现真正面邻接；如果未来打开 margin，不要相信输出已腐蚀。
- **src/dressing.py:535–544**：目标权重重复计数的上轮 bug 已修，值得增加「目标/来源权重恒等」「跨骨混合」「仅新骨」三类测试，防后续退化。

---

## 7. 最小下一批任务（给执行 Agent）

**R2-P0 物理证据闭环**：先做 pair matrix 工具，跑 355 刚体+105 个 mixed mask 的 FP/FN；明确区分输入 PMX 关系和 Blender 实际 layer 关系。然后将 setup 拆为 PREPARE（静置 offset）→Kinematic Bake→SIMULATE（单次、冷缓存）→MEASURE；ON/OFF 必须在启动前分开设置。加入 Mode0/Mode1 简单摆锤 fixture。**未通过这关，不再用总 sign-flip 判断翻译成功。**

**R2-P1 可见问题闭环**：先实现「过膝袜小腿 target-derived patch」，从固定 B 复制皮肤片、继承权重，再按 A 的袜片转移 UV/material；只用一次分区预览人工确认，保存选择。对不透明/透明材质分开做 underlayer。验收是小腿不露皮、袜口无缝、屈膝不破，而不是把径向系数调大。

**R2-P2 鞋楦**：保留 final9 遮蔽作为基线；按 heel/ball/toe 长轴校正鞋头长度，再按前足宽、足背高度做绝对包络修正，金饰单独锚定。不启用 4× 径向扩张，不盲目细分全靴；用 4 张细节图、5 个姿态、网格相交/UV 变形自检验收。

**R2-P3 QA**：分别统计可见性、几何相交、物理代理、数据完整性；以独立的未删/未隐藏 B 真值网格评估几何，不让遮蔽面数改变几何指标的分母。关键未知失败必须影响 exit status。

**范围控制**：不要为了解决一个小腿袜的露皮问题重写整个换装管线；不要默默扩大鞋至 4×、删掉目标皮肤后就宣称几何修复，也不要因为 Blender 物理近似错误而无目标地重建全部裙摆关节。

## 8. 参考与验证边界

- 仓库 5d8884b 的 src/physics_sim.py、src/qa.py、src/dressing.py、progress.md。
- progress.md 中 17,530 面遮蔽、final9、6383 vs 5278、105/355 混合 mask 是**项目自身的实验记录**，不是本轮独立实测。
- Blender 官方参考：<https://docs.blender.org/manual/en/5.0/physics/rigid_body/world.html>（Rigid Body World / point cache），<https://docs.blender.org/manual/en/dev/physics/rigid_body/properties/collisions.html>（Collision Collections），<https://docs.blender.org/api/current/bpy.ops.ptcache.html>（Cache 操作）。具体 Blender 5.2.1 行为优先按你的最小 fixture 脚本验证。
- 上轮关于 <code>new_from_object(evaluated_obj)</code> 的通用建议，已被你的 Blender 5.2.1 实测（返回空网格）否定；这里不再次要求替换已验证的 <code>evaluated.to_mesh() + copy()</code> 路径。
