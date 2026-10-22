# REVIEW4 — 第四轮 MMD 换装与物理 QA 代码审查

> **仓库**：NiHaiMa123/mmd  
> **审查基线**：main @ <code>62ca5e563e79b2e16e93469f1dff60a1d20d57fe</code>  
> **本批对应提交**：620f9fa、b56f6df、777227e、61058db、9022d37、14d715f、8ef40f1、62ca5e5；审查基于最终文件状态，不把中间提交当作交付版本。  
> **审查重点**：<code>src/dressing.py</code> 的 <code>subdivide_triangles()</code>、<code>project_layer_on_limb()</code>、<code>transfer_target_weights()</code>；<code>src/physics_sim.py</code>、<code>src/qa.py</code>、<code>scripts/blender_runner.py</code>、<code>progress.md</code>。  
> **执行限制**：静态源码审查；仓库中可确认有三张 <code>docs/images/final22_*.png</code>，但当前 GitHub 文本接口不能读取二进制 PNG，因此**没有直接看到图像像素**，对画面只使用 progress.md 的描述和用户已有实测。<code>work/test_subdivide3.py</code> 不在当前 Git 跟踪树中，因此“9 项全绿”是项目自报，无法检查测试断言或独立运行。**没有在本地 Blender 5.2、PMX 或 VMD 上复现。**

## 0. Executive summary：下一步先攻什么？

**优先：修两个新代码层面的真实风险，再快速封闭脚踝缝隙，最后才攻完整鞋楦。**

1. **P0：<code>subdivide_triangles()</code> 的扇形中心 UV 插值有确定性错误。** 几何拓扑不留 T-junction 是进步，但中心在不同扇形三角面的 UV 被分别设成不同的“边中点”，会在**原来一张三角形的内部产生纹理断裂**。现有“每个 UV 层都写了”与“UV 保真”不是一回事。
2. **P0/P1：<code>project_layer_on_limb()</code> 的“外来骨”识别与目标权重覆盖存在语义混淆。** <code>body_bones</code> 实际来自原骨架映射键，不等于目标素体所有真实骨；发现一个不在此集合、但确实是 B 身体骨的组，可能跳过整个袜层，或者满权重混合后把目标 B 的真实辅助骨权重过滤掉。
3. **P1：脚踝缝隙**是目前最好获得“明确视觉通过/失败”的小工作：先区分“确实没有覆盖三角形”与“<code>__mmd_hidden__</code> 材质竟然可见”，再以**袜/源腿皮肤片区的局部边界带 + 与靴筒重叠**修复，而非扩大整条腿、强行拉下边缘。
4. **P1/P2：露趾**是更大的几何任务，应独立拆成“可见性”和“鞋楦宽度/封口”两条验收；不要再尝试整只鞋最近点投影。先测 heel-ball-toe 局部宽度/足背高度，分离鞋帮、鞋头、鞋底、金饰后做有约束的绝对位移，或对不透明封闭鞋选择局部正确遮蔽作为视觉 fallback。
5. **Blender 物理继续只承担 proxy 回归。** final22 普通动作 QA 改善但带物理 proxy 有退化，不能相互抵消、也不能推导目标 MMD 的改善。物理未成为当前最值得继续投入的主线，除非先验证 setup 反馈与求解稳定性。

---

## 1. 对本批“已修”的逐条判断

| 修改项 | 静态判断 | 尚缺的证据或潜在风险 |
| --- | --- | --- |
| 620f9fa 细分共享边保留 | **方向正确**：共享外部面的边不插入中点，避免常见局部 T-junction；含形态键绝对位置写回 | **扇形中心 UV 错误**；未处理所有非 UV loop 属性、特殊 non-manifold 边；9 个测试脚本不在仓库可复核 |
| 全部 UV layer / shape layer | **相对上轮进步明显**，按边/中心线性写了形态键绝对坐标 | 必须核验中心 UV 一致性、UV 岛边界、active key、PMX UV morph / 拓展数据 |
| b56f6df 轴参数与 ±5 cm 膝混合 | 参数现在实际参与选骨；smoothstep 避免“高度一到膝就换轴” | 两种独立射线命中点的**线性混合不保证仍贴在体表**；现有 local/world 混用仍在 |
| 目标权重与伪组排除 | <code>mmd_edge_scale</code>、<code>mmd_vertex_order</code> 不是骨这一点处理方向正确 | <code>body_bones</code> 定义范围错；整层跳过条件过粗；blend=1 可能过滤真实 B 辅助骨 |
| 777227e follow 平均/P95/最差帧 | 报告较原来更可解释；mode2/feedback count 是诚实的代理边界 | 仍在当帧写 key 之前测、只测平移且混合所有刚体样本；两遍 point cache 问题未解决 |
| 61058db effective pairs 算式 | **确认已修正**：直接统计 shared，断言 <code>effective=expected-FN+FP</code> | <code>near_by_group</code> 的 near 计数却在所有错误 pair 上累加，仍有确定性报告 bug |
| 9022d37 near-field 采样时机 | **确认更正**：setup 前 <code>view_layer.update()</code> 然后拷贝静置位置 | center distance 12 cm 是粗候选，不能当真实接触/完整近场范围 |
| QA denominator 与 UNKNOWN exit | 普通 motion QA 增加分区候选数；runner 的 UNKNOWN/FAILED 返回非 0 | 符号“存在”不等于“符号足够大、可做判断”；**物理 QA 分支仍不输出各分区 denominator** |
| 14d715f 旧鞋路线默认关闭 | **正确保护成品**，三次失败是有价值的负证据 | “径向 factor 顶到 1.3”**不足以单独证明**来源鞋在同一解剖位置比 B 窄 ≥30%；要做对应剖面几何测量 |
| final22 交付与图片 | progress 记录了完整模型和关键缺陷 | 当前接口未能读取 PNG，不能把其当作本次“我亲眼确认”的视觉证据 |

