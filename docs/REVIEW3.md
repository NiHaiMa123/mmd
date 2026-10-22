# REVIEW3 — MMD 换装工具链第三轮代码审查

> 仓库：NiHaiMa123/mmd  
> 审查基线：main @ **8fed10ce0b428d16f34fe4a50d8238b6ff851eda**  
> 对比起点：上一轮 REVIEW2 提交 50dfe5f6e51ba35d36da1cd9d4e0d22017805e9d  
> 重点：src/physics_sim.py、src/qa.py、src/dressing.py，关联 src/physics.py、scripts/blender_runner.py、progress.md  
> 审查方法：逐项阅读当前源码与更新记录；检索核对当前上游 mmd_tools 的 PMX import/export、刚体属性和构建代码，以及 Blender 5.2 官方 Data Transfer/BMesh 说明。**没有在本地 Blender 5.2.1 重新运行 final17/final18**。下文标明代码可证结论和需要运行验证的风险。

## 一、最重要的结论：先纠正 collision mask 的布尔语义

**本轮发现一个比 8910 个假接触更根本的 P0：代码将 mmd_tools 的 collision_group_mask=True 当成“允许接触”；当前上游源码显示，True 实际表示“禁止与该组碰撞”。**

这不只是代理模拟精度问题。它同时影响 src/physics_sim.py 的碰撞分层、contact_matrix_report、setup 的 break_outfit_body，**以及 src/physics.py 迁移后实际导出的 PMX 碰撞关系**。因此，现有的「期望 16090、假接触 8910、漏接触 0、翻译后增加 4242 个接触对、−3.6%」不能作为已经证明逻辑正确的结论。

### 直接源码证据

上游 MMD-Blender/blender_mmd_tools 的当前 main 中：

- mmd_tools/properties/rigid_body.py 的 collision_group_mask 属性说明是 **“The groups the object can not collide with”**。
- mmd_tools/core/pmx/importer.py 读取 PMX 位掩码时写入 Blender 属性：
  ~~~python
  collision_group_mask = [
      rigid.collision_group_mask & (1 << i) == 0 for i in range(16)
  ]
  ~~~
- mmd_tools/core/pmx/exporter.py 导出时：
  ~~~python
  mask = 0
  for i, v in enumerate(mmd_rigid.collision_group_mask):
      if not v:
          mask += 1 << i
  p_rigid.collision_group_mask = mask
  ~~~
- mmd_tools/core/model.py 的 buildRigids() 直接使用变量名 ignore：
  ~~~python
  for n, ignore in enumerate(obj_a.mmd_rigid.collision_group_mask):
      if not ignore:
          continue
      # 对该组创建 non-collision 约束
  ~~~

因此必须区分**文件原始 bit**与**Blender 插件属性**：在当前这一插件的 import/export 约定里，Blender 的 mmd_rigid.collision_group_mask[g] 为 True → **不碰撞该组**；False → 不禁止。不要仅凭字段名“mask”猜它是 allowed set。

上游阅读位置：
- https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/properties/rigid_body.py
- https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/core/pmx/importer.py
- https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/core/pmx/exporter.py
- https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/core/model.py

**请在你安装的 bl_ext.blender_org.mmd_tools 版本上，用两刚体最小 PMX 反例核对，不要直接把网络 main 当作本机环境的版本锁定。** 但在这项核验完成前，必须将现有碰撞逻辑 A/B 标记为 UNKNOWN/INVALID。

以该属性语义为前提，基础公式应是：

~~~python
# mmd_rigid.collision_group_mask: True 表示排除/不碰撞
def expected_contact(a, b):
    a_ignores_b = bool(a.mmd_rigid.collision_group_mask[b.mmd_rigid.collision_group_number])
    b_ignores_a = bool(b.mmd_rigid.collision_group_mask[a.mmd_rigid.collision_group_number])
    return not (a_ignores_b or b_ignores_a)
~~~

还需进一步加入连接关节禁碰、已导入的其他 non-collision 约束、有效实体类型等，使之成为“可碰撞 pair”而非实际发生了接触的统计。

**同一根因还出现在现有文件：**

| 位置 | 当前逻辑 | 如果 True=禁止，会怎样 |
| --- | --- | --- |
| physics_sim.py:95–101 | mask[other] 且 other_mask[g] 为 True 才开 layer | 把相互禁止的组当成允许 |
| physics_sim.py:136–145 | 两边 mask 都 True = expected contact | “期望 16090”统计方向反了 |
| physics_sim.py:175–188 | break 时把对方组 mask 设 False | 实际是在**取消禁碰**，不是拆除服装↔身体接触 |
| physics.py:184–193 | 仅对 src_mask 为 True 的组做“允许组”迁移 | 迁移的是禁碰信息却按允许关系解释 |
| physics.py:254–285 | 为了“打开服装与身体接触”把相关 bit 设 True | 可能在导出的 PMX 中**禁止接触**，效果和意图相反 |

