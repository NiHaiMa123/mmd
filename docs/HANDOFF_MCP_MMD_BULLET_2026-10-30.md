# MCP / MMD 兼容物理当前状态

> **最新用户方向（2026-10-31，优先于以下历史状态）**：用户要求研究 `E:/project/bilibili` 的 B站资料和夏安原工程，不用自行创造的物理/几何混合方法。旧 FINAL_MMD15 已生成但方法未获接受，保留归档，不能重复启动旧流水线。已在夏安原始工程发现 HairC1–HairC4 的 `jiggle_blend` 曲线，与现成 Jiggle Physics 插件源码吻合；20 根头发旋转均逐帧烘焙，ABC 属于外套/裙子。确切烘焙前全部参数尚不能还原。最新完整研究见 `RESEARCH_MMD_HAIR_PHYSICS_2026-10-31.md`。优先复现有来源的插件流程，服装暂停、抱手保护、禁关机继续有效。

> **2026-10-31 已完成新交付。** 最终为 `headless_bullet/FINAL_MMD15`，成片 `完整角色_MMD物理与发片避碰_1080p_15s_Shikako.mp4`，1080p/30fps/450帧/15秒带音乐，全段解码通过。新.blend、完整相对缓存、准确输入/源码/参数复刻包全部保存；最终源数据和保护段保持检查通过，原身体误差0。全部3593样本独立实际网格检查无交线/内部点，8时刻128614包含点复查也通过。最终MCP已打开新工程。父PID67124流程成功退出，禁止重复启动旧候选。详情与保留问题见 `DELIVERY_NORMAL_MMD15_2026-10-31.md` 及交付目录README。下文为历史过程快照，不能用它覆盖最终状态。

> **连续审阅已完成，渲染继续中**：`FINAL_MMD15/frames` 的301–360已渲染成2秒正常连续片。Agent实际看过原生301/311/321/326/331/336/338/344/345/350/355/357/360（含11.8秒原跳位时刻），无此前灰扁大翻片，发尾体积保留、肩前卷发与皮肤分离；缓存速度和法线连续性也已诊断，仍有接触侧发较急的运动，不能宣称全头自碰/CCD或所有快速变化都已解决。`agent_continuous_review.json` 已写PASS，明确为抽帧视觉+缓存诊断范围。既有父PID67124已继续GPU渲染余下1–300/361–450，不要重复启动。独立原生3593样本仍并行，日志native_part_a.log/native_part_b.log，实际头发24207点/40181面与真实皮肤50428面；目前无失败。最后还需全450渲染、合音乐及完整解码，不能提前宣称交付。

> **当前准确状态（取代下文旧快照）**：完整 `guard_component15` 已完成3593样本，1515/15213自由顶点（14个自由连通部件）整段参考回退，13698仍有25%成熟物理次级运动。但运动检查发现旧参考在11.8秒有47m/s子帧跳位，原生物理本身对应约0.58m/s，不能只交零穿插结果。旧 FINAL_BULLET15 / FINAL_SMOOTH15 仅候选，未交付。新增 `smooth_headless_hair_temporal.py` 按30fps>3m/s自动定位15个跳位部件，4Hz头部局部零相位滤波+12帧余弦包络，再做真实接触和边长投影；先接受已有效姿态，失效暖启动自动冷重试。自动投影失败时刻的平滑减弱配置为 `temporal_projection_episodes.json`，不是手填骨骼姿势。
>
> 最终缓存运行目录 **`headless_bullet/guard_temporal_final15`** 已完成3593样本；仅137部件未采用时间平滑，保留有效接触参考。逐30fps最大头部局部速度由约6.35降到4.28m/s（frame258，侧发受手臂接触），11秒附近最大约3.48m/s，仍需实际连续画面复查，不宣称全部跳变已数学解决。
>
> **当前实际交付目录 `headless_bullet/FINAL_MMD15`**，新干净 `.blend` 与完整PC2已保存，9个1080p32samples GPU关键帧1/211/256/300/321/326/331/336/450已全部看过：完整正常人物，肩前卷发有厚度/体积、与皮肤分离，无原灰色扁片；保护动作保留，原身体髋部/腕部残余仍在。已写 `agent_visual_review.json` PASS，仅关键帧范围，连续尚未批准。
>
> **正在运行**：通过MCP启动 `finish_headless_delivery.py --delivery .../FINAL_MMD15`，父PID67124，MCP任务键 `MMD_BACKGROUND_finish_delivery_final`，日志 `headless_bullet/finish_delivery_final.log`。先查 `FINAL_MMD15/delivery_status.json` 和 `native_audit_jobs.json`，不能重复启动。它并行独立原生3593样本检查，GPU先渲染frames301–360；生成 `11秒附近_连续复查.mp4` 后等待 Agent 看过连续画面并写 `agent_continuous_review.json` PASS。**不要未经实际观察写审阅标记。** 之后才GPU渲染其余1–300/361–450；独立复查失败会自动停止本任务自己的渲染进程，不能跳过失败。
>
> 待450帧全部新渲染，脚本将合并两个独立审计，做原SurfaceClass原皮肤面交线、关键帧全顶点/边中点/面心包含、源Action/231形态键/网格/权重/保护段验证；合Shikako音乐并全段音视频解码；保存复刻包、README与delivery_report。视频名 `完整角色_MMD物理与发片避碰_1080p_15s_Shikako.mp4`。当前仍未生成成片，不可声称完成。
>
> `prepare_delivery_final` 父PID62084已结束，其日志为 `prepare_delivery_final.log`。GPU渲染已被用户明确允许（不再打游戏），继续MCP，不抢键鼠。不恢复自动关机。旧候选及输入全部保留。后续最终报告需如实说明25%物理混合+有限宽度约束+少量整段参考回退+自动时间处理，未证明全头自碰或连续CCD。复刻包支持按输入长度重放，整首3分钟尚未验证。

