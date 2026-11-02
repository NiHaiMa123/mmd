# 现成头发物理流程：2026-10-31 进行中

> **最高优先级：用户已要求外出期间遇到问题停下来，当前已暂停。** 最新完整状态见 [PAUSED_MMD15_2026-10-31.md](PAUSED_MMD15_2026-10-31.md)。下文所有“当前运行”均为历史记录；最新宿主检查仅GUI Blender13260，没有后台解算/渲染。用户返回并要求继续前，不启动新任务。仍无新版无穿模15秒成片通过。

> **10:48前后最高优先级状态**：Jiggle11/12/13的450帧审查分别208/186/384帧失败，均不能交付；11为原权重/前根1，12尝试1890点head>=.5权重固定，导致局部拉扯，未采用；13恢复所有原权重，固定54个链首两段+插件预热60，仍有肩胸/臂穿模。13原231键、68272点权重、原6NLA曲线的数据保持验证通过，但不代表物理通过。14复用13补齐固定FK通道的诊断副本，与13坐标/碰撞相同，证明漏通道假设不成立；不要继续这条补通道路线上浪费时间。当前唯一物理解算：**官方Append append03** PID37764；MCP键append_cloth03；`standard_cloth_20261031/append03`，source完整准备场景10，官方RigidBodyToClothConverter BONE_CONSTRAINT源码不变；PC2 CUSTOM时间正确，450帧身体误差0；原生Cloth质量32、collision16、stiffness1000、mass.005、bending50、distance.025。Head附着驱动改用源Head每1/8帧的独立原生FK烘焙（3593样本），避免同一原骨架发骨StretchTo→代理Armature→原骨架循环。日志60.9秒的2个循环是converter刚创建时、替换独立驱动前的瞬态；须重开工程核对不再有循环，不能只忽略日志。append02是上一版仍用CopyTransforms附着驱动的试算，已仅停止其自有PID29124并保留数据，不重启。03转换后首帧真实网格差3.9e-7m；逐帧身体cache误差0。**append_review03** PID34212，等待现有03烘焙后正常1080p GPU关键图10张和450帧实际表面/包含检查，不另开物理。查append03.log、append_review03.log、append03/status.json和review_status.json。未通过前严禁PASS或整段渲染。

> **2026-10-31 本轮最高优先级更新**：native06已完成，但重开后实际为静态头跟随，未通过。只读探针发现负帧缓存范围重开显示0帧；Blender pointcache.cc扫描用unsigned start，与负帧范围不兼容。把现有正帧原生缓存复制为ASCII命名、显式外部缓存并正帧范围，另存 **standard_cloth_20261031/candidate07_replay** 后回读恢复；不重新模拟、不改旧文件。07实际10时刻检查3次失败，331/338/345帧右Sidetail3/4.R穿皮肤，含内部连通块；正常1080p 69/331帧已实际看图，331仍有脱散发片，**06/07均不能验收或整段渲染**。`repair_native_cache_replay.py`、`probe_native_cache_paths.py`、07/audit和keyframes记录证据。外部缓存无原生frame0信息文件，UI点数15080不能作实际顶点数，文件头实际24207；不要当最终缓存交付。
>
> **当前正在运行**：通过已连接的Blender MCP启动 **Jiggle candidate11**，原版插件不修改源码，沿用10参数但修正PC2 CUSTOM帧驱动及120fps时间展开时的驱动表达式；pid33612，任务键jiggle_candidate11。未开启旧混合轨迹。输出 `jiggle_physics_20261031/candidate11`，日志candidate11.log。另接续只读/GPU审查 **jiggle_review11** pid37460，等待当前烘焙后450帧真实表面/包含检查与10张正常1080p关键图，日志review11.log。这些PID是记录时快照，继续须核对；不要重启已结束旧任务，不能提前写PASS。当前唯一GUI Blender PID13260，TCP9876可用，无键鼠控制。

> **再更新，优先级最高**：native04修正碰撞缓存后16时刻零皮肤交线，但试渲出现发片散落，未验收、不能整段渲染。原始渲染网格166连通块，其中103块3907顶点未连接固定根。已按原始Basis几何、不同原连通块间0.5mm距离添加4212条**原生Cloth Sewing Springs**接缝，得到14连通块且全部连接原8994硬根，未增加假根。当前唯一解算为 **native实际发片 candidate06，PID20768，MCP键native_mesh_cloth06**；60帧负帧预热（-59..0），Head/首首帧保持约束仅负帧启用，1–450完全停用。当前原数据比对 `candidate06/source_preservation.json` 已通过：原Actor232键（原231＋既有初态整理）、原骨骼权重、原NLA动作曲线均保持，头发副本232键24207点保持。candidate05曾尝试另建头部驱动，但初态坐标检查未通过即停止，无成品；06保留原权重/形态键，通过冻结负帧首姿修正。另已通过MCP启动 **native_review06**，只等待06现有解算完成后做22个关键时刻实际表面/包含检查及10张正常1080p GPU试渲，不重算物理；查看 `review06.log` 和06的`review_status.json`。不得提前写agent_keyframe_review PASS。Jiggle11修正时间映射的对照未启动（当时自动审批额度错误），无需为继续交付而再启它。