**这是优先级 P0-CRITICAL，必须先核验并修复，优先于 point cache 和换装几何优化。**

---

## 二、P0：contact_matrix_report 是否正确？8910 假接触该怎么收口？

### [P0-02] contact_matrix_report 的“actual”并不是 Blender 真正接触

代码：src/physics_sim.py:105–156。当前使用两刚体 collision_collections 的位交集 shared = bool(li & lj)。

这最多是 **layer filter potential pair**，不是 contact manifold，也未覆盖：
- 刚体实际是否 ACTIVE/kinematic，是否在世界中启用；
- 是否由 generic joint / non-collision constraint 禁止碰撞；
- 刚体是否几何相交或进入 broadphase；
- 形状 margin、求解器、是否动态发生实际接触；
- Blender 对当前对象/约束的具体过滤行为。

因此报告建议改字段：expected_pmx_filter_pairs、effective_blender_layer_pairs、false_positive_layer_pairs、false_negative_layer_pairs、observed_contact_pairs（如果有真实 contact API，不能获取就留 UNKNOWN）。

你在 work/test_collision_filter.py 所谓“单侧开启就撞”不能推导出一条非对称碰撞法则：**layer 交集本质上是对称关系**。例如 A={1}、B={0,1} 会碰撞，是因为交集有 1，并不意味着 Blender 只看 A 的 mask。两刚体实际小球测试还需固定碰撞层与其它场景变量，才能验证此假设。

另外 report 的 by_group 错误统计没有区分 false positive 与 false negative，group pair 键未标准化（同一无序组对可能分别计入 (6,0) 与 (0,6)），也没有输出具体实例 pair/name/关节/距离。即使修正掩码语义仍应完善。

### [P0-03] 8910 不代表不可避免的“真实物理假接触”

当前 8910 是 62,835 个**所有刚体组合**中的 layer-filter 差异（更严重的是：基准 expected 语义可能反了）。这不是 8910 次碰撞，也不能证明 8910 个潜在 pair 都会在同一动作中相遇。

应报告四个口径：

1. 全局过滤矩阵 FP/FN；
2. 在初始空间上近邻的 pair FP/FN（相交或以一定 margin 扩展 AABB）；
3. 目标动作 340–420 帧的 **swept AABB 潜在相遇 pair** FP/FN；
4. 真正发生接触的 pair 数（需要引擎 API 或经过验证的接触近似）。

对当前重点裙摆↔腿，只有这一相关子集的 FP/FN 才能判定代理是否足以支持“腿部接触 QA”。例如全局 8910 中多数发生在相隔很远的头发/装饰/另一侧肢体，实质影响可能很小；相反少量错误 pair 如果位于臀/膝接触区，动态影响可能极大。**不能按错误 pair 数本身断言代理一定失败或者“只有轻微误差”。**

### 可操作的三档收口，不需要放弃 Blender

**档 A：严格 PMX 逻辑验证**（必做，低成本）：正确解释 mmd_rigid mask，并在 PMX raw 层进行 roundtrip；直接以 355×355 expected pair matrix 证明迁移增加/移除的关系，只输出“逻辑映射是否正确”。这是**无需 Blender 动力学**的确定性测试。

**档 B：保留 Blender 作为近似动态回归**（建议）：继续渲染带物理动作、检查裙摆是否乱飞/震动/局部穿模，但明示“不是 PMX 物理一致性证明”。加 near-field 和 swept-pair 错误报告，选少量相关 collision pair 做接触定向测试。

**档 C：只针对关键近场 FP 做 Blender 定点修补**（可选）：参考 mmd_tools 的 non-collision constraint 路线，在**实际有可能相遇**的错误 pair 上设置 disable_collisions 的约束；注意 Generic Constraint 必须保证其关节限制/弹簧不会额外约束物体，且在 Blender 5.2 上通过两球/裙摆小链 fixture 验证。不要盲目对全局 8910 pair 全部建约束，这可能显著降低性能或引入新刚体约束冲突。

若档 C 仍有明显模拟误差，就把「MMD 引擎／Bullet 对照小测试」独立做，不需要抛弃 Blender 的换装 QA/渲染能力。**推荐分工：PMX filter 的 truth → 矩阵测试；Blender → 粗物理和画面 QA；真实 MMD 播放器 → 最终表现。**

