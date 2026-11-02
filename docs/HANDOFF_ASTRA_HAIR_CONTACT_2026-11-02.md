# Astra 新窗口交接：完整角色头发物理与防穿模

更新日期：2026-11-02，Asia/Shanghai。用户要求整理后由新窗口 Astra 接手，并把文档及轻量代码上传 Git；大文件保留本机。

## 先看结论

**用户最认可的是无碰撞的“根部点锚定”版本，评价“好很多了”。这版7.5–15秒视频已经完成并完整解码通过。加回防穿模的几轮候选均未通过，不能把最新候选当成最好版本。**

最新实测是社区 Jiggle Physics PR47 的真实身体网格碰撞：完整27束、源帧1–450连续解算，7.5–15秒225个整数源帧中23帧超过用户5cm深度门槛，最深6.56489cm，源帧412（13.7秒），主要是右侧短发Sidehair1.R。已停止，未启动整段新视频。社区源码没有本地修改。

额外复现了PR47浅穿越漏检：半径1cm，点从表面外2.5cm移到表面内0.5cm，函数直接返回内部点，未执行射线回查。它是明确的独立函数边界问题，但**尚未证明它是角色13.7秒进入身体的唯一历史原因**。不要把这个推断写成已完全定位，更不要以修好立方体替代完整头发验证。

交接时通过Blender MCP重新核对：68个登记后台任务全部退出，活动任务0。快照：
`E:/project/mmd/work/headswap_xl_codex/jiggle_pr47_mesh_20261102/handoff_background_jobs.json`。
不要依据2026-10-30旧交接中的历史PID恢复旧PPF任务。

## 用户当前目标与约束

- 优先完整角色、正常材质、全部头发的自然惯性、重力回落与防穿模，最终可扩展到3分多钟成片。需要插件/成熟算法、可复现流程；允许一定改动，不能逐帧手摆或自创一套物理求解器。
- 角色：东雪莲头＋达妮娅当前素体，完整脸、眼睛、头饰、全部27束头发，原银白发色、真实柔光材质。背景为夏安BREAK ME DOWN地库，固定全身镜头。
- 服装流程仍暂停。原舞蹈、表情、身体和腕部修正保留；抱手保护**源帧256–321**不拆开。原工程、原数据、旧缓存和认可视频均保留。
- 最新穿模口径为**最大埋入深度超过5cm才处理**，已从早先“深度或范围”改成只看深度。不能拿埋入范围、交线数量、毫米级相交当失败标准。0.6cm用户认为几乎不可见。
- 脚本/API接口错误自行修复；发现实际超过门槛的穿模、明显飘起、拉伸或物理失稳，先停下来报告，不默默扫描多组参数。
- 最新展示窗口是**原片7.5–15秒**，1080p、24fps、24采样、Shikako音乐。此前完整15秒目标为30fps/450帧；预览输出24fps不意味着物理解算改为24Hz。
- 用户曾要求图集代替视频，后来明确要求做视频，最近认可版及当前对照按视频窗口准备。未通过候选只有完整角色关键帧，不要冒充新视频已完成。
- **自动关机已取消，严禁恢复。** 用户已授权GPU，当前不再按玩游戏低占用模式限制。优先Blender MCP后台操作，避免操作桌面。

## 工作环境与入口

- 工作区：`E:/project/mmd`；Git仓库：`E:/project/mmd/mmd_repo`。
- Blender：`D:/software/blender/5.2.1/blender.exe`，5.2.1 LTS，build `9e2066aef7ef`。
- Python：`E:/project/mmd/mmd_repo/tools/contact_stack/venv/Scripts/python.exe`，PowerShell中加`-X utf8`。
- 主网格：`东雪莲x达妮娅_素体`；骨架：`东雪莲x达妮娅_骨架`。原基础68272顶点、231形态键；Jiggle准备另加1个静态初态整理形态键，当前232，不要误删或误判为原始数量。
- 接触技能：`C:/Users/Administrator/.codex/skills/repair-animation-contact/SKILL.md`。后续用户5cm/自然度/停止要求优先于旧技能严格接触门槛。
- 起始场景、素材和长期历史见`E:/project/mmd/mmd_repo/docs/HANDOFF_NORMAL_MMD15_2026-10-30.md`；最新详细连续记录见`E:/project/mmd/mmd_repo/docs/JIGGLE_ROOT_POINT_2026-11-02.md`。旧文档中的“下一步”、任务状态以本交接覆盖。
- 音乐：`E:/data/music/Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3`。
- 原动作：`E:/data/模之屋/动作/シニカルナイトプラン/シニカルナイトプラン.vmd`。
- 现有背景来源：`E:/data/模之屋/渲染/【夏安】BREAK ME DOWN!! - プレコ feat. 知声`。直接复用正常场景，不重新搭建或导入镜头VMD。