> **最新覆盖状态**：已发现并修正碰撞体 PC2 时间映射错误。FRAME/SCENE模式把采样编号当帧号，candidate10 的 step=.25 缓存实际以四分之一速度播放；331帧对应约83帧身体。Jiggle120fps10、Append代理01及Native实际发片03的碰撞结论因此不能用于评判正确配置下的后端能力。30fps Jiggle07 step1不受此项错误影响，其32失败帧仍有效。**当前唯一烘焙任务为原生实际发片 candidate04，PID69036，MCP键native_mesh_cloth04**，目录 `standard_cloth_20261031/candidate04`；脚本已使用CUSTOM/FRAME及 `(frame-first)/step` 驱动碰撞体，先逐点验证450帧同步误差<5e-6m，再烘焙。检查该目录实际status，不要重启03或其他旧任务。03已结束且试渲失败，不能当最终交付。

优先于旧混合物理交付文档。用户拒绝自行设计的混合运动/几何回退/滤波方法，要求研究已有 MMD 作者与插件，并继续完成完整角色 1080p/30fps/450帧/15秒带 Shikako 音乐展示。服装暂停、抱手256–321保护、原文件保留、禁止恢复自动关机、优先 MCP 不抢键鼠继续有效。

## 当前正在运行：先检查，勿重复启动

本次实际发片 **Blender 原生 Cloth** 全450帧烘焙：

- 宿主 Blender PID **55080**，MCP任务键 `MMD_BACKGROUND_native_mesh_cloth03`。
- 目录 `E:/project/mmd/work/headswap_xl_codex/standard_cloth_20261031/candidate03`。
- 脚本 `scripts/run_native_mesh_hair_cloth.py`；日志为上一级 `candidate03.log`；状态 `candidate03/status.json`。
- 记录时达到390/450，约392秒；这不是最新状态，继续时须读实际文件及宿主进程。
- 输出工程 `完整角色_原生发片Cloth_15秒.blend`：解算前已保存，不能凭文件存在宣称烘焙完成。
- 原生磁盘缓存位于 `blendcache_完整角色_原生发片Cloth_15秒/`，有效完成还须检查 `point_cache.is_baked` 及450份文件。
- `cache/` 中包含原身体碰撞PC2与原有效腕部缓存。
- `cache_probe/*.npy` 是一次未完成字节重排解码的**无效诊断数据**，已标注 `UNVALIDATED_DO_NOT_USE.txt`；绝不能当模拟结果、验收数据或渲染输入。原生 BPHYS 从未被此探针改写。

Blender GUI PID60164、MCP端口9876，当前仍开旧 FINAL_MMD15；未在GUI打开未经通过的新候选。

## 原生 Cloth 当前做法

基础为 `jiggle_physics_20261031/candidate10/完整角色_Jiggle配置_未烘焙.blend`，只是首帧整理、发骨初态匹配后的完整正常场景，**不是 Jiggle 烘焙结果**。旧整头运动缓存及其主修改器已移除，身体NLA与腕部修正保留。

原完整角色网格保留；从副本通过原生编辑模式删除非头发顶点，保留UV、材质、权重和232个形态键（原231＋一次性初态整理）。真实头发副本名为 `完整头发_原生Cloth_实际发片`。原角色仅通过末尾 Mask 隐藏已经由副本显示的头发，脸、眼睛、头饰、身体、舞台和镜头仍显示。

新属性 `SourceVertexID` 追踪原始顶点编号；全部24207个头发顶点保留，8994个真实硬根 Pin=1。副本 Armature→原生 Cloth，身体为已有精确闭合皮肤缓存加 Collision；碰撞集合只选身体，未关闭手或抱手段。自碰未开启，不能宣称头发互碰解决。

Cloth设置：quality20、mass .005、air10、拉伸/压缩/剪切1000、弯曲50、碰撞quality12、distance .003m，身体outer .003m。无自写动力学/接触投影/时间滤波，无旧避让轨迹混合。