---

## 2. P0 — <code>subdivide_triangles()</code> 新引入的 UV 保真错误（优先修）

### [R4-P0-01] 扇形中心 UV 按边中点写入：同一个几何中心有多个不一致 UV

**代码**：<code>src/dressing.py:1235–1331</code>，关键在 **1323–1330**。

当前 fan 模式会在每张新三角面的中心 loop 写：

~~~python
u0 = vals[k]
u1 = vals[(k + 1) % m]
nf.loops[2][lay].uv = (u0 + u1) * 0.5
~~~

但是每张扇形新三角面共享同一个**几何中心顶点**，其对应 UV 应当是原面**同一个二维中心位置**。现在会随着所选边的不同而变化，造成相邻新三角面在内部中心/放射边**UV 不连续**。

**构造性反例**：原三角面 UV 三角形 U0=(0,0)、U1=(1,0)、U2=(0,1)；三条边若都保留而采用三角扇形，则三个扇形中心分别被赋值 (0.5,0)、(0.5,0.5)、(0,0.5)。几何上同一中心点在三张子面具有三个 UV 值，纹理“开裂”。即使因为边中点存在而不是 3 扇形，结果同样不一致。

**最小修复**：

~~~python
# 逐来源面、逐 UV layer 只算一次该面的 UV 中心
uv_centre = sum(original_corner_uvs, Vector((0, 0))) / n
# 每个扇形子面的 centre loop 使用同一个 uv_centre
nf.loops[2][lay].uv = uv_centre
~~~

一个面原本位于 UV seam 的两个岛之间没有问题：UV 中心只须**在各自的原始来源面内**一致；不要跨来源面平均 UV。对一般非三角多边形，简单中心平均需要额外保证 UV 空间非自交；现有默认 PMX 三角形情况下可优先按此实现。

**补充专项测试（现有 9 项绿仍可能漏掉）**：

- 一张原三角面，保留 1、2、3 条边，以扇形切分；检查每张共享内部边两侧 loop 的 UV **严格一致**，且与原面双线性/重心插值映射一致。
- 2 个相邻三角面，只有一个被选中；测试外侧边不产生 T-junction，并且被选面**内部**没有 UV 裂缝。
- 一个有两张 UV 图层、跨 UV seam、250 个 shape key 的片区；测试新顶点每层 shape 的 absolute co 与源权重插值一致。
- UV 图像用高频棋盘/条纹实拍：变形前后除几何重映射外不允许额外不连续或断线。

### [R4-P1-02] “所有属性保留”范围大于实际实现

**代码**：<code>src/dressing.py:1144–1190、1223–1339</code>。

当前显式处理的是 **co、deform 权重、shape layers、UV layers、material_index、smooth**，而不是 Blender Mesh 的“所有属性”。以下尚无逐层转移：loop/corner color attribute、顶点色、custom normals / split normal、非 UV 的泛型属性、部分 MMD 扩展通道的导入/导出约定。没有这些层的模型可以正常工作；对存在的模型，不能静默宣称属性全保真。

尤其 <code>mmd_vertex_order</code> 是伪顶点组，代表的数值可能具有索引/排序意义，**不能默认线性插值后就与源拓扑语义一致**。目前所有 deform 顶点组（含伪组）都做算术中值；建议逐属性定义处理政策：连续量插值、离散序号重新生成、未知属性拒绝/警告。检查 PMX export→reimport 后的 morph/材质/UV/顶点排序，而非只看 Blender 活体。

### [R4-P1-03] 边界识别对非流形边不稳，且 BMesh index 应显式刷新

