# REVIEW3 Errata — 碰撞遮罩语义纠错、物理 A/B 与漆皮 UV 最简路线

> 仓库：<code>NiHaiMa123/mmd</code>  
> 本勘误依据：用户在 **Blender 5.2 本机扩展源码、PMX 格式文档及达妮娅/刻晴两模型**上的核验；并重新阅读当时 main <code>3df293e608468d93db5bb88551710cdca18717c4</code> 的 <code>src/physics_sim.py</code>、<code>src/qa.py</code>、<code>progress.md</code>。  
> 被勘误文件：<code>docs/REVIEW3.md</code>（保留原文件以便追溯，**不修改原文件**）。  
> 范围：只纠正第三轮 review 的错误及由此引出的判断，不改功能代码；未在本地独立运行 Blender 或重新测试 PMX/VMD。下文所称“实测”均指用户已提供的实验记录。

## 0. 结论先行

**撤回 REVIEW3 的 P0-CRITICAL 指控：本仓库在导入后使用的 <code>mmd_rigid.collision_group_mask</code> 中，True = 允许与该组碰撞，False = 排除该组；<code>src/physics.py</code> 与 <code>src/physics_sim.py</code> 按 True=allow 解释，方向是正确的。** 上轮把 PMX 文件中的 non-collision 原始位，与 importer 反转后的 Blender 属性混为一谈，是审查错误。无需为此反转项目的 collision mask 逻辑。

保留 REVIEW3 的其余重要判断：Blender 的 20 个共享碰撞层并非完整 PMX 成对过滤；两遍 setup / point cache 的重算没有被严格证明；多余假接触**可能让穿模变多也可能变少**，不能称 −3.6% 为真实 MMD 改善的“下界”。

**新增发现（本次重读当前代码）：<code>contact_matrix_report()</code> 的 <code>effective_blender_layer_pairs</code> 公式写错；所谓“初始 12 cm near-field”实际上可能读到 setup 双遍扫描后的末帧位置。** 这两项属于统计实现问题，与遮罩极性无关，应列入下一次修复。

在工程选择上推荐：

- **档 A：原始 PMX / 导入后数据的碰撞矩阵逻辑验证，作为翻译正确性的唯一直接判据。**
- **档 B：Blender 用作近似动力学回归与视觉异常筛查；固定声明“非 PMX 物理等价”。**
- **漆皮层优先保存 A 自身几何与 UV；只有形状、骨骼拓扑确实不适用的局部才生成 B-derived patch。** UV 迁移先试 Blender 原生 Data Transfer，不必一开始实施复杂解剖参数化。

---

## 1. 正式纠正 REVIEW3 第一节 P0-CRITICAL

### 1.1 三层数据不能混淆

| 层次 | 值为 1 / True 的含义 | 备注 |
| --- | --- | --- |
| **PMX 文件原始 non-collision mask bit** | **禁止**与该组碰撞 | 文件是 deny-list，默认允许；某 bit 为 1 即该组被排除。 |
| **mmd_tools importer 转换后的 <code>mmd_rigid.collision_group_mask[g]</code>** | **允许**与该组碰撞 | importer 将文件位逐位取反。 |
| **mmd_tools exporter 写回 PMX** | 属性 False → 文件 bit 1（禁止） | exporter 再次取反，和 importer 互逆。 |

用户已核验的核心代码：

~~~python
# PMX -> Blender mmd_rigid（文件 bit=0 才给 True）
collision_group_mask = [
    rigid.collision_group_mask & (1 << i) == 0
    for i in range(16)
]

# Blender mmd_rigid -> PMX（属性 False 才写文件 bit=1）
mask = 0
for i, v in enumerate(mmd_rigid.collision_group_mask):
    if not v:
        mask += 1 << i
~~~

因此当数据已经经过 <code>import_pmx()</code>，两刚体之间的 PMX 允许碰撞谓词应为：