> 最新进度：用户已说“我现在不打游戏了，用显卡”，显卡渲染已授权。`guard_pilot`、`guard_global_pilot`、`guard_faded_pilot`、`guard_full15`、`guard_continuous15` 均已失败并停止，不能续跑或复用未完成尾部。当前正在 `headless_bullet/guard_component15` 完整连续处理，日志同名 `.log`，脚本 `guard_headless_hair.py --global-strain --safe-reference .../dynamics_contact_islands --physics-gain .25 --component-fallback`。成熟物理位移以25%统一强度叠加有效避让参考，再进行真实宽发片约束。少量不能收敛的自由连通发片在整段一致回退参考，避免帧间切换；当前约7.16秒，3个连通自由部件/194顶点回退，其余保持物理运动，最终数量须看完成报告。
>
> 正常试渲 `REVIEW_GUARDED/keyframes` 已完成1/211/331/336/450五帧1080p，331和336已经视觉检查，无此前灰色翻片，卷发与皮肤分离。此目录仅五个样本，不是完整缓存。CPU试渲PID36696已结束。不要重复启动。
>
> MCP已启动 `prepare_headless_final.py` 等当前完整修正完成，PID68136，任务键 `MMD_BACKGROUND_prepare_component_final`，日志 `prepare_component_final.log`，最终新目录 `FINAL_BULLET15`。它将发布完整PC2、用独立后台Blender从正常母工程干净装配（避免MCP辅助场景材料重名）、恢复35%头发柔和投影、最终打包，再GPU试渲9个完整关键帧。完成标记 `preparation_status.json` 的 KEYFRAMES_READY_REQUIRES_AGENT_VISUAL_REVIEW。不能跳过视觉复查。
>
> 关键帧通过后，由Agent写 `agent_visual_review.json`（decision PASS、具体观察），再通过MCP启动 `finish_headless_delivery.py`：并行独立原生实际网格3593样本检查；先GPU渲染301–360、生成正常连续复查片；待Agent看过连续帧并写 `agent_continuous_review.json` PASS，再渲染其余帧、原SurfaceClass/完整包含/源数据保护检查、合指定音乐、完整解码和复刻包。此脚本尚未启动。绝不能写假审阅标记。
>
> `guard_headless_hair.py` 当前已冻结用于在跑任务；不要边跑边改物理/几何代码。整段一致部件回退在结束时回填前缀，因此必须等COMPLETE后发布。新回退政策/数量须写入最终报告，不可声称全部自由发片都在未经修正的原生物理中。`build_headless_repro_bundle.py` 保存准确源码及输入，并生成按片长参数化的 `replay_bones.py` / `guard.py`；三分钟尚未验证。

目标仍是完整角色、原柔光材质、夏安地库、固定全身镜头、指定动作与 Shikako 音乐的 1920×1080 / 30fps / 450 帧 / 15 秒展示视频。用户明确要求有自然头发物理、先合法初态、可复刻到三分钟。服装暂停，抱手 256–321 不拆开，原始数据和旧工程保留，禁止自动关机。

用户最新要求：正在打游戏，使用 MCP。Blender Addon 1.8 已连接 9876；工具列表没有独立 Blender 命名空间，按已安装插件的真实 JSON 协议通过 `scripts/blender_mcp_request.py` 连接 127.0.0.1:9876。没有使用键鼠，没有切换桌面焦点。GUI Blender PID 60164。脚本执行由定时回调排队，超时后先查状态，不能重复提交。

## 已否决与权限

旧 `fullhair_repro_20261030/FINAL_REPRO15` 虽有完整视频，但用户反馈 11 秒穿模观感、梆硬，已否决。柔性 PD 和材料支撑分支又有压皱/灰色翻片，已停止，不能复用旧视频充当新交付。