**代码**：<code>src/dressing.py:1144–1201、1333–1338</code>。

<code>keep_edge = {k for k, n in outside_users.items() if edge_use[k] == 1}</code>；如果一条非流形边被**两张选中面 + 一张未选中面**共用，则 <code>edge_use[k]==2</code>，代码仍会在这条边生成中点，重新出现 T-junction。PMX 有重复面、装饰、贴片时不是完全可以忽略的输入。至少预先报告非流形拓扑：对任意有 outside_users 的边，一律不拆；或者拒绝拓扑异常输入。

另外 <code>BMVert.index</code> / <code>BMFace.index</code> 在 BMesh 修改前后可能 dirty；现有 <code>ensure_lookup_table()</code> 用于可按序索引，不等于 <code>index_update()</code> 的保证。建议从 <code>bm.from_mesh</code> 后立刻 <code>bm.verts.index_update()</code>、<code>bm.faces.index_update()</code>，新顶点尽量保存 BMVert 引用而非依赖 <code>len(bm.verts)-1</code> 形成“临时索引”。当前没有直接证明这一点在 Blender 5.2 上触发错误，但用于长期自动化值得加契约测试。

**结论**：这轮的拓扑方向值得保留，**不用推倒重写细分函数**；修中心 UV、加非流形/属性守卫，并把可复核测试移入仓库的 <code>tests/</code> 或 <code>scripts/tests/</code>，是最小成本收口。

---

## 3. P0/P1 — <code>project_layer_on_limb()</code> 混合权重和“外来骨”判断

### [R4-P0-04] <code>body_bones</code> 不等于所有目标身体骨

**相关代码**：
- <code>src/dressing.py:1575–1604</code>；
- <code>src/dressing.py:451–578</code>；
- 调用处 <code>run()</code> 的 <code>body_bones = set(rig_map["mapping"].keys())</code>（使用来源→目标骨映射键）与 <code>project_layer_on_limb(..., body_bones=body_bones)</code>。

现有筛选：

~~~python
for g in layer_vertex_groups:
    if g.name in body_bones:
        continue
    if g.name in target_armature.bones:
        garment_bones.add(g.name)  # 任意一次命中 -> 整个层不转权重
    else:
        pseudo.add(g.name)
~~~

这修正了 mmd_tools 两个伪组的问题，但定义仍不严谨：**目标素体 B 真正用于膝/踝蒙皮的辅助骨，可能存在于 B 的骨架和 B 的顶点权重中，却不在来源↔目标 rig_map 的键集合里**。例如目标的 足D、ひざD 或新增 B 辅助骨；它们会被误判成“服装专用骨”。

而且只要任一层顶点检测到一个这样的组，就全层 <code>target_weights="skipped"</code>：这不是每个顶点独立决定，可能吞掉整个贴皮层的预期功能。

**建议更稳定的三集合分类**：

~~~python
target_skin_bones = {
    name for name in target_body.vertex_groups
    if name in target_armature.data.bones
    and any_target_skin_vertex_has_positive_weight(name)
}
true_garment_bones = explicitly_transferred_source_garment_bone_names
pseudo_or_metadata = all_groups - set(target_armature.data.bones)
# 伪组不能简单合并成“无效”，因为 mmd_vertex_order 有自身语义
~~~

不要只使用 <code>arm_bones</code> 是否存在来判断“是否服装骨”；更不要把“rig_map 映射键之外”直接当外来骨。来源和目标同名的服装骨，还需要用迁移清单的语义判断。

最小自检：打印 <code>classification_summary</code>，包括 skin_bones、garment_bones、pseudo、unknown，各类覆盖顶点数和导致整层跳过的真实骨名。出现**一个混合绑定顶点**不应自动终止所有其余 4000 个贴皮顶点的转移。

### [R4-P0-05] blend=1 的 <code>transfer_target_weights</code> 可能把合法目标骨权重丢掉

**代码**：<code>src/dressing.py:511–562</code>，尤其 539–552。

在 <code>project_layer_on_limb()</code> 中一旦确认可转，调用：

~~~python
transfer_target_weights(
    garment, tgt_body, body_bones, tightness,
    blend=1.0, max_dist=0.05, domains=False, keep_groups=pseudo
)
~~~

<code>transfer_target_weights()</code> 对目标权重 <code>blended</code> **只保留名字在 body_bones 内的骨**。如果目标素体的局部真实 skin weights 大部分在不属于 rig_map.keys() 的 B 辅助骨，而某个袜顶点 t=1，来源身体骨权重乘 (1−t)=0；目标 B 辅助骨又被过滤，可能得到：
- 归一化后错误地把剩余极小的骨权重扩大到 1，导致膝/踝变形异常；
- 或 <code>total=0</code>，顶点没有有效蒙皮骨；伪组存在也不代表有骨骼绑定。