~~~python
def pmx_filter_allows(a, b):
    return (
        a.mmd_rigid.collision_group_mask[b.mmd_rigid.collision_group_number]
        and
        b.mmd_rigid.collision_group_mask[a.mmd_rigid.collision_group_number]
    )
~~~

任意一侧 False 都应禁止该 pair。上面是**group/mask 基础过滤关系**，不等于场景中一定发生实际接触，也不包含额外物理约束或求解器行为。

本机模型的交叉证据亦支持这个解释：

- 达妮娅组 3 的 10 个 mode 1 真物理刚体属性 mask 全 True，按导入后属性理解为允许所有组，合理。
- 刻晴裙摆组 6 的 72 个 mode 1 刚体允许集合仅为 {6}，因此原模型裙摆不允许碰腿组，与观察到的裙摆穿腿情况相符。

**错误来源**：属性文件里的英文描述 <code>The groups the object can not collide with</code>，以及 <code>core/model.py</code> 里变量名 <code>ignore</code> 和建 non-collision 约束路径，和导入/导出的布尔语义产生表面矛盾。上一轮引用这些**描述/内部变量名**，没有把 importer 的 <code>== 0</code> 正确代入求值。对于你这条「导入 PMX → 换装 → 导出」链路，应以本机 importer/exporter 的真实转换和 PMX 原始位为准，不能让注释覆盖运行中的数据契约。

### 1.2 对 REVIEW3 其他结论的影响

| REVIEW3 的原结论 | 更正 |
| --- | --- |
| “P0-CRITICAL：True 表示禁止；项目把极性反了” | **撤回。** True=允许；项目沿用现有 True=allow 正确，不应全局反转。 |
| “现有 16090 / 8910 / 4242 数据因 mask 极性必然无效” | **撤回该理由。** 这些统计的基础 mask 方向可以正确；仍需校验报告实现与 Blender layer 代理误差。 |
| “应先修 physics.py 和 physics_sim.py 的 mask 极性再做别的事” | **删除此任务。** 应加 importer/exporter round-trip 单测作为防回归，而不是反转逻辑。 |
| “Blender 代理碰撞层不是 PMX 完全等价” | **保留。** 共享 layer 会额外允许不期望的 pair。 |
| “−3.6% 不能当作真实 MMD 改善下界” | **保留。** 假接触对输出穿模没有单调影响。 |
| “setup 双遍 / cache 需要可重复性校验” | **保留。** 与 mask 极性互不相关。 |

建议永久添加一个简单的单测注释和转换函数：<code>pmx_non_collision_bit = not blender_allowed_flag</code>。这样后续模型和 Agent 不会再次被 ambiguous 的 <code>mask</code> 字段名误导。

---

## 2. 最新 contact_matrix_report 的两处实际统计问题

这两项是在本次复核 main 上 **当前版本**发现的，不是纠正用户已确认的 True=allow。

### [E-01] <code>effective_blender_layer_pairs</code> 计算式错误（静态确定）

位置：<code>src/physics_sim.py:175–180</code>，当前：

~~~python
"effective_blender_layer_pairs": n * (n - 1) // 2 - false_negative
~~~

但 <code>effective</code> 是 <code>shared = bool(li & lj)</code> 为 True 的 pair 数，不是“所有 pair 减漏接触”。

正确恒等式：

~~~text
expected = TP + FN
effective = TP + FP
effective = expected - FN + FP
~~~

按用户的 ON 数据：<code>expected=16090</code>、<code>FN=0</code>、<code>FP=8910</code>，**effective 应为 25000，而当前公式会误报 62835**。OFF 数据：<code>11848 + 1936 = 13784</code>，而不是 62835。该 bug 不改变 <code>false_positive_layer_pairs</code>、<code>false_negative_layer_pairs</code> 已逐对累加的数值，但会污染整体 summary、覆盖率与后续报告。如果未来某次 FN>0，问题仍然存在。