## 最重要的可复用版本

认可版目录：
`E:/project/mmd/work/headswap_xl_codex/jiggle_root_point_dance_075_15_20261102`

- 工程：`完整角色_原舞蹈_根部点锚定_15秒.blend`。
- 视频：`preview/完整角色_7.5-15秒_根部点锚定_无碰撞_1080p24fps_Shikako.mp4`。
- 视频为1920×1080、24fps、180帧、7.5秒，音频也7.5秒，完整解码通过；SHA256 `e98d66159c02498b0c3ecee1391ef25a3b8e07775464f70d3810f049b07bb597`。两GPU工作进程渲染墙钟434.11秒，编码验证6.97秒。
- `cache/`包含身体PC2与两份腕部PC2，三份均有效，使用绝对路径；头发已烘焙在Action中，回放不要求运行插件。此视频**无碰撞**，不是防穿模通过版。
- 未烘焙原舞蹈输入：`E:/project/mmd/work/headswap_xl_codex/jiggle_naturalness_fix_20261102/B_smaller_radius/完整角色_Jiggle配置_未烘焙.blend`。其旧配置写simulation_fps120，但新worker明确使用30Hz/15步预运行，不照搬旧时间展开。
- 根部策略来源：`E:/project/mmd/work/headswap_xl_codex/jiggle_root_point_20261102/configuration.json`及`long_hair_root_policy.json`。

该策略让18束长后发/长侧发的前两整节骨解除冻结，只锚定链起点；动态骨90→126，共144发骨、27束。其余9条编发/刘海/短侧发链仍沿用前两骨固定，其中`Sidehair1/2.L/R`尚未解冻。**不要把“所有发束根部都已自由”当事实。** 最坏短发属于这两条Sidehair链，可评估固定区与避让空间，但不要盲目缩短固定区。

动力参数：root/length elasticity均1、angle0.7、soften0.6、gravity0.25、air0.2、friction0.5、blend1；碰撞半径依发骨不同，见认可版`configuration.json`的settings，不能假设全部2.25cm。30Hz、0.5秒预运行。不应再用120Hz时间展开当作中性提高精度：原版阻尼/弹性按步生效，改变频率会改变响应。

早先3秒静止身体＋转头测试在`E:/project/mmd/work/headswap_xl_codex/jiggle_root_point_20261102`，用于验证根区/惯性。其脚本会冻结身体和缓存时钟，**不能拿它直接替代原舞蹈**。

## 加碰撞的实际结果：不要重复已失败路线

以下深度均对真实显示头发，不是仅代理骨/球体；除特别标注均为源帧226–450的225个整数采样。

| 版本 | 最深埋入 | 超5cm帧数 | 结论 |
|---|---:|---:|---|
| 认可无碰撞版 | 6.46575cm，f412 | 43 | 惯性观感获认可，接触未通过 |
| 恢复旧14椭球 | 2.94776cm，f347 | 0 | 两侧短发被明显顶成水平，观感失败 |
| 内缩贴合223球 | 5.90527cm，f411 | 85 | 飘起减轻，但超限更多，未通过 |
| 223球改直接骨骼父级 | 5.90528cm，f411 | 仅复核6个选定帧 | 修正绑定规范，但运动/残余基本不变 |
| 社区PR47真实身体网格 | 6.56489cm，f412 | 23 | 超限次数减少，最坏仍超门槛 |

