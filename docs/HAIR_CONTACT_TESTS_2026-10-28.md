# 头发穿模测试：2026-10-28

**本轮未修好整段头发，状态 HAIR_UNRESOLVED。** 完成了可重复检测、低应变投影初态、物理接线修复与有效的 15 秒 Bullet 对照。原模型、原 1080p 成片和身体候选未覆盖。

产物根目录：`E:/project/mmd/work/headswap_xl_codex/contact_repair_20261028/hair_tests_v2/`。总回执 `acceptance.json`，48 张原生 1920×1080 正／斜／侧／背画面在 `review1080_verified/`。蓝色为头发，橙色为真实交线所在发三角形。交线对数不是独立穿模事件数；开口分区包含检测不完备，采样不是 CCD。

## 先纠正旧物理结论

原拼接工程保留 185 个 `RigidBody` 属性，却没有 `rigidbody_world.collection`；MMD Build 没有自动补齐成员。因此旧 `native_hair_probe/` 及本轮世界修复前的 `mmd_*` 对照并未真正运行 Bullet，旧的纯物理／混合模式优劣结论作废。旧数据不删除，总回执逐项列出无效目录；其几何异常可作为诊断，不能作为有效动力学证据。直接基于最终网格的发骨优化不受此问题影响。

`physics_world.ensure_world_members` 现补齐刚体和约束成员；本模型重新加入 185 个刚体、107 个漏失约束，最终世界约束 11,116 个。独立无 MMD 落球测试通过：修复空世界后，球从 1m 落到地面上约 0.100004m，见 `outputs/physics_world_contract/report.json`。

另修复过滤错误：本机 MMD Tools 的 `non_collision_distance_scale=0` 会跳过大多数非碰撞约束。显式排除、固定首段和前发后，本次核对到实际 9,630／9,630 对所需发骨非碰撞约束。并非以关闭头发／身体碰撞来修穿模；本实验没有启用头发自碰。

## 实际结果

| 方法 | 实测 | 结论 |
|---|---|---|
| 低应变发骨投影初态 | 首帧头发／身体三角交线 442→0；有效边长约 0.939–1.078 倍，身体不动；头皮交线仍保留 | 仅身体初态改善 |
| 低应变投影＋有限手臂反馈 | 35 个姿势中 12 个目标交线为零，21 个满足边比 0.9–1.1；第 240 帧仍 366 对身体交线，前发被推出尖片 | 未通过 |
| 有效 Bullet：混合模式、合法初态、首段／前发固定 | 107 动态＋37 固定发刚体＋41 身体代理，连续 450 帧；第 240 帧完整重查有 1,819 对身体交线，第 450 帧有效边长最大 3.49 倍、P99 1.249 | 未通过 |
| 同上＋独立真实身体表面碰撞网格 | 25,365 顶点、47,150 三角形；PC2 对源皮肤误差 0，无发骨依赖环；第 240 帧完整重查仍 1,818 对身体交线，第 450 帧边比最大 3.26、P99 1.252 | 未通过 |
| 官方原生 XPBD 发片 | 焊接 UV 缝后 20,507 模拟点；世界空间固定点漂移，头局部空间可稳定固定点但仍严重拉伸 | 未通过，未默认启用 |

Bullet 两个有效实验的所有审查采样中，身体皮肤坐标差为 0。代理发胶囊不足以约束整张发片的宽度和混合权重区域，简单增加身体网格碰撞也没有解决问题。第 240 帧前发卷到肩颈附近、第 450 帧后发卷起，均已原生多角度查看。不能把这些候选替换成正式成片。

NLA 候选：`continuation_witness_15/HairContact_ContinuationCandidate.blend`，层重建误差约 1.43μm，主骨矩阵差 0，抱手保护段真实皮肤差约 0.596μm。它是未验收实验，35 个姿势不是整段检测。Bullet 文件 `mmd_world_verified/NativeHair_LiveProbe_NotAccepted.blend` 与 `mmd_world_surface/NativeHair_LiveProbe_NotAccepted.blend` **未持久烘焙缓存**，重新打开不能乱序拖帧复现；关键帧真实坐标另存 `keypose*.npz`，画面由它们生成。