直接在逐对循环增加 <code>shared_pairs += int(shared)</code>，同时 assert <code>shared_pairs == expected_pairs - false_negative + false_positive</code>，可完全防止此类误报。

### [E-02] near-field 12 cm 并不一定是“初始空间近邻”（静态确定调用顺序）

位置：<code>src/qa.py:483–500</code> 调用 <code>physics_sim.setup(...)</code> 后才：

~~~python
setup["contact_matrix"] = contact_matrix_report(
    _rigids,
    positions={o.name: o.matrix_world.translation for o in _rigids}
)
~~~

而 <code>setup()</code> 本身在 <code>src/physics_sim.py:337–365</code> 已将场景逐帧推进两遍。**因此这里的 <code>positions</code> 是 setup 返回时的对象矩阵，不是导入后、模拟前的初始位置**。是否恰好回到了起始姿态取决于求值/缓存；不能把报告写成“初始 12 cm”。

此外当前 near-field 按**中心间距离** <=0.12，而不是 collider 外表面间隙：两个较长的裙摆胶囊或大腿碰撞体虽然中心相距 >12 cm，表面仍可能接触；中心靠近的 pair 也可能因形状/位置不相交。因此 <code>near_false_positive</code> 只能叫“某帧中心距代理筛选误差”，不是相关性/接触的完备证明。

最低成本改法：
- 在任何 setup / <code>frame_set</code> 物理推进**之前**保存 <code>rest_positions</code>；只把它传给 <code>initial_near_field</code> 统计；
- 同时按刚体半径/shape 的保守外接球间隙（<code>||centerA-centerB|| - radiusA - radiusB</code>）判断可能接触，别把 12 cm 当唯一标准；
- 可选：从代表性动作里抽关键帧建立 <code>dynamic_near_field</code>，近场阈值/是否已发生接触必须分开命名；
- 对真正决定裙摆↔胯/膝的少数 pair 输出原始 bone、group、mask、空间距离与 ON/OFF layer 位，而不是仅看全局 8910。

**别把“8910 个 layer 允许错误”写成“8910 次物理误碰撞”。** 它们是潜在 pair，而非 Bullet 已生成的 contact manifold。

### [E-03] 关于 Blender layer“单向过滤”的表述

用户在 <code>work/test_collision_filter.py</code> 做过两球实验，但该文件未包含在 Git 仓库的跟踪文件中，本次无法审查其具体步骤。仅针对当前用于矩阵统计的 <code>shared = bool(li & lj)</code>，这一规则是**对称**的；“一侧放开也撞”应理解为“一侧在多个 layer 中开启，两个物体仍共享至少一个 layer”，不应简单视作非对称碰撞决定过程。保留两球 fixture，新增一个“交集空 / 交集非空 / joint 禁碰”三分测试，进一步校验期望的 Blender 有效关系。

---

## 3. setup 两遍扫描：最省事且可靠的替代实现

### 3.1 现有问题是什么（不是断言“每次一定错”）

关键代码：<code>src/physics_sim.py:313–365</code>。

当前执行顺序是：先安装 <code>frame_change_post</code> handler，再开始第 1 遍逐帧推进；每帧 <code>scene.frame_set(f)</code> 可能完成当前帧的 Bullet/动画求值，随后 handler 将 Mode1/2 刚体结果写回骨骼；setup 才将 Mode0 物体置为新世界矩阵并为 f 帧插关键帧。第二遍开始前把 <code>point_cache.frame_start</code> 改为 <code>first_frame-1</code> 再改回。

**问题不是已有证据能够断言“缓存完全没清”**，而是：这两个赋值不是一个经过本工程验证的“彻底释放并重建所有求解状态”的契约；即使它们在当前 Blender 5.2 某次触发了重算，仍可能产生同帧/前一帧时序混合。<code>frame_change_post</code> 按 Blender API 是**新帧完成求值之后**回调，所以“handler 已安装”不等于“物理在计算 f 帧碰撞之前已读取 f 帧回写骨骼”。<code>max_follow_error</code> 只检验平移差，也不能验证角度偏差或完整模拟状态。