这在静态穿模数上可能**完全看不出来**；对目标 VMD 的膝盖、踮脚动作可能是显著回归。

**最小修复策略**：
1. 目标插值得到的 weight map 中，所有**在目标骨架存在并且确实驱动目标皮肤的骨**应视为合法 target skin influence；不能只认 <code>body_bones</code> 映射键。
2. 对贴皮层且没有真正 source garment 专用骨的顶点，直接替换**真实骨骼权重**为 B 最近对应三角面的完整插值权重（不混入伪组）；对于还绑有衣服骨的顶点，保留其语义并做局部有界混合/分区，不要整层跳过。
3. 重建权重前后分别检查：每顶点 real-bone weight sum、归一化误差、零骨权重点、非法目标骨、最多影响骨数/PMX BDEF/SDEF 导出约束，尤其**膝盖 ±5 cm 带与脚踝邻近环**。
4. 报告必须给出 <code>vertices_selected</code>、<code>vertices_reweighted</code>、<code>vertices_no_nearest_face</code>、<code>vertices_no_real_bone</code> 和 <code>skipped_reason</code>；不能只看有没有返回 <code>target_weights</code> 字段。

**建议专门测三类样例**：B 权重全在映射内；B 皮肤含目标专属辅助骨；一个袜口顶点还含真正服装专用骨。核对动作后的蒙皮轨迹与 B 对应皮肤点的相对距离，而不是只测 rest pose 权重和为 1。

### [R4-P1-06] 膝带混合的几何点不一定在目标皮肤外

**代码**：<code>src/dressing.py:1449–1471、1528–1556</code>。

smoothstep 权重让 **kw 连续**，但当前是先分别沿股骨轴、胫骨轴射线计算两个 3D hit，再：

~~~python
target = ((1 - kw) * thigh_surface_hit + kw * shin_surface_hit)
~~~

即使两处 hit 都落在 B 的皮肤外 4 mm，**其连线可能穿进弯曲的膝盖/小腿皮肤内部**。线性插值保连续，不保证保持到体表的 signed clearance。也有一个 ray miss 时权重自动重标的问题：某一侧 hit 消失，kw 连续却可能突然换到另一侧的 100% 目标点，仍会出现折痕。

推荐：先插值得到候选 target，之后**再做一次目标皮肤局部 BVH/法线方向投影并求 signed clearance**；必要时向外恢复 margin，限制相邻面法线变化；连续的 centerline frame 是更稳的长期方案。报告膝带 <code>min_clearance</code>、<code>max_curvature_jump</code>、<code>ray_miss_count</code>，比只有 max_displacement=13–17 mm 更能证明“没有堆叠”。

### [R4-P1-07] 局部/世界空间混用仍存在

**代码**：<code>src/dressing.py:1412–1436、1458–1471、1528–1551</code>。

- 目标 BVH 用 <code>tgt_body.data.vertices[i].co</code>（目标物体 local）。
- 骨骼的 head/tail 乘 <code>tgt_arm.matrix_world</code>（world）。
- 投射输入和写回使用 <code>garment.data.vertices[i].co</code>（衣服 local）。
- <code>knee_weight(v.co.z)</code>（衣服 local）与 <code>knee_z</code>（world）比较。

当前模型如果所有对象的矩阵均近乎 identity，会“碰巧正确”；这不是通用的 Blender 工程不变量。若不同 import scale、armature parent 或整体位置发生变化，贴合会偏离。

最低成本回归：整体**只平移模型、旋转 Z 90°**，输出贴合后的目标腿局部位置应与原输入一致。修法统一在 world space 建 BVH、轴、射线、位移，最后转换回 garment local；normal 在非均匀 scale 下用 inverse-transpose 处理。此项并非 b56f6df 新引入，却是本轮新算法能否通用的主要边界。

---

## 4. 物理 / QA：认可的修复与需要谨慎的地方

### [R4-P1-08] contact matrix 的公式修复正确，但 <code>near_differing</code> 目前会误报

**代码**：<code>src/physics_sim.py:145–203</code>。

逐对 <code>shared_pairs++</code> 并核验 <code>shared == expected - FN + FP</code> 是对的。但：

~~~python
if allowed and not shared:
    near_by_group.setdefault(key, []).append(1)  # 在 if near 之外
    if near: near_fn += 1
elif shared and not allowed:
    near_by_group.setdefault(key, []).append(0)  # 同样在 if near 之外
    if near: near_fp += 1
~~~

所以 <code>worst_group_pairs[*].near_differing</code> 其实等于该 group pair 的 **differing 全局数**，不是 12 cm 近场数。顶层 <code>near_false_positive</code> / <code>near_false_negative</code> 的判断在 if near 内，较可信；错误只在 group breakdown。

