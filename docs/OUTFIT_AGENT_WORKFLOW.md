# 供其他 AI 模型使用的换衣流程

**最新用户复查：当前双手姿态不是握拳，优先处理服装与身体穿模。2026-10-27 本轮候选均未通过，不得将 `outputs/contact_stack/outfit_body_contact_v1/` 中的新 Blend 当作修复成品。** 见 [服装／身体接触失败记录](OUTFIT_BODY_CONTACT_2026-10-27.md)。服装审计现在必须包含混合骨权重边界、整片埋入以及鞋袜交叉，不能只读取身体区域或零交线结果。以下旧版本的通过范围只适用于各自原动作和缓存。

15 秒舞蹈衣服起皱的修复版见 [保形布料修复](STRUCTURED_CLOTH_REPAIR_2026-10-27.md)，输出 `outputs/cynical_cloth15/structured_v2/`。统一附着骨、按结构保形，并保留实际网格解算；工程含 46 帧预热，成片区间 47–496。不要再把旧 `trial3` 的自由布料分区当作当前推荐设置。

先读 [实际踩坑记录](KNOWN_PITFALLS_2026-10-26.md)。用户新指出的两腿间片状物已在 `outputs/cynical_cloth15/clean_model/Keqing_PlateRemoved.blend` 修复；`hosiery_cleanup.clean` 排除袜层内部小岛并断开旧补裆片，不改变身体、脚和形态键坐标。旧 `review_ready` 只保留为对照，不再当最新修复输入。

丝袜与袖子的最新原生修复入口见 [完整丝袜与袖子记录](STOCKINGS_SLEEVES_2026-10-26.md)。查看 `outputs/stockings_sleeves/review_ready/` 的工程及 `acceptance.json`；保留当前头部比例与 White Bridal 足袜结果。该版包含 Blender 运行时几何节点，不能用旧的 PMX 验收结论代替，也不能将旧补鞋脚本的尾部顶点索引直接套到新 `Stockings` 对象。

> 当前版本 0.9：新增默认关闭的试验袖口物理生成，继承臂轴修正、闭口硬鞋锁定、可选平地接地动作和手套覆盖。拒绝 v0.2 的 `anatomical_foot_last` 配置。闭口鞋和手套覆盖模式不支持自动脱除/透明度淡出；半透明衣料保留皮肤。

本流程把几何操作封装在 Blender 插件内。调用者负责提供文件、核对配置与检查输出图片，无须临时生成网格变形脚本。

White Bridal 外部 Blend 鞋的最新专用流程及修复版在 [White Bridal 记录](WHITE_BRIDAL_SHOES_2026-10-26.md)。使用 `outputs/white_bridal_shoes/checked/`，旧 `final/` 鞋内接触未通过。新增 `shoe_contact.py` 处理明确选择的鞋内衬与完整脚/袜层，多角度脚本每脚 12 方向并支持动作接触采样。鞋型边长和地面高度通过不能代替脚/袜/鞋三角面交线检查；28 帧通过也不等于全帧或动力学通过。该流程未集成到 0.9 ZIP，其他模型不能直接套用本机专用的足袜对应索引和材质规则。

刻晴完整头部替换见 [换头记录](KEQING_HEAD_SWAP_2026-10-26.md)，入口为 `scripts/fit_keqing_head.py`，最新比例修正版 `outputs/keqing_head/proportions_v2/`，显式使用 `--scale 0.94 --head-lift 0.018`。首版 `final/` 保留对照，不能只按脸宽决定整体头部比例。固定流程负责颈口裁切与桥接、眼骨引用、原生 68 个表情、头发物理迁移和颈部渐变材质；使用 `review_head_swap.py` 和 `review_keqing_head_pmx.py` 分别检查原生工程与导出 PMX。不要只导入重叠的头网格，也不要用领口遮挡代替颈口和透明纹理检查。换头后保留原身体和衣服的有效表情；源骨架内部 ID 不能直接复制到目标骨架。该入口同样尚未打包到 0.9 ZIP。

## 固定调用

在工程目录使用普通 Python 运行，Blender 可执行文件须已安装 MMD Tools：

```powershell
python scripts/outfit_cli.py --blender '<blender.exe>' --action inspect --source '<来源.pmx>' --target '<素体.pmx>' --preset keqing_daniya --output-root '<任务输出目录>'
```