### 3.2 推荐方案：**预烘焙运动骨的 Mode0 → 干净进程模拟一次**

为了少改代码、并尽量利用当前已有的独立冷启动 A/B，我建议一个非常明确的 **Prepare once / Simulate once** 两阶段方案。

**Stage K：仅制作碰撞体的确定性跟骨动画，**不运行物理。

1. 从同一个基线 PMX/VMD 导入，冻结静置 <code>rigid_rest_world</code> 与 <code>bone_rest_world</code>；保留你已修复的 offset。
2. 暂时让活动物理仿真不执行（例如在准备阶段关闭 rigid body world，具体操作以本机实验验证）。**不要安装 physics→bone handler**。
3. 逐帧求出所有由**VMD/普通动画直接驱动、且不依赖物理骨**的 Mode0 目标矩阵，将 <code>bone_pose_world(f) @ offset</code> 直接写成 keyframes。可以依次产生 f 帧动画，但不让 Bullet 积分。
4. 把这个确定的 Mode0 运动资产保存到新的临时 <code>.blend</code>／中间文件，**启动新的 Blender 进程**加载；不要在当前进程强行拨缓存两次。
5. ON/OFF **各从同一份 Stage K 资产新开进程**，在第一次物理求解之前设置碰撞矩阵，初始化 world、安装所需写回，然后从 first_frame 顺序模拟 **一次**。
6. 将两个冷启动仿真结果按相同帧采样；比较渲染/轨迹/mesh 与对应原始数据。

这能直接移除“前一遍已经做过物理、后一遍依赖缓存刷新”的不确定性，保留已有的 Mode0 offset 逻辑，并且成本远低于重写整套 Bullet 接口。

**必须明确一个例外：若 Mode0 刚体依附的骨骼本身由 Mode1/Mode2 物理驱动，则不能在 Stage K 仅凭 VMD 预计算出正确轨迹。** 对这种依赖存在 3 个可选处理：

- **推荐最低成本**：统计这种依赖的刚体和其可能影响的接触 pair；先对该子集报告 <code>feedback_unverified</code>，对不涉及它的动画驱动碰撞/视觉代理继续验收。
- 若这一反馈确实决定裙摆与腿的接触，用 Blender 的物理约束/rig 驱动关系明确表达这种同帧依赖，或采用真正支持 MMD 物理驱动语义的运行时；不能靠 2-pass 热缓存重算“证明精确”。
- 接受上一帧结果驱动下一帧 Mode0 的**显式一帧延迟代理**也可以做粗回归，但必须在报告里标记 <code>one_frame_lag_proxy</code>，绝不能宣称 MMD 等价。

这个拆分不要求现在就实现完整 mode2 语义；应如实记录 mode2_count / 受影响的部位并隔离相应结论。

### 3.3 如果确实想保留两遍怎么办？

可以把它降级为**只用于诊断**，而不是 QA 的正式求解流程：分别保存第 1 遍与第 2 遍关节/刚体轨迹，比较 Mode0 平移+四元数旋转误差、Mode1/2 物理态与骨骼写回同帧偏差；观察停止更新后的结果是否收敛。若第二遍轨迹与同一输入的新进程 fresh simulation 不一致，应立刻判定 cache/state 污染。

**不建议寻找一个“万能清 cache API”来修补现有时序**。即便清缓存可靠，也解决不了先求解 f 再插入 f 的 Mode0 keyframe 的相位问题。先用两个刚体的最小 fixture 验证 Mode1 父骨→Mode0 子碰撞体在同一帧的关系（旋转、平移与 collision 轨迹），再考虑任何反馈实现。

参考 Blender 5.2 API：<https://docs.blender.org/api/5.2/bpy.app.handlers.html>（frame_change_post 在新帧求值后调用）；<https://docs.blender.org/api/current/bpy.types.PointCache.html> 和 <https://docs.blender.org/api/current/bpy.ops.ptcache.html>（缓存属性与操作）。

