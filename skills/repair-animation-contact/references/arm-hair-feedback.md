# 发根空间不足时，反馈到手臂动作

适用于软发束已能正常弯曲，但手掌／前臂挤进固定发根、仅靠发片避让会拉伸根部的情况。插件 0.1.3 提供可复用 Python 模块；此分支尚未接入通用 CLI／侧栏的一键流程，需按角色准备映射和烘焙包装器。不要把普通 `solve` 或 `hair-experiment` 当成此完整流程。

## 输入与选择

- 使用一条显式 `control_chains`，依次上臂、肘、腕；四元数旋转、普通直接变形骨、米制世界坐标。复杂约束控制器需适配。
- `parts` 来自 `surface.regions`。`profile.pairs` 保留该臂／手对头和身体的真实检测对，不用隐藏面减轻问题。
- `envelope` 含 `moving_regions`、`hand_region`、`anchor_bone`、`anchor_bind_matrix`（4×4 世界矩阵）、`guide`（绑定时世界坐标点）、`radii`（米）。当前规划器取前四点，代表固定根部附近的胶囊包络；包络需从实际发片建立，不能把整束当刚体。
- 时间段不能覆盖有意接触保护窗口。上下文 NLA 必须保留并在最终求值状态下读取，不能为方便清掉原栈。

`two_bone_contact_path.apply_two_bone_goal(arm, chain, target_world, preserve_wrist=1., swivel=0.)` 用解析双骨 IK 保持骨段长度和手腕世界朝向。它会明确恢复原局部 location／scale，防止矩阵分解的微小误差逐次积累。

`arm_detour_planner.plan_arm_detour(mesh, arm, profile, parts, envelope, frames, out, max_offset=.125, clearance=.008, max_correction_speed=None)`：在手腕笛卡尔偏移／肘平面旋转候选上，检查实际蒙皮身体交线、内部点、根部包络及关节偏移；保留 `candidate_layers.json`。这些默认距离来自一次人物试验，应随角色比例和动作要求配置。

`select_arm_route(layers, frames, max_correction_speed=None)` 可独立选择已测候选节点：先最小化峰值偏移速度，再最小化代价。速度指修正量的帧间差，不是手的总速度。显式速度上限不满足则失败，不自动放宽；未给上限也只表示返回候选，绝不表示动作自然。候选 JSON 为 `frames` 与逐帧 `layers`，每节点包含三维 `offset`、`swivel`、`cost`。

## 从节点到动画

1. `interpolate_waypoints(..., mode='pchip')` 提供端点斜率为零的单调分段插值。节点无碰撞并不保证连接路径无碰撞。
2. 在子帧重新执行 IK、测真实皮肤和包络。手腕朝向保持后仍可能有指尖蹭脸；可限角微调手腕，必须记录最终世界朝向误差，不能只看局部旋转角。
3. 把已测绝对姿态写到只覆盖该链和该时间段的 REPLACE NLA 层，原 Actions 不改；精确复测烘焙前后求值一致。若使用 COMBINE，必须检查原栈组合语义，不能只认为四元数差一定重现原结果。
4. 独立进程复查更密子帧，以及非受影响蒙皮、主骨、区间外和保护动作。骨权重后代决定实际影响范围，语义面标签不能替代这一检查。
5. 清掉旧物理结果，用新身体轨迹重新解算头发；原生曲线经过 `strand_binding` 映射回实际宽发片后再检验。
6. 保存缓存时，固定于头骨的发束优先用 `hair_position_cache.bind_position_cache(..., anchor_armature=arm, anchor_bone=name, anchor_matrices=sampled_world_matrices)`。输入仍是世界坐标，内部转为骨局部坐标，重放时应用精确的动画附着矩阵，避免世界空间线性插值让根部漂移。

## 验收与已知失败

2026-10-28 单束试验：第 200–250 帧共 201 个四分之一帧采样，实际发片交线 0；边长比 0.9486–1.0634，根部插值误差 <0.001mm。右臂独立八分之一帧复查无交线，原 Actions 摘要一致。手腕最大移动 **12.5cm**、世界朝向最大误差约 **1.77°**，动作改动并不小。身体修正只在 212–228 帧；保护抱手段保持原样。

该试验用 3mm 体素皮肤壳、6mm 接触余量，60 子步／200 次约束。更粗的外壳／更小余量曾在后续采样漏碰；参数不能保证其他角色通过。短段在 200 帧零速度初始化，无完整预滚，不代表整段动力学。

世界空间缓存即使整帧根部正确，帧间仍曾漂移约 1mm；骨局部缓存修好了这一工程误差，但不替代碰撞求解。深穿后的最近表面法线可能反向，局部雅可比陷入错误分支；`root_envelope_feedback.solve_root_feedback` 在本例失败，不能作为已成功的默认算法。

实际发片表面、边应变、附着误差、动作自然度分别报告。开口区域完全包含、采样间穿越、头发自碰、其他发束及完整时间线仍未证明。不得把本次局部采样通过写成完整系统验收。