该方法依据 Blender 官方 Cloth on Armature / Pin Group / Collision 工作流，而非新设计求解器：
https://docs.blender.org/manual/en/4.1/physics/cloth/examples.html#cloth-on-armature

下一步必须实际检查缓存重开、完整表面、正常关键帧和连续动作。原生烘焙结束也不等于通过。

## 本轮此前的现成插件结果（均未验收）

1. Jiggle Physics 原版固定提交 `792db09a22cd5c7dc5b5c1b4eb0ea12c4af3e6b1`，ZIP SHA256 `4b9ef7fbee86e43dddd0d979a9d8c503c8e69cfb24caf40e32de724899df5c81`，源码与ZIP逐字一致，`__init__.py` SHA256 `1bd2c0ad34e4f4b83b8c04abd6294ad9e7ca9ad66cbc068fab7e71785e3b61aa`。
2. `jiggle_physics_20261031/candidate01–10` 均保留。01初始代理问题明显；02/08/09包装脚本或验收失败未产生成品。07较好但450帧检查仍32帧有交线，4帧有包含，不能交付为零穿模；10采用120fps原生NLA时间缩放、还原30fps，身体误差0但231/450帧有交线，部分发束外翻，已停止这条参数路线。**不要重启其渲染或填写PASS。**
3. 120fps时间缩放检查：`check_jiggle_nla_retime.py` / `retime_checks.json`，直接缩放NLA strips能保持源姿态；原Action不必改写。此为集成检查，不是已验证发型结果。
4. MMD Tools Append 官方提交 `5f60297972f856b4cc08b753022bb1add1db2d1d`，ZIP SHA256 `ad1b69f72cafdfdf5e6ee5809d7d19fc64a4bc0af824f57dae0140488986f99b`，保存在 `jiggle_physics_20261031/append_reference/`。
5. 官方RigidBodyToClothConverter的BONE_CONSTRAINT模式对144个原有头发刚体成功转换，得到396点171面代理，原生Cloth全450帧完成。保存在 `standard_cloth_20261031/candidate01`。但实际原始发片16时刻有15次失败，最多1574交线，另有拉伸，**不是已成功的新路线**。期间转换器产生依赖循环/未绑定Smooth警告；配置后来另建头部附着驱动减少依赖，不能忽略最终实际失败。
6. Native mesh candidate02 因源编辑网格隐藏顶点的选择问题未通过分离对应检查；03已用reveal+BMesh原生选择修正并开始烘焙。

## 审计与渲染工具

- `audit_jiggle_hair_candidate.py` 现已适配原生Cloth实际头发副本。若存在副本，则从两个最终求值网格的 `SourceVertexID` 合成原始编号坐标；断言原50428个皮肤三角形和40181个头发三角形没有被隐藏/删除，再检查真实交线。只读审计；名字虽有jiggle，不代表仍使用该求解器。
- 参数 `--source <新blend> --out <新报告目录> --containment` 默认16个关键时刻；`--first 1 --last 450 --step 1` 检查每帧，`.125` 检查3593个样本。可选component containment，不是全头自碰或CCD证明。
- `render_full_hair_showcase.py --source <新blend> --out <新图池> --frames ... --percentage 100 --samples 32 --device GPU`，原生1920×1080，固定全身镜头。
- `review_jiggle_candidate.py` / `finish_jiggle_delivery.py` 目前写死了Jiggle工程名与审计入口文件，**不能直接用于原生Cloth新工程**，须适配实际文件名后再启动。
- `encode_jiggle_showcase.py` 不依赖旧混合验收文件，能验证450新帧、按两帧提前量合Shikako、ffprobe及完整解码；输出名仍有Jiggle，适配后再用于最终原生Cloth成片。不要伪造旧缓存publication/审计schema通过旧编码器。

MCP启动器 `scripts/blender_mcp_request.py` + `scripts/mcp_launch_background_job.py`；后者读 `native_mmd_bridge_20261030/headless_bullet/next_job.json`，记录Popen避免同键重复。

## 来源研究

见 `RESEARCH_MMD_HAIR_PHYSICS_2026-10-31.md`。夏安原工程与ZIP校验一致：头发20根骨骼逐帧旋转烘焙，HairC1–4留有 `jiggle_blend` 曲线与Jiggle Physics一致；不能证明全部20根上游求解器。两份ABC用于外套/裙子，XPBD组未接入对象。B站平台风控停止API，没有假装看完未读视频。

用户要看到完整正常15秒视频，不要再次只交单束/灰模研究。若最终仍有残余，必须明确指出，不能以单束、代理、抽帧或原生缓存结束冒充完整通过。