建议让 <code>near_by_group</code> 的 append 条件也在 if near 中；输出按近场错误数**重新排序**的 <code>worst_near_group_pairs</code>，不要拿全局 top10 伪装近场 top10。此外 12 cm 仅中心距离，体积很大的胶囊和裙摆刚体应按碰撞包围体的表面间隙/动态 swept AABB 重新确定风险集合。

### [R4-P1-09] Mode 0 follow 统计更诚实，但不能证明 point cache 干净

**代码**：<code>src/physics_sim.py:349–449</code>。

本轮 p95/mean/worst frame 报告是进步，但：
- 错误是 <code>scene.frame_set(f)</code> 后、**对当帧 Mode0 重设世界位置/写关键帧之前**算的，会混进 f−1/f 的求值相位；
- 使用原对象 <code>r.matrix_world</code> 而非确认的 evaluated 刚体位置；只测平移，不测旋转；
- 误差样本把所有 follow 刚体和所有帧揉成一个分布，某个关键大腿 collider 的异常可能被许多稳定刚体稀释；
- <code>first_frame</code> 不计；若没获得有效样本，全部统计返回 0，容易误认为 0 误差；
- setup 的两遍扫描中仍通过改 <code>point_cache.frame_start</code> 试图刷新，既没有“明确 free_cache”保证也不能解决**当帧求解后才写入当帧 key**的问题。

既然你决定采用 Blender 只做粗代理，建议暂时**不再为两遍扫描优化真实 PMX 拟真度**。但要将 <code>cache_reset_verified</code>、<code>mode0_phase_verified</code>、<code>feedback_bodies</code> 列为警告级/适用范围限制。若还想用它做跨版本比较，至少跑固定初始状态下的两进程重复性测试，保留核心碰撞体 f 与 f−1 的位置对照；不能用 p95 本身反证缓存正确。

### [R4-P1-10] 新增的分区候选数是进步，但“符号未定义=0”过强

**代码**：<code>src/qa.py:326–347</code>、<code>src/motion.py:250–305</code>。

<code>undefined_sign_by_region</code> 只在顶点索引**完全缺失**于 <code>rest_sign</code> 时计数。但真正的判定函数 <code>_pierce_count()</code> 只有在 <code>rest_sign[i] > 0.001</code> 且当前 <code>side < −0.001</code>、最近服装距离 <=6 mm 时才算命中。**rest_sign 存在但为 0、负值或过小的点实际上不能被此检测器判成穿出**，却被计算进“候选点”分母，且不会报告为 undefined。特别是同位贴皮/漆皮层，rest side 容易近零，脚区 1,316 点、命中 0 不能证明 1,316 点都做了有效符号翻转检测。

最少增加：

~~~text
region_total_sampled
region_reference_positive = count(rest_sign > 0.001)
region_reference_nonpositive
region_missing_reference
region_distance_le_6mm_at_each_frame
region_test_eligible_at_each_frame
region_signflip_hits
~~~

还要区分“累计各帧 hits”与“单帧候选数”：<code>pierced_by_region</code> 是跨帧相加，<code>candidates_by_region</code> 是静置时的一次采样分母，不应拿两者直接相除称之为穿模率。

**额外：这些新 denominator 只在普通 <code>motion_check</code> 分支出现，<code>physics_motion_check</code> 目前仍未返回 <code>candidates_by_region</code>/<code>undefined_sign_by_region</code>。** 如果报告统一展示两类 QA，应注明统计口径不同，不要把普通 QA 的候选数直接当物理 QA 的证据。

### [R4-P2-11] QA 的 UNKNOWN 退出码已修；还需要分别统计“视觉缺陷”和“几何缺陷”

<code>scripts/blender_runner.py:254–276</code> 现在把 UNKNOWN/FAILED 映射成非零退出码，符合要求；<code>qa.run_qa()</code> 区分 UNKNOWN 的方向正确。剩下的关键不是再优化总百分比，而是针对脚踝缝、露趾建立：

- 渲染可见面/材质 ID 的 pixel-level 漏出区域面积；
- 原始 B 完整皮肤真值 vs 被遮蔽 B 的差异；
- A 皮肤贴层/靴口的边界间隙（mm）；
- 靴子的实际包络（长度、脚掌宽、足背高、足趾最小 clearance）。

因为“皮肤被隐藏”可能让几何穿透指标更小，但不会自动使靴子拓扑或穿着轮廓正确。

---

## 5. final18 → final22：数据该如何解读

以下数据是仓库 <code>progress.md</code> 的**自报实测**，本 review 未重新跑。