20 个 layer 不能表示任意 355 刚体接触图，但**不代表对当前模型关键子图一定做不到**；优先验证实际子图，而非一上来改全部物理。

---

## 三、P0：setup 两遍扫描、handler 与 cache 的新风险

### [P0-04] 偏移提早抓取是正确改动；两遍扫描仍不可视为可靠 cache reset

代码：src/physics_sim.py:159–352，重点 240–335。

正确的改变：
- Mode0 静置偏移在执行时序前取得；
- Mode1/2 的 rigid→bone rest offset 改在动态前获取；
- handler 现在提前安装；
- 冷启动 ON/OFF 在 setup 前确定（消除了跨**进程**热缓存比较问题）。

**但有以下新问题：**

1. **handler 在两遍“烘焙”期间已经写回 pose bones**：frame_change_post 在 scene.frame_set 内运行；接着 setup 又用这些已物理写回的 arm.pose.bones[bone].matrix 算 Mode0 并插关键帧。第二遍是在一条被前一遍生成的关键帧/刚体状态反馈影响的轨迹上再生成。它不是“第一遍错一帧，第二遍必然正确”的算法证明。
2. 第一次 pass 每帧先 scene.frame_set(f) 运行物理，再**写入**当帧 Mode0 关键帧。对于动态求解，刚体 f 帧的边界条件已在积分之后改变；当前姿态可能属于上一帧。第二遍只有在 Bullet 真正完全重置并且新的当帧关键帧在求解前生效时才可能修好。
3. 改 point_cache.frame_start → first_frame-1 → first_frame 不是官方定义的“强制清除所有缓存”语义；Blender 是否重新跑要做状态/轨迹对照，不是凭最终 max_follow_error 就可判定。
4. 代码对 follow 中每个对象执行 animation_data_clear（两遍），可能清掉其它继承/约束动画；直接设置 r.matrix_world 与插入 location、rotation_quaternion、scale 关键帧，若父对象变换非单位需核对 local/world 转换是否仍保留预期骨骼偏移。
5. max_follow_error：src/physics_sim.py:325–331 在**更新当前帧 Mode0 刚体矩阵之前**测 r.matrix_world 相对 bone 的差，既包含求值时序又可能是上一帧状态；并且只测平移，忽略旋转漂移和 scale。这个数不是“当前帧已经锁定正确”的证据。
6. Mode1/2 的写回直接 pose_bone.matrix=...，虽然按父子深度排序，但依赖图/IK/后物理骨依赖可能反馈到同一帧物理；Mode2（物理旋转、位置由骨骼驱动）仍没独立实现。应报告 mode2_count，并按数量决定 Blender 代理有效范围。

**最简单的收口**：将 setup 拆成下面的职责；不是继续找更灵的“清缓存”技巧。

~~~text
REST_SNAPSHOT
  在导入后的确定静置时点冻结 bone_rest 和 rigid_rest offset。

BUILD_KINEMATIC_KEYS
  在“未推进刚体物理/无 physics→bones handler”的状态下，
  只从 VMD/普通骨动画生成 Mode0 跟骨 keyframes。
  如果 Mode0 依赖动态驱动骨，标为二阶段依赖，不能用静态预烘焙代替。

INITIALIZE_SIMULATION
  先设置正确的 ON/OFF contact filter 与 point cache 范围；
  安装单一 frame handler；验证第一帧所有刚体状态；
  正常逐帧推进一次。

MEASURE
  记录每帧 Mode0 骨-刚体 offset（全矩阵或平移+四元数）、
  Mode1/2 写回骨跳变、rigid 轨迹、受影响关键刚体。
~~~

当 Mode0 跟随被物理驱动的骨骼时，**静态预烘焙可能本身不足**。更可靠的是先制作一个最小 parent Mode1→child Mode0 的 fixture，确定 handler/bone/rigid 时序（每帧值对应 f 还是 f-1），再实现显式 per-frame kinematic update。对真实裙摆先限制到这条受控路径，未验证不能强制声称“一遍/两遍都正确”。

ON/OFF 两个**独立进程**的隔离应保留，但 setup 内的双遍预跑仍会破坏“从完全干净的初始状态执行一次求解”的可解释性。优先采用“一次求解 + 预计算/明确反馈”，不要再以调 cache.frame_start 当作算法核心。

### [P0-05] “新的 handler 安装”还需要防止重复执行和旧引用残留

代码按 handler.__name__ 删除旧 handler，当前 session 中可以减少重复；但对象可能在不同场景/view layer、文件载入和 depsgraph 更新中重复触发求值。建议增加 debug 记录：调用 frame、depsgraph scene、更新前后 rigid pose hash、pose bone hash，以及帧单调检查。不能在 handler 内再次调用会导致重复求值的操作而无 instrumentation。