---

## 4. 选择“档 A + 档 B”后，A/B 应怎样写才不误导？

### 4.1 可以保留的客观事实

根据已有记录，ON/OFF 分别在**独立冷启动 Blender 进程**下执行，同模型、同 VMD，抽取 6 帧：

| 代理结果 | ON：迁移后的服装↔身体接触 | OFF：关闭该跨部件关系 |
| --- | ---: | ---: |
| 6 帧 sign-flip proxy 总点数 | **3955** | **4103** |
| 差值 | **−148** | 相对 OFF **−3.6%** |
| 最差帧 sign-flip 比例 | **0.969%** | **1.032%** |
| 当前 PMX 期望过滤 pair 数 | **16090** | **11848** |
| 当前 Blender 共享层位 FP（全局） | **8910** | **1936** |
| 当前共享层位 FN（全局） | **0** | **0** |

以上按用户记录报告，不冒充此次独立复测；新增的 <code>effective_blender_layer_pairs</code> 总数公式需按 E-01 修复后再引用。

### 4.2 建议直接复用的报告措辞

> 在两个独立冷启动 Blender 5.2 进程中，以相同 PMX、VMD 和采样配置运行 ON（启用迁移后的服装↔身体碰撞组）和 OFF（禁用相应跨部件关系）。对 6 个样本帧，旧版 6 mm sign-flip **代理指标**分别为 3955 与 4103 个命中，ON 比 OFF 少 148 个（约 −3.6%）；最差帧命中比例分别为 0.969% 与 1.032%。这说明**在当前 Blender 代理模拟和这 6 个采样帧里**，打开相关碰撞关系伴随代理命中数略降。它不等同于真实 MMD 的穿模改善，也不证明所用 Blender layer 过滤与 PMX 等价；全局共享层位存在大量潜在 FP。该结果不能被视为真实改善的上界或下界，亦不能外推到未经采样的动作或更深穿模。

建议报告 JSON 标注：

~~~json
{
  "claim_type": "blender_proxy_ab_observation",
  "engine": "Blender 5.2 rigid body proxy",
  "reproducibility": "two independent cold-start runs, as recorded",
  "samples": 6,
  "measure": "6mm sign-flip proxy hits",
  "on_hits": 3955,
  "off_hits": 4103,
  "relative_difference": -0.036,
  "mmd_runtime_validation": false,
  "pmx_filter_equivalent": false,
  "global_false_positive_pairs_on": 8910,
  "global_false_positive_pairs_off": 1936,
  "conclusion": "ON had fewer proxy hits in the sampled frames; true MMD visual benefit is unproven"
}
~~~

### 4.3 三层口径重新收口

**档 A / 逻辑层**：你已确认 True=allowed，原项目逻辑无需反转。若“ON 比 OFF 恰增加 4242 个目标 garment↔body pair、其余 expected pair 不变”确已在**原始 PMX/导入后数据**逐 pair 核实，便可说“**计划的逻辑碰撞关系修改通过**”。**此结论与 Blender FP=8910 并不矛盾。** 但要检查 <code>outfit_groups</code> 与 <code>body_groups</code> 的对象分组不存在共享 group/漏分组；按 group 关掉跨部件关系未必等同于精确按 object pair 关掉。

**档 B / 动力学代理层**：可以说“**物理回归可运行，且观察到部分代理命中下降**”；若 near-field 碰撞关系有错，显式附上误差和涉及的部位。不该写“仿真已正确复刻 PMX”“MMD 里至少改善 3.6%”或者“外观改善已经得到证实”。

**成品外观层**：仍需实际播放器或可信 PMX 运行时的可见穿模/漏肤、裙摆轨迹和代表性动作复检，才可填写 <code>visual_improvement=true</code>；目前更严谨状态是 <code>not_established</code>。