官方 MMDBridge 1.3.0 已校验，用户明确允许首次启动并继续视频。但 Computer Use 启动返回 `Computer Use was not approved to use mikumikudance_chs`。没有启动该 EXE，不能绕过限制换接口控制同一拒绝应用。当前使用不同的无窗口 MMD 兼容开源运行库，未恢复该 EXE 启动。

## 目前输入和发现

工作根：`E:/project/mmd/work/headswap_xl_codex/native_mmd_bridge_20261030/`。

`calibrated_proxy_chain/calibrated_proxy_shapes_ready.blend`：一次性发骨/代理初态校准，真实初始发片重放误差约 1.9µm，41 身体代理在真实皮肤内，代理初态交叠 0。Blender Bullet SPRING1 分支仍失稳（边长最大约 7.35 倍），已停止。其 `raw_positions.npy` 只有第一行，不是有效缓存。

`headless_bullet/input/` 是通过 MCP 新导出的全头校准 PMX、修正身体 FK VMD（30 帧静态前缀 + 450 帧）和 `headless_source.blend`。导出完成，不覆盖旧输入。

发现重要输入错误：导出 PMX 部分头发关节枢轴高度约 0.88 MMD 单位，而对应发骨高度约 18.56，远离头部。按校准后子骨骼头位置重建关节枢轴后，失稳大幅减少。保留原质量、阻尼、限制轴、弹簧、碰撞组及遮罩；所有修复日志均留存。

## 当前后端与脚本

`tools/mmd_headless/` 固定依赖 babylon-mmd 1.3.0、@babylonjs/core 9.15.0、esbuild 0.25.12，npm --ignore-scripts，版本锁已保存。

`bake.mjs` 经 esbuild 打包成 `bake.bundle.mjs`。NullEngine 无画面，无 GPU，单线程 Bullet WASM SPR，240Hz，gravity=(0,-98,0)，`disableOffsetForConstraintFrame=true` 兼容 MMD Bullet 2.75 的约束行为。手动 beforePhysics / afterAnimations / afterPhysics，记录所有 458 骨世界矩阵；144 物理发骨、185 总刚体均启用。全段约两秒，不能据此声称画面合格。

运行：`node tools/mmd_headless/bake.bundle.mjs <headless_bullet目录> 479 <新输出目录名> repair-pivots --legal-start`。必须使用新目录，保留旧结果。`--legal-start` 在静态前缀重置到合法初态，源第1帧不预先下垂，再连续运行物理。

`scripts/evaluate_headless_hair.py --run <目录>` 用真实权重回放全部 24207 原始头发顶点，映射骨别名，补偿源身体/头运动微小差异，保持原 8994 真根，无新增硬根。输出 3593×24207 positions.npy。`legal_start` 全段完成；原始骨骼蒙皮仍有实际穿插，不能交付。

MCP 真实表面复查 `REVIEW_RAW/raw_contact_audit.json`：源第1帧 0交线/0包含；211 帧1496交线，331帧423，336帧410，450帧545。实际检查40181头发三角面与50428真实皮肤面，不忽略头皮肤。证明仅PMX骨骼代理物理不足以处理当前宽发片。

`scripts/guard_headless_hair.py` 为成熟骨骼物理之后的有限宽度几何修正，不积分运动、不加刚性头部形状弹簧。检查实际皮肤交线/内部点、原边长±10%、真根。`--global-strain` 用稀疏全局边长投影加速旧GPU避碰，保留身体不动；仍待连续及视觉验收。旧 `guard_pilot` 在211帧边长未收敛已失败，不能采用。`guard_global_pilot` 正在1/211/331/336关键帧运行。先检查 status.json 和进程，不能重复启动。

## 关键帧完整画面

`scripts/publish_headless_hair.py` 将候选转头部局部 PC2，明确标记未验收；不能伪造 Bullet 速度状态或已通过几何检查。`REVIEW_RAW` 只有1/211/331/336/450五帧缓存，其余行未填充，严禁渲染整段。

`mcp_assemble_headless_preview.py` 通过 MCP 追加原正常场景，保留原材质、地库、脸眼饰品全部头发、固定镜头，保存新 `.blend`。`mcp_render_headless_preview.py` 通过 MCP 启动隐藏 CPU 渲染，4线程12samples1080p，PID68240，日志 `REVIEW_RAW/render.log`，输出 `keyframes/`。先查PID或 MCP driver_namespace['HEADLESS_NORMAL_PREVIEW_RENDER']，禁止重复启动。

## 必须继续完成

先看全画面关键帧及连续11秒片段。关键帧几何、发型及柔性都通过后，连续解算/几何修正全部3593样本，发布完整缓存，重做450帧正常1080p渲染、合指定音乐、ffprobe及整个音视频解码。新工程、有效缓存、精确后端版本/配置/校准/代码和最终视频一并交付。原身体保护段、原Action、231形态键及几何不变要重新验证。全头发片自碰/CCD未证明，身体原有残余如实说明。目前未完成新15秒成片。