`keqing_daniya` 只用于本机已验证的刻晴/达妮娅模型对。其他模型先用 `conservative`，按实际材质与骨架核对配置，不能套用角色专用规则。

读取返回 JSON 的 `profile` 路径，检查 selected_materials、target_exclude_materials、clearance_rules、surface_patches、shoe_fit 和 arm_rest。保留 PMX 校验和绑定；不要把其他输入文件路径直接替换进已有 profile。

```powershell
python scripts/outfit_cli.py --blender '<blender.exe>' --action fit --profile '<返回的profile.json>' --motion '<测试动作.vmd>' --output-root '<任务输出目录>'
```

动作可省略，此时回执会明确标为未检查。所有任务另建目录，原模型不被覆盖。后台 API 也支持 submit/poll/cancel；同步调用用 jobs.run，避免调用者遗漏超时处理。

对这套刻晴/达妮娅模型，可选择在 fit 命令增加 `--cuff-physics`，或请求中传 `cuff_physics=true`，生成试验袖口物理。默认关闭；需要新预检得到的 `arm_rest.method=anatomical_upper_arm` 和启用物理迁移。插件负责识别袖片、建立 16 骨/16 刚体/32 关节及平滑权重，调用者不需要自行操作骨骼。读取 `adaptations.cuff_physics` 和 `validation.cuff_physics`；静态预览和普通 VMD QA 不显示动态避让，仍须连续运行物理后看图，不能因为 helper 验证通过就宣布穿模解决。飘带未新增解算方法，重复生成须从原始输入重新 fit。

闭口硬鞋需要修正平地穿地时，在上面的 fit 命令加 --ground-motion，JSON/API 传 ground_motion=true，面板勾选“另存鞋底接地动作”。要求提供 VMD、静止的顶层全ての親轨道和保形闭口鞋。读取回执 effective_motion 与 grounding_report，使用新模型时加载 effective_motion；原动作不覆盖。grounding_report 包含完整帧范围、基线最低点、最大抬高、重导入验证帧数和验证最低点。只移动全身根骨，不改鞋形或腿姿；不处理斜坡、脚滑、腿姿重定向或已有动画的根骨，超出条件明确失败。

## 必须读取的输出

1. result.json：state、ok、accepted、warnings、images、pmx、blend。
2. validation.json：未知骨、无权重顶点、异常权重、物理引用与缺失贴图。
3. preview/：四个全身视角与六张细节图，逐张检查胸口、袖口、双手、袜口与鞋头。
4. adaptation_report.json：实际重建面数、UV 采样距离、整鞋变换、原鞋边长比例误差和鞋内脚面遮蔽数量；隐藏备份只保存在 Blend，原 PMX 不变。
5. model/manifest.json 与 motion/qa_report.json：完整参数、物理迁移警告与动作抽样结果。

0.4 的 patch.seams 记录 UV 拆分位置共享位移的数量及原先可能张开的距离；uv_domain_fallback_faces 记录缺少对应手指/手掌来源时的纹理回退面数。physics.joints_unrelated 是不属于所选服装、正常不迁移的来源关节，不能当作服装丢失；真正缺端点记录在 joints_skipped 和 missing_joint_endpoints。

动作报告包含 motion_deformation。身体穿出比例较低时，仍可能出现父骨丢失导致的长条网格；新检查会将严重拉伸判为 FAILED。可用 `scripts/outfit_motion_preview.py --job <任务目录> --frame <帧号>` 在 Blender 后台渲染指定帧的四个全身视角，复核问题姿态；这不运行物理模拟。

0.5 动作报告增加 visibility_filter 与 raw_geometry：前者说明排除了哪些可确认透明的衣料面，后者保留同帧未过滤计数与各自静态参考。未知着色器和受 UV 形态键影响的面继续保留，模型几何不删除；拉伸检查仍覆盖全部衣料。过滤后的 max_ratio 可以更高，它仍是定位候选点的信号，不能当作可见穿模的证明。源码辅助命令 `scripts/outfit_contact_review.py --job <任务目录> --out <新诊断目录>` 可独立复查，`outfit_region_review.py` 支持 --out、--frames 和 --no-render。