目录分别为：

- `E:/project/mmd/work/headswap_xl_codex/jiggle_root_point_collision_075_15_20261102`
- `E:/project/mmd/work/headswap_xl_codex/jiggle_fitted_contact_20261102/candidate01`
- `E:/project/mmd/work/headswap_xl_codex/jiggle_bone_parent_contact_20261102`
- `E:/project/mmd/work/headswap_xl_codex/jiggle_pr47_mesh_20261102/candidate01`

14椭球的胸肩`Jiggle_Ellipsoid_上半身3`占用真实身体外空间，叠加发骨半径并向外/向上推，12.5秒短发末端抬高约11.5–15.2cm。零头发半径的独立查询也有不合理推移，不能只靠再次全局缩半径或增加重力解决。

223球是一次性几何拟合：球半径=到闭合真实皮肤的内部距离−5cm，初态发骨检查点无推移；原版求解器未改。但这是骨点球形包络近似，**不是严格实现“真实发片超过5cm才介入”**，更不是整片几何保证。当前5cm可靠落实在结果验收上，原版/PR47标准接触本身通常会在接触边界时响应。不得把验收门槛说成解算器已有的精确死区。

作者明确不支持用约束驱动碰撞体，已把Child Of改成直接bone parenting；实际求解时451次矩阵采样误差0。该改法有社区依据，但新旧450帧27束末端质心差最大仅约2.62e-6m，不能宣称它是本例主要穿模原因。作者说明：
https://github.com/naelstrof/blender-jiggle-physics/issues/11#issuecomment-3058691780

## 当前社区源码、已知漏检与证据边界

官方基底：`naelstrof/blender-jiggle-physics` commit `792db09a22cd5c7dc5b5c1b4eb0ea12c4af3e6b1`，v4.5.3，源码SHA256 `1bd2c0ad34e4f4b83b8c04abd6294ad9e7ca9ad66cbc068fab7e71785e3b61aa`。

社区PR：https://github.com/naelstrof/blender-jiggle-physics/pull/47

- 仓库`Noisysundae/blender-jiggle-physics-ns`，commit `00a01ff31f8d4cea3c07efd5f030e3f15b93398a`；截至本轮仍open/未合并。
- 隔离源码：`E:/project/mmd/work/headswap_xl_codex/jiggle_pr47_mesh_20261102/vendor/Noisysundae_00a01ff31f8d/__init__.py`。
- GitHub blob SHA1 `e65b6da85983481146dd9e633f3cb658bcf7d111`已校验；源码SHA256 `1334a8b452745fc7201cf6c05d6982bfe0a33b2c67335420025b260cb16c2b57`。
- AST复核只改`VirtualParticle.mesh_collide`和`set_child`，未本地修改；其他资源从相同官方基底复制。保存于PR目录`plugin_provenance.json`。
- `mesh_collide`使用半径内最近面查询；查询失败才从`position_last`发射线；最后忽略背面接触。该PR没有改`constrain()`的碰撞反向传播分支。

最新直接复现：立方体前表面x=0，半径0.01m，上一点x=-0.025m、当前点x=+0.005m。非穿越期望x=-0.01m，实际原PR返回x=+0.005m。最近面在半径内查询成功，因此跳过射线，再被背面过滤提前返回。若当前点深入到x=+0.05m，反而会触发射线并挡住。0.5cm是复现输入，**不是把用户验收改成毫米级**。

关键证据均在`E:/project/mmd/work/headswap_xl_codex/jiggle_pr47_mesh_20261102`：