| 指标 | final18 | final21 | final22 | 解读 |
| --- | ---: | ---: | ---: | --- |
| 普通 QA 最差帧 | 1.459% | 1.356% | **1.323%** | 相比 final18 下降 0.136 个百分点，约 −9.3% 相对变化；不是所有部位都改善 |
| 普通 QA 腿区累计命中 | 582 | 453 | **553** | 比 final18 少 29，但**比 final21 多 100**（约 +22.1%） |
| 普通 QA 腰区累计命中 | 4916 | 4732 | **4574** | 持续下降 |
| 普通 QA 躯干累计命中 | 664 | 763 | **756** | 比 final18 多 92（约 +13.9%） |
| 物理 proxy 最差帧 | 0.980% | 1.146% | **1.156%** | 比 final18 多 0.176 个百分点，不能说带物理 QA 改善 |
| 物理 proxy 腿区累计命中 | 92 | 92 | **77** | 当前采样下腿区下降，但需与动画抖动区分 |
| 物理 proxy 躯干累计命中 | 292 | 403 | **342** | 比 final18 多 50，比 final21 少 61 |

**结论**：普通 QA 的整体最差帧改善可报告，但腿区对 final21 有回归、躯干对 final18 有回归；带物理代理的峰值指标相对 final18 变差。既不能混合为“总体物理更好”，也不应凭一组 sample 断言成品更差。一次动作帧间 443～1036 命中的波动，提醒用相同**具体帧号**对齐比较；如果受物理混沌轨迹影响，增加独立冷启动复验、同动作片段的中位/P95、局部截图/几何 clearance，而不是只看 6 帧求和。

**关键观察**：当前最明显的两个视觉问题——脚踝缝与露趾——不能由上面的 sign-flip 总指标可靠覆盖。因此下一步的验收中心应转向局部证据，而非把全局 1.323% 再降 0.05 个百分点。

---

## 6. 下一步最值得做的三项实际功能工作

### A. 第一优先：脚踝局部缝隙（低成本、高确定性）

当前 <code>progress.md:61–69</code> 已纠正前提：**「腿」材质不是过膝袜，而是来源角色的小腿皮肤涂装**；所谓白边是 <code>__mmd_hidden__</code> 的目标皮肤在来源腿皮与靴口之间的缝隙区域显现。不要再按“单独布料袜口”处理它。

先回答**一个二分问题**：

1. **隐藏材质本应不可见，为什么能看到白色/测试绿色？** 如果 PMX export/reimport 的 <code>__mmd_hidden__</code> 透明度或渲染行为不正确，那么先修 material alpha / 透明显示。否则所有通过 body_mask 获得的“遮蔽”结果都可能是潜在 bug。用显示-only 分组渲染（B 原皮、B hidden、A 腿皮、靴口）分别输出 ID/alpha，记录 PMX 重导入后 <code>__mmd_hidden__</code> alpha、材质名、实际像素是否出现。不能只靠“看起来白”猜是孔洞。
2. **腿皮覆盖和靴口本身存在几何空带？** 如果隐藏材质完全透明但中间有空白，那么用边界 loop 查两组件最近 3D 距离和投影覆盖；明确是 A 腿皮下缘太高、靴筒上沿偏低，还是两者在不同截面完全错开。

**优先补一个 1～2 环的局部过渡皮带 / bridge patch**（来自 A 的腿皮、保留来源贴图/权重或局部绑定 B），让它埋到不透明靴筒内部适当深度；不要通过整体拉低 source 腿皮下缘，因为你已实测这样会造成尖刺。

若两组件不能拓扑相连，也可做受控 overlap：新环带沿脚踝表面贴合、在靴口内少量重叠，UV 在源腿皮最后一环连续外推，权重对齐目标踝。靴口原 UV/金饰不动。所有新增或修改只作用于踝部小 patch。

**证明成功的证据**：
- 静置、踮脚、跖屈/背屈、脚内外翻下，至少前、侧、45°、后侧视角，无绿色/白色 hidden 面可见像素、无背景孔洞，且没有新生边缘尖刺；
- 靴筒与腿皮 seam 的最大物理间距/实际覆盖率明确；
- 2 个独立 PMX reimport 渲染或同一 reimport 的可复现报告、模型 hash；不能只看 Blender 内工作文件；
- 不改变腰、躯干、左右脚的形状或碰撞组。

如果只是显示错误，通过修隐身材质解决；如果是几何空带，通过局部 bridge 解决；若两者兼有则分两项处理，不要一次性增加全身 mask。

### B. 第二优先：真正的鞋楦包络（先证明宽度差，再做实验）

你实测三条旧路线都失败，默认关闭是对的。不过：<code>fit_shoe_radius</code> capped at 1.3 只能证明**那次径向算法受限**，不自动证明 A 鞋与 B 前掌在**同一解剖截面**上真实宽度差 ≥30%；旧算法的参考集合曾混入膝/小腿、纵向 bin 也可能错位。