0.6 的手部 surface_patches.covered_skin 可设 opaque_backup。刻晴预设会为完全不透明且与手套一一对应的皮肤面建立隐藏备份，再从穿衣 PMX 移出这些重复面；丝袜和未知/半透明区域保留皮肤。读取 adaptations.patches[].skin_coverage 和动作报告顶层 skin_coverage，确认 masked_skin_faces、backup_object 及采样范围说明。覆面后的穿模比例和未覆面版本不能等同比较，移出的点并未通过穿模检查。恢复时将 covered_skin 设为 retain，从原始输入重新 fit；Blend 中也保存了原皮肤 UV、权重、形态键与索引，但它不是可直接导出的换装开关。

0.7 的 adaptations.shoes.vertex_morph_lock 记录鞋顶点清除的形态键位移；validation.preserved_shoes 检查重导入后的全部顶点形态键都不会改变硬鞋。reference_positions 提供保形坐标依据，不仅凭踝骨权重猜测哪些顶点是鞋。普通衣料动作 QA 仍抽样 24 帧；启用接地时另有整段逐帧的鞋底高度验证，两者覆盖范围不要混淆。

0.8 新生成的刻晴预设含 arm_rest.method=anatomical_upper_arm。同侧上臂、扭转辅助骨和袖链共享真实肩至肘方向的刚性静止变换，避免将辅助骨任意的显示方向解释为袖片转向。adaptations.arm_rest 记录涉及骨骼、变换矩阵和原先的朝向/锚点差异；目标已有骨架、衣服尺寸与权重不改。缺少此字段的旧配置沿用原行为，升级后应重新 inspect。此规则改善肩部袖片翻折，不处理弯肘后的前臂穿袖；继续检查袖口和飘带图。

手部 isolated 图片是有开放切口的隔离诊断图，可能从手腕看到内部表面。结合同帧 hand_L / hand_R 完整模型特写判断，不能只看隔离切面就断言真实露肤。`scripts/outfit_cover_review.py --job <任务目录> --out <新目录>` 可与原素体核对备份。

对于启用 `preserved_closed_shoe` 且提供 VMD 的任务，可在 Blender 后台执行 `scripts/shoe_motion_review.py --job <任务目录>`（`--python` 后的脚本参数需放在 `--` 后）。读取 `shoe_review/report.json` 并查看四个静态视角及第 1、121、256 帧动作图。报告检查原鞋形状、单骨权重与脚部备份，逐帧最低 Z 值用于识别踩地误差；不能只看刚体拟合误差就宣布鞋子验收通过。0.3 本机记录仍有约 4.77 mm 的动作踩地误差，见 `OUTFIT_SHOES_V03_2026-10-23.md`。

`ok=true` 和退出码 0 表示任务及结构检查完成。`REVIEW_REQUIRED` / `accepted=false` 保留人工视觉验收要求；不能改写为“已经零穿模”。若 FAILED，先读 error.code/message/stage 及 blender.log，修正对应输入后新建任务重跑。

## 可复用的调整入口

| 观察到的问题 | 配置入口与限制 |
|---|---|
| 胸衣层互相穿插 | 使用 radial_order 保持径向层顺序；不要退回逐顶点吸附后仅追求间隙为零。 |
| 指甲露在手套外 | include_skin_materials 包含目标指甲材质；不透明贴肤手套可用 opaque_backup 仅覆盖一一对应且经不透明检查的面，保留完整备份。半透明手套仍保留皮肤，不整体删除身体。 |
| 手腕接缝露出 | 检查 wrist_overlap、目标手部权重及袖口形状；扩大覆盖后重新看手腕特写。 |
| 肩饰/袖片翻折，辅助骨显示轴不同 | 刻晴预设重新 inspect，检查 arm_rest 的解剖臂轴变换；不要把辅助骨尾端方向当作肢体方向。弯肘碰撞仍需另查。 |
| 弯肘宽袖需要物理自由度 | 可试用 cuff_physics=true 自动生成袖口物理，再连续解算看图。默认关闭；本机四帧对照中第 121 帧指标退化，不宣称全动作改善。静态预览不显示碰撞响应。 |
| 袜口与鞋帮之间留缝 | 检查腿部 lower_offset；UV 与边界按目标网格重建，不能只凭全身缩略图判断。 |
| 闭口尖头鞋露趾 | 使用 preserved_closed_shoe 的整鞋变换与鞋口遮蔽，检查四面特写；不得拉宽鞋头、抬高鞋面或拉长鞋饰。开口鞋必须另做脚姿和绑定适配。 |
| 动作穿插 | 读取具体帧和部位；VMD 抽样检查不包含真实 MMD 动力学，也不是全动作穷举。 |