本轮无需为此建复杂回调框架；先用一条单关节链证明：Mode1 旋转一帧后，child Mode0 在**相同 f** 的世界矩阵和骨骼 offset 对得上；否则报告 1-frame lag，并在 QA 拦截。

---

## 四、P0：A/B 三层结论要修订

progress.md:207–237 的现有结果：

| 统计（项目记录） | ON | OFF | 差异 |
| --- | ---: | ---: | ---: |
| 6 帧 sign-flip 点合计 | 3955 | 4103 | −148，约 −3.6% |
| 最差帧 | 0.969% | 1.032% | 下降 |
| 代码当前期望 pair | 16090 | 11848 | +4242 |
| 代码当前 layer FP | 8910 | 1936 | +6974 |
| 代码当前 layer FN | 0 | 0 | 0 |

**重要：如 P0-CRITICAL 所述，mask 极性颠倒将使当前 expected、ON/OFF 的物理含义乃至导出的 PMX 语义失效。修前不得把这些数升级为验收证据。**

并且即使纠正极性，这段推断也不成立：

> “代理多出来的假接触只会制造额外穿模，因此真实 MMD 的改善至少 3.6%。”

**错误原因：物理是非线性耦合系统，额外的误碰撞既可能减少，也可能增加穿模。** 假接触可能撑开裙摆防穿腿，也可能把裙摆挤进腰/另一个腿，无法给“真实效果”建立单调下界或上界。6 帧 sign-flip 差额甚至可能完全来自其它区域或运动轨迹扰动。必须删除“下界”标签。

修复以后，三层判据应是：

1. **logical valid**：原始 PMX 的 expected pair matrix 与目标迁移前后按计划差异相符，非目标 pair 保持不变（如有故意新开跨 body 关系，标识具体 pair）。
2. **proxy valid**：关键近场 pair 的 Blender effective filter 与 expected 一致，并通过有/无碰撞的最小物理响应测试；用 layer-report 全局误差标出未知区域。
3. **visual improvement**：原版 MMD 或经过模型/动作验证的物理播放器中，真实可见穿模和破损在代表性动作中改善。Blender 近似的 6 帧 6-mm sign-flip 只用作趋势线索，不可替代。

两个冷启动进程是正确且应继续保留的实验设计，但**相同初始条件≠模拟器实现了正确的 PMX 碰撞语义**。

---

## 五、P0/P1：袜子新增 subdivide_triangles 的具体实现问题

### [P0-06] 没有真正切开「原始边」，局部细分与未选三角面交界会产生 T-junction

代码：src/dressing.py:1090–1172。

代码使用 bm.verts.new() 产生 ab/bc/ca 顶点，以新面替换被选三角形；**但没有对边的原始 BMEdge 做 split**，邻接的、未被选中的三角形仍使用原始边 a—b。结果是一个面侧使用 a—ab—b，另一侧只有 a—b，二者在 BMesh 拓扑上不连通，形成 T-junction、法线/蒙皮断层。rest pose 可能共线看不出缝，但后续骨骼混合权重/形态键不同就能裂开。两级细分将这个问题扩大。

**修法**：最小改法要对共享边做一致细分/连接过渡三角形，或只对已沿边界分离的**整片连通袜子组件**做完整 1→4 细分；局部边界不要在同一个网格上留下 T-junction。若部件本来就独立断开，必须明确其边界及 overlapped seam 的策略。

### [P0-07] shape key 与非 UVMap 图层未完整插值，可能破坏 PMX Morph

代码：src/dressing.py:1108–1166。中点只手工插值：
- vertex.co；
- bmesh deform 顶点组；
- 一张 UV（uv_name 或 active）。

没有遍历 bm.verts.layers.shape 来插值所有 Shape Key 顶点，也没有处理所有 UV layers、其他 loop/corner attributes、顶点色、额外 UV、MMD 扩展顶点属性。**Blender 的 BMVert.new 不会自动把所有语义层的正确插值补齐**。含 Morph 的漆皮片区会在导出后表情/服装形态键上出错；若切面共享边，还会出现形变裂缝。

应：
1. 新建中点时对每个 shape layer 做 v_mid[shape] = 0.5*(v1[shape]+v2[shape])；
2. 新子面按**每个 loop 的每个 UV layer**分别插值，特别注意 UV seam 必须使用原面一侧的 loop UV，而不是共享顶点 UV；
3. 逐项核对材质索引、smooth flag、custom normals、颜色层、MMD 附加层，并走 PMX export→reimport 的 morph/权重/UV 测试；
4. 如果暂时不支持形态键或扩展层，**检测到则拒绝细分并给明确 WARN/FAIL**，不能静默抹掉。