建议把 <code>blender_proxy_valid</code> 拆为 <code>simulation_runs</code> 和 <code>filter_fidelity</code>，因为 **“Bullet 在运动”不等于“碰撞对全部正确”**。

### 4.4 关于额外 FP 的影响，特别纠正“下界”

ON 的额外假接触可能把裙摆推离腿（使指标变好），也可能推入腰/另一侧腿（使指标变坏）。动力学响应非线性，**无从从 FP 数量推导 ON 改善是更保守的下界**。正确做法是选与胯/膝空间接近且在动作中可能接触的 FP pair 定点看轨迹，而不是把 8910 当作 8910 次真实接触。

---

## 5. 漆皮层：最快路线不是重拓扑，而是保留来源 UV

### 5.1 推荐“按部件分流”，不是把 target-derived patch 用到全部服装

| 部件 | 默认路线 | 何时才做 B-derived patch |
| --- | --- | --- |
| **过膝袜**（A 漆皮、当前径向分段贴合有效） | **保留 A 细分后的几何、原 UV、原贴图**；补膝过渡、踝部包覆和局部目标权重 | 动态反复漏肤、袜片跟随 B 变形不稳定，或来源几何缺失而不能补片 |
| **简单袖口/手套** | 若手套来源完整且各指跟随正确，先保留 A UV 做局部 cage/射线撑开 | B 五指骨变化大、指缝错配、手指运动撕裂 |
| **贴皮式鞋面** | 若闭口不透明，优先保留 A 鞋面/鞋楦和原 UV，隐藏被完全覆盖的 B 足部皮肤，按 heel–ball–toe 补鞋长/宽/高 | 开放趾或透明部位必须准确跟随 B 各脚趾时，在相应露出区域生成 B-derived patch |
| **鞋底、鞋跟、靴筒、金属饰件** | 保留 A 原几何与原 UV，分件变形或锚定 | 通常不走 B-derived patch，因它们不是身体皮肤 |

**重要：目标有 5 根独立脚趾（多根骨），并不意味着一双不透明封闭靴子必须逐趾重建。** 鞋楦需把整个目标脚的形状包络住；内部脚趾正确蒙皮可隐藏在鞋里。只有漏趾、露肤、透明鞋或者真实需要逐趾变形的贴皮部件，才需要独立 B 趾表面和权重。

这样能最大限度复用你已经成功的「A 漆皮几何 + 按解剖轴撑开」，也避免 UV 重制工作量。

### 5.2 最省事的 B-derived patch UV 迁移：Data Transfer，不烘焙纹理

如果必须从 B 复制皮肤三角形生成新 patch，不要求先做纵向 u/环向 θ 的完整解剖参数化。

**步骤：**

1. 把**原 A 的漆皮组件复制一份作为 UV donor**：保留所有 UV islands、材质和贴图。
2. 对 UV donor 使用你现有的**分段径向贴合/鞋楦 landmark/cage warp**，让其位置、轮廓尽量与 B patch 在同一静置姿态重合。只为对应查找，不必作为最终渲染件。
3. 从 B 的固定素体复制对应三角面，继承 B 权重，成为 **B patch**；A donor 和 B patch 均在 rest pose 下对齐。
4. 在 B patch 上使用 Blender **Data Transfer Modifier**：源对象选变形后的 A donor；数据类型选择 **Face Corner Data → UVs**；优先 **Nearest Face Interpolated**，局部法线方向明确时试 **Projected Face Interpolated**；设 Max Distance，并适当设 Islands Precision。
5. 按左右、袜上/下、掌心/手背、鞋面/鞋底分别传输，避免最近面误跳到别的 UV 岛或另一根手指；只迁移选定 UV layer。
6. **保留 A 原纹理图片不变**，迁移的是 UV 坐标而不是图像颜色；只要匹配关系正确，**没有额外纹理 bake 重采样带来的分辨率损失**。这不保证所有图案都不拉伸，需看 UV 畸变和岛边界。
7. 对无法映射的角点、跨 UV 岛接缝、花边/Logo 畸变产生定位报告；仅对少数坏区做手工 landmark 或二维解剖插值。只有 Data Transfer 失败且图案复杂时才考虑高分辨率纹理 bake。