- `function_probe.json`：原五项基础测试按其预期通过；其中“内部点不动”本来就是背面过滤行为，不是有效救回穿模的证据。
- `function_boundary_probe.json`：新增`cross_front_shallow`明确失败，源码未改。
- `worst_frame_contact_probe.json`：f412已烘焙Sidehair6.R head埋入约5.76677cm，同点静止查询返回零推移。它是静止后验测试，**没有恢复原积分器上一时刻状态**。
- `result.json`：225帧深度汇总；超限帧277、408–426、431–433。最大值为面心6.56489cm，最深实际顶点约6.55679cm。
- `candidate01/depth_A/`、`depth_B/`：每帧实际头发顶点和面心的有符号距离、分束报告。
- `candidate01/setup_comparison.json`：144骨参数与认可版完全相同、源文件相同、碰撞网格时钟误差0。
- `candidate01/collider_timing.json`：451次求解入口矩阵及实际网格重放误差均0。
- `candidate01/collision_observation.json`：4183次真实网格投影，覆盖450个帧号。
- `candidate01/bake_report.json`：全450整数帧身体骨和皮肤误差0，无既有拉伸标记。
- `candidate01/motion.npz`：真实显示末端、head_world、raw_frames/raw_particles。原始粒子仅存位置，未存逐粒子bone_name/type映射；如要追踪真实入体过程，需要补只读观察信息，不能把后验骨点直接说成完整原始积分状态。
- `candidate01/preview/frames/`：正常完整角色关键帧，输出1/14/35/37/85/111/121/149/180。f0149是源f411（13.6667秒），不是精确f412；不能把它标成精确13.7秒测量画面。

**尚未确定的内容**：身体移动与粒子自身移动的相对穿越、骨长约束是否把碰撞修正拉回、短侧发固定根区、粒子到骨骼/蒙皮回写等对实际f412入体的各自贡献。浅穿越漏检与内部点不恢复确实存在，但未追完整进入历史，不要只凭它们宣布整个角色根因已全部定位。

## 另一个容易跑偏的结论

官方`VirtualParticle.constrain()`约602行：未设置碰撞目标时完成forward constraint即返回；设置非空碰撞目标后，当前angle0.7/length1会进入backward constraint及相邻骨混合，即使该步没有真实投影。因此打开碰撞也会改变无接触响应。223球版f1零真实投影，短侧发显示末端仍相对认可版偏移约1.9cm。

这是可复现的行为差异，但作者v4.1.0把碰撞反向传播列为正式功能，**不能直接叫成已经确认的bug，更不能新增“无接触逐值完全一致”作为用户没有要求的严格门槛**。当前官方主线及PR47都保留它；所查发布/PR中未找到独立关闭选项，但未穷尽所有fork。用户要的是看起来自然、可复现且控制明显穿模。

## 复跑脚本与命令

核心脚本在`E:/project/mmd/mmd_repo/scripts/`：

- `bake_jiggle_root_point_dance.py`：默认无碰撞；`--collisions ellipsoids`可配`--collider-profile`、`--collider-binding bone-parent`；`--collisions mesh --plugin-provenance <json>`使用社区原码和实际身体PC2。默认450源帧，不能不检查缓存范围就跑3分钟。
- `probe_jiggle_pr47_mesh.py --root <PR根目录> --boundary-only`：无需角色动力学即可复现浅穿越；`--frame 412`做已烘焙最坏时刻静止几何查询。
- `measure_full_hair_intrusion.py --source <blend> --out <新目录> --frames <逗号帧列表> --capture-motion`：只读真实头发深度，闭合身体连通分量并集，三方向射线判内外，最近边界距离；24207顶点＋40181面心。只代表采样，不是连续CCD/任意面内精确最大值/自碰证明。
- `render_jiggle_dance_preview.py --physics <候选目录> --out <新输出目录> --collisions mesh --keyframes-only --key-outputs 1,85,121,149,180`：完整角色GPU关键帧。关闭新模拟，只读Bake；也可分段`--first-output 1 --last-output 90`及`91/180`。
- `encode_jiggle_dance_preview.py --out <预览目录> --wait-for-render`：要求180帧及两段回执，H.264/AAC、计帧与完整解码；新候选需独立PNG池，不能复用认可版图片。
- `inspect_jiggle_collision_lift.py`、`prepare_jiggle_tolerance_colliders.py`、`summarize_jiggle_contact_refit.py`：旧试验诊断，勿当成已通过默认流程。

Blender调用格式：