另有一个直接 Python bug：若模型没有任何 UV layer，ua/ub/uc 不会赋值，而下方仍构建包含它们的 uvs 元组，可能触发 UnboundLocalError。即使 MMD 常有 UV，也需要处理无 UV 的最小 fixture。

### [P1-08] 三角面、材质和体积的保真还缺显式断言

当前代码直接对每个 f 执行 a,b,c = f.verts；假定选中面全部为三角形。这对初始 PMX 可能常见，但经过 Blender 编辑/导入后不应默默假定所有面都已三角化。处理前 assert len(f.verts)==3 或显式三角化。

新面复制 material_index 和 smooth 是有益修复，但**不能据此认定所有材质相关属性/UV/Morph 已完整保留**。建议输出：细分前后被选区域的面数（应 4×）、边界 loop 数、非流形/T-junction 数、权重和、UV/Morph 差异、测试姿态的裂缝、PMX roundtrip 结果。特别检验是否改变裙摆以外区域的拓扑。

---

## 六、P0/P1：project_layer_on_limb 的新隐患

代码：src/dressing.py:1175–1352。

### [P0-09] **明确的坐标空间混用**

当前目标腿 BVH 以 tgt_body.data.vertices[i].co（**target mesh local**）构建：
~~~python
verts = [tme.vertices[i].co.copy() ...]
bvh = BVHTree.FromPolygons(verts, ...)
~~~

而轴 origin/dir 由 tgt_arm.matrix_world @ bone.head_local/tail_local 得到（**world**）：
~~~python
head = tgt_arm.matrix_world @ b.head_local
tail = tgt_arm.matrix_world @ b.tail_local
~~~

然后 v.co（**garment mesh local**）与 world 轴混用：
~~~python
rel = v.co - axis_origin
hit = bvh.ray_cast(origin, direction, max_dist)
positions[i] = v.co + (target - v.co) * w
~~~

**这是真实的空间错误**。即使当前 PMX 因为对象 matrix_world 巧合接近单位矩阵而看起来能用，只要整体变换、Blender 物体 parent matrix、导入 scale 或姿态稍有不同就错。建议全程在 **world** 求 BVH、骨轴、ray、目标位移，再通过 garment.matrix_world.inverted() 写回 local；若含非均匀 scale，法线用 inverse-transpose 变换。增加「把整个人平移 1 m、绕 Z 旋转 90°，修复结果相同」单测。

### [P1-10] ray origin 不保证在目标皮肤内部；第一交点不保证是正确表面

射线从骨轴上的骨中心往径向打。若骨轴点位于皮肤外、目标 mesh 存在孔洞、骨和曲面不是理想圆柱，第一 hit 可能落在身体另一面、错过小腿，甚至打到旁边组件。ray_cast 距离的 max_dist=0.12（当前空间下约 12 cm）也需要明确单位。

建议：
- 只选右/左、腿段的对应连通组件，并按沿骨长度限定候选三角形；
- 检查 hit 法线 n 与射线 direction 的夹角、沿骨投影偏差及与原袜顶点的距离；
- 如果从内部发射，找到第一个法线朝外的候选；无法确认时 fallback 到原 mesh 并返回“未命中”，不能悄悄留下裸皮；
- 对膝过渡以连续曲线/两骨 frame 做 blend，避免按单一 z 门槛硬切轴。

### [P1-11] axis_bones 参数没有真正生效

函数签名 axis_bones=("下半身", "足先EX")，但实际始终 bone_axis("足") 和 bone_axis("ひざ")，因此用户 config.project_layers[*].axis 传入什么都不会影响实际计算。结合最新 progress.md 的“用控制骨而不是 ひざD”修复，**需要同步更新函数签名/配置语义**：要么删掉 axis 参数并明确固定 足/ひざ，要么正确解析对应目标部位的控制骨配置，并在 report 输出最终选用的轴名称。避免执行 Agent 以为调参生效。

### [P1-12] 分段界面和边缘过渡可能导致“脚踝白边/膝盖堆叠”

src/dressing.py:1293–1348 在 knee_z 切换轴，且采用 top_cut=z_hi-0.25*(z_hi-z_lo) 选择「上端边界」，以拓扑 rings 控制 fade。隐患：
- 膝处虽然袜几何连续，投影方向会突然从股骨轴变成胫骨轴，刚好对应进度记录中的轻微堆叠；
- 顶部 25% 的 boundary 被锁住，而中间区域可能大位移；袜口装饰连接点不一定等于 material border；
- 下边界全面释放若与靴筒不相交，会留下局部裸脚/裸踝。
- 路径中遍历「每个 depth 顶点 × 全部 garment.edges」，时间复杂度不必要地高。一次构建邻接表然后 BFS 更简单。