**鞋楦前诊断（比直接写变形代码更重要）**：

1. 按 L/R 单独标注目标脚的 heel、ball、toe_tip、instep、sole 平面；对 A 鞋标出 heel、vamp、toe cap、heel sole、金饰/鞋口。
2. 在同一**heel→ball→toe 归一化长度坐标**下测 max width（左右）、instep height（上下），写成 mm/mm 与 ratio 表和剖面截图。不要混淆“来源鞋外表面”与“真正鞋内表面”；单层漆皮没有容积时应测**目标脚的可见覆盖包络**，而非虚构鞋内壁。
3. 标注目标脚在 A 鞋壳**外侧可见的实际 3D 区域**，分辨“封口鞋头不足”“鞋面太窄”“源几何直接缺面”“纯粹目标皮肤透明遮蔽不正确”。
4. 只对鞋面/vamp/toe cap 选择**局部绝对宽高位移 / cage deform**，以目标脚包络 + clearance 为约束，沿 heel-ball-toe 设连续位移场；鞋底/高跟/金饰用 anchor 随动，禁止对金饰和靴筒执行全局 nearest-surface。
5. 若鞋面必须改变宽度但原 UV 会严重拉伸，可只在前掌局部加少量 edge-loop，并保持 A UV 连续；目标趾骨数量不代表必须把一双不透明封闭鞋细分成五根独立趾面。
6. 如果闭口不透明鞋的关键问题只有漏出目标脚趾，可以临时设置**局部 B 趾区严格透明遮蔽**，但这只标记为 visual fallback，不应把“几何鞋楦完全包住脚”判定成功。

**验收**：在鞋表面/目标脚剖面测得的最小包络间隙达到项目选定正 margin，脚趾可见像素 0，鞋帮无新裂缝，鞋底/跟/金饰不变形，动态五种踝/脚趾姿态下仍满足。若局部几何不可修复，报告“不兼容/需要更换鞋”是合理结论，但不能从旧算法 1.3 cap 直接推导“固有不可兼容”。

### C. 第三优先：让 QA 指标与真正可见缺陷对齐

**新增三个小工具比继续调整全身穿模率更划算**：

- <code>visible_hidden_material_pixels</code>：MMD/Blender PMX 重导入后，隐藏材质本应不可见的任何像素都要报警；
- <code>ankle_gap_report</code>：腿皮下环至靴口上环的局部距离、无遮挡面积、动态最大值；
- <code>toe_exposure_report</code>：目标趾区外露像素与覆盖率，并按 front/side/45° + 踮脚/脚趾动作记录。

这些指标应独立于衣服-身体 sign-flip 的 6 mm 阈值。为了不让“隐藏身体”刷低几何 QA，仍需保存固定 B 原始 mesh 作为几何 truth，并将渲染可见性单独统计。

---

## 7. 物理代理：现在先收口，不再扩大投入

本轮 <code>physics_sim</code> 的 mode 分布、feedback 数与 follow 误差统计是好方向。你已经选定 A（PMX filter 逻辑）+ B（Blender 粗物理回归），建议正式声明：

- **<code>translation_logically_valid</code>**：导入后 True=allowed 双向 pair matrix 按计划改变，非目标 pair 不变，PMX raw bit round-trip 无错误；这是可证明的。
- **<code>blender_proxy_runs</code>**：带物理的 VMD 求值有实际刚体运动，Mode0 轨迹误差与 Mode1/2 写回在项目容差内；另附全局与动态近场 FP/FN。
- **<code>blender_proxy_filter_equivalent</code>**：有非零 FP（你曾测得全局 8910），**False**；不把它写成 MMD 引擎效果。
- **<code>mmd_runtime_visual_validated</code>**：本机尚无法运行目标播放器，**Unknown**，不能写 True。
- **<code>visual_improvement</code>**：可以对 PMX reimport 的 Blender 渲染特定缺陷写“Blender 可见性改善”；不要扩大成“真实 MMD 视觉通过”。

若目标是每轮都可复现的 Blender proxy 基线，保留两次独立冷启动；对同一输入至少重复运行并比较**逐帧的关键 rigid transform hash、Mode0 offset、Mode1/2 轨迹误差**。仍存在 setup 两遍扫描 + point_cache.frame_start 热刷新这一尚未正式解决的内部不确定性；即使两个进程各自冷启动，单个 setup 内已经跑两遍，不能凭冷启动排除该问题。

但由于这批交付最大的肉眼缺陷是踝缝/露趾，**不推荐现在为了得到准确 MMD 同步物理而重写所有 handler**。保留明确适用范围，把工程资源移到局部几何与渲染质量。

