# 头发视觉修订当前交接

> 2026-10-30 21:46 更新：下文材料弹簧分支已经停止并被视觉复查否决，不能续跑或视为交付。当前工作转到 `HANDOFF_MCP_MMD_BULLET_2026-10-30.md`。用户正在打游戏，要求使用 Blender MCP，不操作键鼠、不切换窗口。旧工程和数据均保留；严禁恢复自动关机。

最新用户反馈：旧视频约 11 秒头发有穿模观感，头发梆硬。目标仍为完整角色、原柔光材质、地库、固定全身、指定动作与 Shikako 音乐的 1080p / 30fps / 450 帧 / 15 秒正常成片。

旧 `fullhair_repro_20261030/FINAL_REPRO15` 保留，但已标记视觉复查否决，不能沿用它的完成结论。第一次自由弹簧试验 `fullhair_flexible_20261030/pd_inextensible_pilot` 在约 11 秒有局部卷发压皱，已停止并保留；即使几何交线为零也不交付该试验。

## 当前版本

根目录 `E:/project/mmd/work/headswap_xl_codex/fullhair_material_20261030/`，交付候选 `DELIVER_MATERIAL15/`，物理输出 `run/`，输入沿用 `fullhair_repro_20261030/input_body_aware/`。代码为 `tools/contact_stack/mmd_hair_dynamics_material/`；不修改旧版求解器。指纹 `38f4bbf513bde3154406b3eb63caec240eff18c137719372f9234f345bf6a44e`。

旋转不变弹性距离弹簧、动态邻发支撑、2.5 cm 范围局部材料支撑边、强度 1000 的柔性形状恢复、重力、惯性与阻尼。结构刚度 1e9，弯曲 30000，局部支撑 1e8，每步 8 次局部／全局迭代。8994 真根不变，24207 头发顶点、40181 三角面完整。自由发梢约 3 mm 皮肤间距，近根平滑减小；实际皮肤接触及原边长约束不放宽。

前缀 1–13 帧已真实保存、试渲正常完整画面，发型保留。去除头部刚性运动后的自由段前缀变化 p95 约 13.45 mm，旧版约 0.047 mm；这只描述短段，不能替代 11 秒连续视觉复查。

## 正在进行与后续

先查宿主进程、`run/status.json`、`run/latest_state.json` 与日志，不能重复启动。

- `run_material_full_hair.py --resume --end-index 2872` 正在连续计算至帧 360（12 秒），日志 `through12s.log`。
- `follow_full_hair_publication.py` 将真实检查点发布到 `DELIVER_MATERIAL15/cache/full_head.pc2`，日志 `follow.log`。没有发布的尾部不可渲染。
- `audit_full_hair_showcase.py --first 1 --last 450 --step .125 --wait-for-publication` 正在独立核验全部 3593 个最终 Blender 采样，日志 `native_audit.log`。
- `render_material_hair_review_when_ready.py` 等物理解算真实保存到 12 秒并退出，再顺序 GPU 渲染 `keyframes_11s/` 的 326/331/336 三帧和 `preview11s/` 的 301–360 连续正常画面。避免 GPU 解算和 GPU 试渲同时运行，曾出现严重资源阻塞。
- `source_preservation.json` 已通过：原网格、权重、231 形态键、原动作、保护段均保留。

收到 `review_ready.json` 后，查看三帧原生画面与连续短片；不能只看零交线。满意后从真实检查点续算至 3592（450 帧），等发布完成。再做原始 SurfaceClass 面直接检查 11 秒，以及关键帧完整包含检查；运行 `check_material_hair_checkpoint_replay.py` 记录严格数值重放与接触／应变是否仍通过，差异如实保留。

完成解算后冻结新 .blend 元数据与相对缓存；全部帧用新缓存重新渲染，不能混入旧版图像。使用 `encode_full_hair_showcase.py` 合音乐并全解码验证。用 `build_material_hair_repro_bundle.py` 打包准确版本源码、参数、绑定和初态，更新最终报告及本文状态。

细节与复现步骤见 `FULL_HEAD_FLEXIBLE_MMD15_2026-10-30.md`。当前尚未交付修订后的完整 15 秒成片，不可声称完成。整头发片自碰与连续 CCD 未被证明；原身体髋部、腕部和保护接触仍有残余。服装暂停，原始工程和数据保留，严禁设置关机。