**低侵入的下一步**：沿腿从髋→膝→踝建立连续 centerline（不必真正做样条求解器，只需在膝附近做 2–4 圈 smooth blend），让径向方向在膝区连续。下边界按“应隐藏于靴筒的环”标注 overlap 目标，不是一律放开。报告 missed_ray_count、max_displacement、knee_jump、ankle_visible_skin_area，围绕这些具体指标优化。

### [P1-13] 贴合后仍继承 A 原始骨骼权重，动态未必真正贴 B

project_layer_on_limb 改的是 rest mesh vertex positions；顶点组仍是来源映射后的权重。静态看袜面套住 B，不代表在屈膝/踝转动时它仍与 B 同步。过膝袜对 B 小腿/膝/踝区应允许局部替换成目标 skin weights（按几何面插值，保留袜口柔性层权重），或生成独立 target-derived patch。任何替换都需保留来源服装专用骨及特殊绑定的角色语义，不允许全衣一键 target_weights。

---

## 七、UV 迁移：如何不糊？为什么可以继续保留 A 漆皮几何？

### 7.1 首先澄清：新拓扑不会自动使纹理模糊

纹理是否模糊主要取决于：
- 是否**重采样/烘焙**了源贴图；
- 目标 UV 岛占据多少纹理像素（texel density）；
- 解剖对应是否正确（图案扭曲 ≠ 分辨率变糊）；
- UV seams、mipmap、采样 filtering。

**如果只迁移 UV 坐标，不重新生成纹理图，直接在新模型继续读取原图，那么没有第一次颜色烘焙的分辨率损失。** 但如果源/目标面对应错位、源 UV 本身布局扭曲，则清晰图案仍会拉伸/断开。

### 7.2 推荐路线：A 几何保留 vs B 表面派生，不要强迫二选一

| 类型 | 更省事的做法 | 原因 |
| --- | --- | --- |
| 不透明纯色 / 简单纹理过膝袜 | **优先保留 A 漆皮几何**，用分段圆柱/射线形变，再做目标权重局部转移 | 直接保留全部源 UV、材质、法线细节；当前可见效果已大致可用 |
| 需要精确纹样/花边、袜口/膝盖动态剧烈 | 考虑 B 派生 patch + 源 UV barycentric 迁移 | 布料与 B 关节权重同步，纹样需要专门参数化 |
| 贴肤手套（五指、关节弯曲频繁） | B 派生手指皮肤 patch + 来源 UV/材质 | 目标手指比 A 粗，指缝/每指权重差异大 |
| 贴肤鞋面/脚趾涂层 | B 派生脚 patch 或 A 鞋面局部 cage warp；鞋底和饰品保留 A 硬几何 | 不可用一条脚骨直接替代 9 个脚趾骨 |
| 有实体体积的鞋头/靴筒/金饰 | 保留 A 几何和原 UV，解剖 landmark/cage 变形 | 来源装饰拓扑、厚度比 B 皮肤更重要 |

针对你的 current final18，小腿袜已能包住腿、只剩脚踝小白边与膝轻微堆叠，**不建议立即推倒重做成 B-derived patch**。先修空间、边界和膝过渡，做局部目标权重 transfer，并用动作验证；只对确实无法由 A 几何稳定适配的区域换用 B patch。

### 7.3 不重新烘焙的源 UV 迁移算法（高质量首选）

当需要 B-derived patch 时，建议用**解剖语义参数空间 u,θ**找 A/B 对应，而不是直接在“两个大小/朝向不同的 3D 形体”上找最近顶点：

1. 对 A 袜面和 B 腿 patch，构造沿踝→膝→袜口的纵向参数 u∈[0,1]，横向在骨局部正交截面上计算环向 θ∈[-π,π)；在膝关节用连续 centerline，左右脚各自建立正交基，不用 world XY 的 atan2。
2. 将来源 A 的每个**三角面角点（loop/corner）**的参数 (u,θ) 和**原 UV**存起来；UV 是 per-loop，不是 per-vertex，UV 岛缝处两侧 loop 可以有不同坐标。
3. 对 B patch 的每个**目标 loop**计算 (u,θ)，在 A 同一部位/同一 UV 岛里查找包含该参数点的三角形，计算 barycentric (w0,w1,w2)；目标 UV = w0*UV0 + w1*UV1 + w2*UV2。
4. 环向 θ 的 seam 要展开（θ+2π 周期匹配），但 UV 不能跨源 UV 岛缝直接插；在条纹/Logo 处，允许从源图案 island 锁定几个 landmark。
5. 对 (u,θ) 范围外或找不到对应源三角形的 loop，产生 missing_map，不准自动映射到另一侧腿/袜内层；修复比例超过阈值应生成预览供人工确认。
6. 目标 B patch 绑定继承 B 的骨权重；原图、原 shader/material 原样复用。**只改 UV，不必生成新纹理**。
7. 用棋盘格和实际条纹图检查 UV 雅可比畸变：例如每个目标面 source/target UV 面积密度比、映射折叠/跨岛率。不要单靠像素相似度认定 UV “不糊”。