---

## 8. 一次交给执行 Agent 的分阶段工作单

### R4-A：回归保真闸门（先做，最少改动）

- [ ] 修 fan center UV：每个来源面在所有 UV layer 使用一个固定中心 UV，并检查所有 fan 内边无 seam；补含 UV 岛、两层 UV、形态键、多 face-border 的测试 fixture。
- [ ] 验证真实 target skin bones vs 映射 keys 的区别；修正 transfer_target_weights 中会丢弃 B 辅助骨的过滤逻辑。混合服装骨时逐顶点决策，不准一个顶点让整层全部 skip。报告 0 骨/非法骨/归一化/PMX 影响骨数。
- [ ] 将 <code>work/test_subdivide3.py</code> 中真正可重现的 9 个检查迁入受版本控制的 test 脚本（若本地允许），补中心 UV/混合权重专项测试。
- [ ] 修 <code>physics_sim.contact_matrix_report</code> 的 <code>near_by_group</code> append 时机；保持 near-field 是“候选 pair”而不是“观测接触”的措辞。

### R4-B：踝缝最小可视修复（功能第一优先）

- [ ] PMX reimport 阶段对 <code>__mmd_hidden__</code> 透明度/材质 ID 开一轮专门检查，确认“看见的白/绿”是否实际 hidden 材质。
- [ ] 输出 A 腿皮片区下边缘、源靴筒上边缘和目标 B 脚踝周围的边界 loops / 有效覆盖距离。
- [ ] 只新增一条局部过渡带或材质遮蔽小范围修正；不拉整个袜子下环、不碰金饰鞋帮。分别静止+4 种足踝动作，前/侧/45°/后侧近景比较。
- [ ] 如通过，单独标记 <code>ankle_gap_visual_fixed</code>；原先 <code>visual_improvement</code> 整体仍不能跳到 MMD passed。

### R4-C：鞋楦 POC（最后做）

- [ ] 只测 A/B 对应 heel-ball-toe 的前掌宽、足背高和 toe cap 真实覆盖，不从旧 1.3 cap 猜出“宽 30%”。
- [ ] 语义分出鞋帮/鞋面/鞋头/鞋底/跟/金饰；对前掌鞋面一处做绝对位移 cage POC，保留 UV + 饰品 anchor。
- [ ] 固定头尾环、只调 width/roof，高亮自交/非流形/UV 拉伸；如果初次 POC 失败就返回诊断与不可修理由，不反复用失效径向倍率碰运气。

### R4-D：QA 证据输出

- [ ] 普通与物理 QA 都报 region_sampled / eligible_reference_positive / per-frame eligible / hits，不将“有 rest_sign 的点”一概视为有效测试点。
- [ ] 导出物料/区域 ID mask 和可见漏肤像素数，区分隐藏材质漏出与真正鞋面不足。
- [ ] 对 final18/final21/final22 用同一具体帧号和各部位相同采样分母比较，输出至少 3 个关键局部帧的几何/渲染差异；带物理结果保持 proxy 字样。
- [ ] 文档如实注明本机 MMD 播放器不可用，所有 MMD 运行时级别结论仍是 Unknown。

**范围约束**：这批不要重写整套 Blender 物理，不要用“多遮蔽/删更多 B 皮肤面”来刷低 QA，不要给封闭鞋强加 5 条脚趾独立几何，也不要继续推动全靴最近点贴肤。优先产出一个确实肉眼可验的踝部修复，以及能阻止新数据/纹理退化的代码测试。

---

## 9. 参考与真实性边界

**代码位置**（均对应 62ca5e5）：
- <code>src/dressing.py:1115–1340</code>：subdivide_triangles；
- <code>src/dressing.py:1343–1605</code>：project_layer_on_limb 与目标权重迁移；
- <code>src/dressing.py:451–578</code>：transfer_target_weights；
- <code>src/physics_sim.py:105–204、349–449</code>：contact matrix near-field 与逐帧误差；
- <code>src/qa.py:326–347、350–455、458–632</code>：普通 QA/物理 QA；
- <code>src/motion.py:250–305</code>：实际 6 mm sign-flip 判据；
- <code>progress.md:1–124</code>：final22 的自报指标和图像说明。

**证据限制**：无法用当前 GitHub 文本接口独立打开 docs/images 的 PNG，也无法读到 gitignored <code>work/test_subdivide3.py</code>；本报告对“9 项全绿”和“图片确实显示脚踝缝、露趾”只按项目已有证据陈述，不伪称逐像素审过。这里的 P0 UV 中心错误、near_by_group 条件错误、目标权重分类风险及候选点资格判据，均来自可见代码本身，具备明确反例或检查步骤。