官方 Blender 5.2 说明：<https://docs.blender.org/manual/en/5.2/modeling/modifiers/modify/data_transfer.html>（UV face-corner；Nearest Face Interpolated；Projected Face Interpolated；Islands Precision/Max Distance）。

**为什么省事**：这等价于“先把来源 A 拉近 B，使 Blender 能用现成的最近三角面插值正确寻找原 UV”，避免自己实现二维展开、周期接缝、反向映射及纹理烘焙。

### 5.3 纯色或简单纹理袜子更简便的方案

如果「腿」材质是单色/简单渐变、原 UV 图案要求不高，**可以直接给 B-derived patch 使用新建的简单圆柱 UV（或原有 B 皮肤 UV + 调整纹理缩放）和来源材质参数**。不一定非要逐点迁移复杂的 A UV。若存在特定纹样/Logo，才应走第 5.2 步的精确 donor 映射。

对当前 final18，优先修膝盖堆叠和踝部小白边，别在画面基本正确时为了理论上的全自动 patch 重做整条袜子。对 A 几何径向撑开后的**动作权重**，可以只在贴肤段局部迁移 B 权重（保留袜口/装饰特殊骨权重），这是比换 UV 更可能决定动态稳定性的改动。

### 5.4 特别提醒：靴子项目的优先约束

鞋内裸脚已通过遮蔽消失，但这只证明**视觉上不露脚**，不证明靴子真实适配 B 的脚形；对于不透明封闭靴子，正确的低成本 QA 是鞋楦是否包住目标脚的长度、宽、高，以及鞋尖/鞋口/金饰是否变形。鞋子来源只有一根 足先EX、B 有多个脚趾骨，并不是要求鞋面全部复制 B 的脚趾网格；来源不透明鞋面可以按掌跖/鞋楦整体驱动，不必逐趾跟随。

对透明或贴皮鞋面局部，才把 B 的趾面 patch 生成出来，然后沿 A donor 的原 UV 做 Data Transfer；硬质鞋底和金饰继续保留 A 的几何及 UV。

---

## 6. 建议的最小后续任务（仅建议，**本次不改源码**）

**R3-E0，统计正确性**：修 <code>effective_blender_layer_pairs</code> 的数学恒等式；把初始 near-field snapshot 移到 setup 之前；按刚体 shape 的近场间隙和动作期间空间近邻补充统计。保留 True=allow，不再以 REVIEW3 P0-CRITICAL 为由改 mask 极性。

**R3-E1，单次冷仿真**：优先去除正式 QA 的热缓存两遍扫描，将 Mode0 的确定性 VMD 动画在 physics disabled 阶段预烘焙；随后 ON/OFF 各从干净保存资产启动新进程、只模拟一次。识别 Mode1/2 驱动的 Mode0 依赖并报告例外；至少跑一个父 Mode1→子 Mode0 的帧序 fixture。

**R3-E2，定性 + 定量代理**：保留 3955/4103 数据为“Blender 近似模拟中 6 帧 sign-flip proxy”，清楚附带 layer FP 与时序不确定性；不将 −3.6% 描述为真实 MMD 的改善、上/下界、或视觉成功证明。

**R3-E3，漆皮局部修复**：过膝袜继续 A 几何/A UV 路线，优先修膝过渡、踝边缘、动态权重；闭口靴子按鞋楦包络 + 原 UV 保形；仅在需要 B-derived patch 的部位使用「贴近后的 A donor → B patch Data Transfer UV」，失败再升级解剖参数映射/烘焙。

本勘误是对第三轮错误的**明确更正**：源代码无需因误读 mask 而反转；已有的物理模型代理仍可继续作为粗回归使用，但不应承担它不能证明的 MMD 物理正确性。