简单伪代码：

~~~python
for dst_face in B_patch.faces:
    for dst_loop in dst_face.loops:
        u, theta = anatomical_uv_param(dst_loop.co, B_centerline)
        src_tri = source_param_bvh.find_triangle(
            u=u, theta=theta,
            side=dst_side, uv_island=expected_island
        )
        if src_tri is None:
            mark_unmapped(dst_loop)
            continue
        bary = barycentric_2d((u,theta), src_tri.param_coords)
        dst_loop.uv = sum(bary[k] * src_tri.loop_uv[k] for k in range(3))
~~~

注意这里的 source_param_bvh 是**二维参数空间三角查询**，不是 world-space BVH。

### 7.4 更省事的 Blender 原生尝试：Data Transfer

Blender 5.2 LTS 的 Data Transfer modifier 已提供：
- Face Corner Data（UV Maps）
- Nearest Face Interpolated
- Projected Face Interpolated

官方：https://docs.blender.org/manual/en/5.2/modeling/modifiers/modify/data_transfer.html

**低成本试验**：先把来源 A 袜/手套在静置姿态下用语义轴形变到 B 表面附近（保留原 UV），再用 Data Transfer 把 A 的 UV layers 传给**已从 B 复制的 patch**。因为这时 A/B 几何相近，Nearest Face Interpolated / Projected Face Interpolated 的误映射会大幅减少；且无需烘焙、原贴图仍可沿用。局部搜索必须限定到同侧、同部件，不能跨另一只手/腿；跳面时检查 seam 和法线角。

失败时才升级到第 7.3 节的解剖二维映射，最后才考虑颜色烘焙。

### 7.5 最后备选：高分辨率 Selected-to-Active Bake

如果 A 的 UV 极度不规则（贴花、复杂袜纹、多个岛），UV 直接映射失败，可用 Cycles **Selected to Active** 烘焙到 B patch 新 UV。4K/8K 是输出纹理尺寸选项，不是无损保证；按纹样真实 texel density 决定，使用足够的 margin，保留 alpha/transparency；只 bake 所需 color/alpha/normal 等通道。Blender 官方：https://docs.blender.org/manual/en/latest/render/cycles/baking.html

相比 UV direct transfer，bake 增加维护成本和纹理 resampling 风险，所以**只对失败材质使用**，不是每件袜子都强制烘焙。

---

## 八、QA 的新代码：认可的修复与还剩的坑

### [P1-14] 分区真改为精确集合，但脚区 0 仍不能宣称“脚绝不穿模”

src/qa.py:295–323 已使用 base in names，修复了 startswith 的混淆；全角数字骨名被正确纳入。这条相较上轮确实完成。仍建议报告各部位候选皮肤点总数/参与 sign-flip 判定的点数/静置符号未定义的点数；6 mm 阈值外、被遮蔽的脚区仍可能在视觉或几何意义上出问题。

### [P1-15] UNKNOWN 的状态/退出码仍有语义漏洞

src/qa.py:621–653 引入 OK/WARNING/UNKNOWN/FAILED 有改进；但 scripts/blender_runner.py:254–258 以 status != FAILED 设置 result.ok，导致 **UNKNOWN 仍退出码 0**。如果“要求动作 QA 必须完成”是一道验收关，应让 UNKNOWN 非零退出或单设 result.executed / result.passed。不要让“报告是 UNKNOWN，但流水线返回成功”再产生误验收。

### [P1-16] garment_motion 不是物理推进的充分性证明

src/qa.py:517–591：只对采样首帧与末帧的最多约 400 个网格点取最大差。VMD 导致模型运动也会使其大于阈值，**不能证明 Bullet 求解或 physics→bone 路径真的生效**；周期动作首末相同又可能误报无运动。建议分别测：
- 6 帧中相邻帧的 mesh/world pose 位移；
- 至少 1 个 Mode 1/2 刚体相对不带物理的 kinematic baseline 发生有效差异；
- Mode 0 collider 跟骨误差，以及 Mode1/2 是否出现不合理大位移/旋转；
- 首末 pose hash 和模拟 cache 起止状态。
无 VMD 或静态动作也不能强制用“mesh 不动”当 FAILED，需区分 intentionally_static 与 simulation_failed。