## 算法与可迁移入口

插件 `dist/animation_contact_tools-0.1.1.zip`，技能 `dist/repair-animation-contact-skill.zip`。插件不包含第三方模型。

- 实际三角交线见证点与最近表面法线约束，结合相对边长损失，受限旋转发骨；可选最多 15° 的手臂反馈，保留头／躯干／脚和抱手保护窗口。
- 对普通 LBS 建立解析蒙皮雅可比；实际 Blender 前向和有限差分验证后才使用。不支持的 DQ／骨约束链需要另适配。
- 全程独立 NLA 层，不改源网格；逐帧 JSONL 保存姿态，防止结尾失败丢失全部计算。现恢复源未动画发骨的原旋转，不强制为单位旋转。
- `--mode hair-experiment` 使用显式 `hair_collision_targets`，可接续已有身体 NLA 层。默认不允许手臂反馈；须按新骨架配置。
- 实验入口固定回执 `HAIR_UNRESOLVED_EXPERIMENT`，CLI 退出码 2；不会因少数姿势为零而称整段头发通过。

独立 ZIP 解包运行 1–2 帧已通过，两个姿势的目标交线为 0、最长有效边约 1.076 倍，仍按预期返回未验收。普通身体英文骨架／厘米单位回归通过；新英文两段发骨模型在米和厘米下，解析前向最大误差 0.409μm、导数差最大 0.000593m/rad，见 `outputs/portable_hair_jacobian/report.json`。这些证明接口适配，不是通用无穿模保证。

## B 站实际内容

已使用用户的 `E:/project/bilibili` 搜索项目，8 个方向扩词得到 51 个唯一候选，读取 4 个视频实际字幕／OCR。本轮搜索工具可用，无须修改搜索项目。证据和转写在 `outputs/bilibili_hair_research_20261028/`。

| 视频与来源 | 读取到的内容与采用范围 |
|---|---|
| [BV1PZ421T7Yj，MiaoBox](https://www.bilibili.com/video/BV1PZ421T7Yj/?t=434)，平台字幕 | 01:02–01:50 初始帧启动；03:17–04:14 顺序模拟；05:03–05:15 改动作后重烘焙；06:40–07:48 头发问题，07:14 建议物理＋骨骼。已用于对照配置。 |
| [BV16eJBzGEGy](https://www.bilibili.com/video/BV16eJBzGEGy/?t=67)，OCR | 01:07–02:31 检查 Blender 实际碰撞层；04:01–04:19 让手不与裙碰撞的办法不符合本任务，不采用；后半段是 VMD 扭骨兼容处理，不能当头发避碰。 |
| [BV1Bi1HBTELx，KafeiMMD](https://www.bilibili.com/video/BV1Bi1HBTELx/)，平台字幕 | 00:02–01:04 MMD bridge 将已算物理导出 VMD，是烘焙／兼容流程，不是通用真实表面穿模修复。 |
| [BV1Fj411b77p，宇庭_特效师](https://www.bilibili.com/video/BV1Fj411b77p/?t=569)，平台字幕 | 09:29–09:46 Particle Instance 沿粒子路径变形发片，10:15–10:41 开 Particle Hair Dynamics。需要改建与映射，不能直接套到现有 PMX 发片。 |

外部底座：[Blender 官方 XPBD](https://developer.blender.org/docs/features/nodes/xpbd_solver/)、[XPBD-Hair](https://github.com/ysk424/xpbd-hair)。后者是 CURVES／CUDA／OptiX 路线，本例未安装实测，不能写成已有成品修复。

## 下一步具体路径

先隔离前发根部的头／发骨混合权重和连接片，逐条测试骨旋转对真实表面的影响；修正异常变形后重新得到合法初态。再约束整个发片宽度和弯曲，增加时间连续约束，检查手与发根无空间时是否需局部改动作。头皮附着点需精确标记，原有埋入与新穿越分开报告。不能全排除 head/hair_root，也不能仅按三角交线数量下降接受尖片。

普通身体仍有原先的保护段过渡与髋部失败，本轮未处理衣服、抱手重建或这些身体残留。