同一输入与配置可以重复提交；每次输出保留独立回执，便于比较。当前仅验证了这一套模型对，其他服装和体型仍需单独验证。

2026-10-26 的 White Bridal 外部 Blend 鞋子采用单独的资产专用脚本：恢复完整脚部、调整高跟姿态、延伸丝袜、限制穿硬鞋时的脚趾独立运动。调用顺序、参数和验证范围见 [White Bridal 记录](WHITE_BRIDAL_SHOES_2026-10-26.md)。该入口尚未纳入 0.9 面板，不能把 Blend 路径直接当成旧 API 的来源 PMX。

## 物理复查

可在 Blender 后台运行 `scripts/outfit_physics_review.py --job <fit任务目录> --last-frame 121`。该诊断连续从第 1 帧步进，使用已安装 MMD Tools 的 build_rig，输出 physics_review/report.json 和最后一帧四视图。检查 no_motion、deformation、碰撞矩阵差异以及 Blender 日志中的 dependency cycle；不能仅凭 PMX 导出成功或最后一帧好看宣布物理通过。旧 setup_legacy_proxy 的层近似与直接写骨骼方案已退出 QA，不作为验收依据。

使用 --out <新目录> 保留既有版本的物理数据。0.5 完整生成排除约束，检查静态全部刚体对以及动作附近的过滤差异；构建完成后移除残留静音骨架关系并使用物理构建前记录的模式 0 轨迹。查看 PHYSICS_SETUP_READY 之后是否还有循环，不要把构建阶段临时警告当作运行结果。读取 setup.kinematic_bake.feedback_bones 和 limitation：这类次级物理反馈被省略，仍非原生 MMD 等价求解。诊断要求新导入、未 build_rig 的模型，不能对已运行的仿真再次烘焙。

MMD Tools 属性 collision_group_mask 中 True 表示“排除”，原始 PMX 文件位 True 表示“允许”，两者不要混用。0.4 修正迁移及诊断中的反向解释。Blender 诊断仍不是原生 MMD 运行时验收。
## 胸衣恢复补充入口（2026-10-27）

用户后来指出 13 秒袖子被压成薄片；最新修复工程改为 `outputs/cynical_cloth15/sleeve_stable/`。它使用原 CLOTH 加旋转、接缝、长度、面积和时间约束；通用核心在 `sleeve_shape_constraints.py` 和 `stable_sleeve_cloth.bind_clamped_frames`。`_install_experimental_solver` 仅保留为未采用的物理对照，不是成品修复入口。完整调用、测试、缓存依赖和限制见 [13 秒袖子修复](SLEEVE_13S_REPAIR_2026-10-27.md)。

已生成原生 1080p 试片工程 `outputs/cynical_cloth15/chest_hd/Cynical_Cloth_15s.blend`。胸口团皱须先区分基础版型挤压、蒙皮和真实布料；本轮不是仅改刚度。代码和实际数据见 [胸衣高清记录](CHEST_REPAIR_HD_2026-10-27.md)。

安装新快照 ZIP 后可调用 `mmd_outfit.chest_panel.restore(cloth, body, arm, faces, template)`。模板示例为成品目录的 `torso_template.json`，含原服装 UV 对应坐标、法线、仿射矩阵和明确面列表。调用时必须是对应模型的中立姿态，且衣服拓扑／UV／顶点编号与模板一致；不能把刻晴模板直接套在其他衣服上。新角色需要生成自身对应数据与分区，当前恢复脚本中的人体高度和骨名配方专用于本次模型。

渲染脚本 `scripts/render_cached_cloth15.py` 支持 `--width 1920 --height 1080 --step 1`，输出 30 fps 的 450 张原生帧；编码脚本核对每张 PNG 尺寸、帧数和音轨。不能通过放大旧 640×360 视频交付高清。