### [P1-17] 裸脚已隐藏，但 body_mask 仍用 source/direct 无条件并集

src/dressing.py:2669–2720。上轮提过的风险仍在：source-only 错误遮面不会被 direct 否决，透明材料与靴口/袜口需检查。最好输出每个目标面遮蔽来源（source/direct/both），以多视角 visible skin/false-hole 检验；不可因隐藏面数多就认定换装几何正确。

---

## 九、下一步实施顺序：先纠正证据，再精修袜子

### 第 1 批（P0，必须先做）：mask 极性与数据真实性

1. **在本机 mmd_tools 拿到 import/export/mmd_rigid BoolVectorProperty 的真实源码**，验证 True 含义；写两刚体/两组 PMX raw 掩码最小 fixture：禁止自组、允许跨组、禁止跨组、双向/单向禁碰；核对导入属性→导出原 PMX bit 完全 roundtrip。
2. 修 physics_sim、physics.py 的 mask 解释，并重新构建 expected pair matrix。不要仅反转报告文字，必须修改迁移和 break 的实际行为。
3. A/B **每条件冷启动**重新跑，打印原始 PMX raw contact matrix 与 Blender layer potential matrix 的 FP/FN。当前 16090、8910、+4242、−3.6% 先标为 unverified。
4. 出具逻辑结论，只对原始 PMX contact matrix 完全通过的迁移宣称“translation logically valid”。

### 第 2 批（P0/P1）：只处理双遍与少量关键近场 contact

1. 做 Mode1 父骨→Mode0 子刚体的两帧对照 fixture，检查 handler 帧序和 offset；移除无法自证的“拨 frame_start 两次 = 清缓存”假设。
2. 报告 global / near-field / swept 3 层过滤差异；近场错误 pair 小时，只对该集合试验 non-collision constraints，严格观测性能和副作用。
3. 分开记录真实播放器画面 QA 与 Blender 代理结果，**删除“额外误碰撞只会让情况变差，所以 −3.6% 是下界”** 的推理。

### 第 3 批（P1）：保留已有袜子进展的小修

1. 修 project_layer_on_limb 的 local/world 空间（独立物体变换测试）。
2. 对 subdivide_triangles 解决 T-junction、shape-key/所有 UV 和 loop attribute；加三角/无 UV 断言。
3. 用连续膝过渡/靴口 overlap 修掉“小腿白边”和“膝堆叠”；只对袜子 patch 转 B 的权重；暂时保留 A 的 UV，不重新 bake。
4. 如果动态仍经常露皮，再尝试「A 袜先贴到 B 附近 → B patch Data Transfer UV」，必要时才用二维解剖 barycentric mapping。

### 第 4 批（P1）：成品验收

- sign-flip 6 mm 是回归 proxy，不是几何总穿透。验收包括裸皮可见像素、真实 mesh 相交、边界 crack、膝/踝动态、UV 面积密度/岛连续性、shape key、重导入 PMX、MMD 播放器渲染。
- 报告分别标记 translation_logically_valid、blender_proxy_valid、visual_improvement，不能用一个布尔值代替三层证据。
- 不要在碰撞极性尚不可靠时让执行 Agent 优化更多碰撞层或物理 spring；不要一次性重建全部鞋/手套。**先完成最小 mask 语义验证，随后局部修袜、保持现有可用成品。**

---

## 参考文件

**当前仓库（8fed10c）**：src/physics_sim.py、src/physics.py、src/qa.py、src/dressing.py、progress.md、scripts/blender_runner.py。

**上游关键证据**：
- https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/properties/rigid_body.py
- https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/core/pmx/importer.py
- https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/core/pmx/exporter.py
- https://raw.githubusercontent.com/MMD-Blender/blender_mmd_tools/main/mmd_tools/core/model.py
- https://docs.blender.org/manual/en/5.2/modeling/modifiers/modify/data_transfer.html
- https://docs.blender.org/api/current/bmesh.html
- https://docs.blender.org/api/current/bmesh.ops.html
- https://docs.blender.org/manual/en/latest/render/cycles/baking.html

**边界说明**：最重要的 mask 结论由上游导入、导出、属性描述和刚体构建源码共同支持；真正本机二进制版本和两个代表性 PMX 的验证需要用户在 Blender 中执行。除这些可以由代码确定的问题外，本报告没有把无法观察的物理运行结果伪装成实测。