```text
D:/software/blender/5.2.1/blender.exe --background --factory-startup --threads 4 --python E:/project/mmd/mmd_repo/scripts/probe_jiggle_pr47_mesh.py -- --root E:/project/mmd/work/headswap_xl_codex/jiggle_pr47_mesh_20261102 --boundary-only
```

正常生产由已连接的Blender MCP后台启动，不操作GUI：

1. `scripts/blender_mcp_request.py`连接localhost:9876；`mcp_snapshot_mmd_background_jobs.py`只读登记进程，先核对再启动。
2. 将`{key, log, argv}`写入`E:/project/mmd/work/headswap_xl_codex/standard_proxy_20261031/next_job.json`。
3. 用客户端`--code-file E:/project/mmd/mmd_repo/scripts/mcp_launch_standard_proxy.py --response <文件> --timeout 12`调用。启动器CREATE_NO_WINDOW，cwd为仓库，命名空间`MMD_BACKGROUND_standard_proxy_`＋key，已运行则拒绝重复。
4. 使用唯一key和新输出目录。网络超时后先查登记任务及日志，不能盲目重试。不要执行残留next_job.json而误启动上一个任务。
5. 有些Blender Python异常进程仍exit0，必须看日志/JSON回执。只因没有Get-Process结果不能断定提权后台不存在。

时间映射：源1帧=0秒，源时间`(f-1)/30`。24fps预览输出i对应源`226+(i-1)*1.25`，180帧覆盖`[7.5,15)`，最后源449.75。音乐从`7.5+2/30=7.5666666667`秒接入，保留原先两帧提前量。

缓存：身体PC2约0.55GB、两腕各约14MB；身体PC2由现有120Hz采样形成，但回放驱动已验证与30Hz源动作一致。保留其CUSTOM时钟/driver，不冻结、不自行重定时。显示头发通过Action回放，不能把顶点缓存冒充可恢复积分器状态。

## 给 Astra 的建议起点（不是已经执行的修复）

1. 先看认可视频，明确需要保留的惯性与下垂观感；看本轮13.7秒真实接触证据。
2. 在独立副本复现`cross_front_shallow`，审阅社区`mesh_collide`、`constrain`与`apply_pose`，评估最小修复是否足够，是否还需处理移动碰撞体或约束回投。用户允许一定改动，但若改社区源码，需明确标注来源和本地差异，不能说成原PR已修好。
3. 不要凭我的建议锁死路线；可以重新评估成熟社区后端，但不能重做已经失败的全局加硬、加长固定区、120Hz盲目展开或扩大碰撞体，并把结果当新发现。
4. 先验证接触边界，再做完整27束连续解算和正常关键帧；重点覆盖277、408–426、431–433，尤其f412。新方案出现实际超限/失稳时按用户要求停下报告。
5. 接触达到用户门槛且观感可用后，完成7.5–15秒正常预览、音乐同步、完整解码；完整15秒及3分钟扩展另核对输入/缓存范围。不要只展示一束或一直停留在立方体实验。

## Git 上传范围

远程为`https://github.com/NiHaiMa123/mmd.git`，当前本地分支`main`。用户要求上传文档和轻量代码，大文件不用上传；本交接之外还有大量历史未提交脚本、addon、tests、skills及文档，需要按实际清单备份。模型、纹理、视频、PNG池、.blend、PC2、数值大缓存、虚拟环境、node_modules、原生第三方二进制及生成ZIP保留本机，不混进Git提交。

本地`E:/project/mmd/work/`在仓库外，本文多数实际工程/报告都在此处；Git只含文档、代码和必要小型证据摘要，不包含完整可播放资产。不能对远程克隆声称素材齐全。推送完成的分支、提交号和同步结果以用户收到的最终回复及本机Git记录为准。

为远程备份额外复制的小型证据在`E:/project/mmd/mmd_repo/docs/evidence/hair_contact_20261102/`，其中README和manifest列出每份JSON的本机来源；不是新运行结果。`E:/project/mmd/mmd_repo/scripts/fetch_jiggle_pr47.py`可下载固定公开提交并校验源码，方便不上传vendor/依赖也能恢复相同社区版本。
