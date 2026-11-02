# 新对话交接：完整角色的正常 15 秒 MMD 成片

记录时间：2026-10-30 08:20，Asia/Shanghai。路径均为本机实际工程。

## 最新用户要求与优先级

用户准备换新对话继续，要求接下来完成**完整角色、完整头发、正常材质和场景的 15 秒 MMD 渲染**。
单缕蓝色发片、灰模、左右诊断对照均不是最终成片。

角色沿用东雪莲头＋达妮娅干净素体，不要颈环。服装与布料此前已暂停，不能擅自恢复旧刻晴衣服流程。
使用完整脸、眼睛、头饰、全部头发和现有身体，沿用已经做好的柔光质感。
背景沿用用户夏安 BREAK ME DOWN 工程的地库；固定正面全身镜头，不使用镜头 VMD。
1920×1080，30fps，1–450 帧，15 秒，带用户指定音乐和原动作／表情。
**自动关机已明确取消，不要恢复，不要设置任何关机任务。**

下一阶段先完成完整场景整合和正常材质关键帧试渲，再输出整段。
碰撞算法研发服务于成片；不要再次陷入只研究一缕头发而始终不展示完整角色。
未完成的全头／身体碰撞须如实列出，不能用单束检测通过冒充所有穿模均解决。

## 工作区与运行环境

- 工作区：`E:/project/mmd`；实际代码仓库：`E:/project/mmd/mmd_repo`。
- Blender：`D:/software/blender/5.2.1/blender.exe`。
- 普通工程 Python：`E:/project/mmd/mmd_repo/tools/contact_stack/venv/Scripts/python.exe`。
- PPF Python：`E:/project/mmd/mmd_repo/tools/ppf/native/python/python.exe`；不要用前一个环境运行 PPF，缺其依赖。
- 主对象：`东雪莲x达妮娅_素体`、`东雪莲x达妮娅_骨架`；68272 顶点、231 形态键。
- 技能：`C:/Users/Administrator/.codex/skills/repair-animation-contact/SKILL.md`。
- 本轮实验源码／技能包在仓库 `dist/contact-experiments-20261030.zip`、`dist/repair-animation-contact-skill-experimental-20261030.zip`。
  稳定插件仍为 0.1.6，不能将实验源码宣传成全角色一键避碰成品。
- 仓库存在大量历史改动、未跟踪脚本和工程，不能清理或覆盖用户文件。

## 可以直接复用的正常 MMD 母工程（重要）

目录：`E:/project/mmd/work/headswap_xl_codex/animation15_20261028/`。

1. `东雪莲_固定镜头_15秒.blend`：已含完整角色、全头发、正常材质、固定镜头、背景与音乐。
2. `东雪莲_シニカルナイトプラン_固定镜头_1080p_15s.mp4`：旧版正常成片，1920×1080、30fps、450 帧、H.264/AAC、音视频 15.000 秒，已全段解码。
3. `README.md`、`setup.json`：素材路径、舞台坐标、光照与镜头设置。
4. `prepare_animation.py`、`render_animation.py`、`verify_animation.py`、`encode_and_verify.py`：完整流程。

旧版没有启用身体／头发修正，穿模保留；**它是正常画面的基础和对照，不是已经修好穿模的最新版**。
新成片必须输出到新目录，例如 `E:/project/mmd/work/headswap_xl_codex/normal_mmd15_20261030/`。
旧渲染脚本把输入文件名和输出目录写死在脚本所在目录；应复制并适配到新目录／新工程，
不能直接调用旧脚本后把旧视频当成新成果。禁止复用旧 PNG 池导致跳过新帧。

实际素材：

- 完整人物动作：`E:/data/模之屋/动作/シニカルナイトプラン/シニカルナイトプラン.vmd`。
  28700 骨骼关键帧、3065 表情关键帧；原动作范围 0–5994，这次只渲染 1–450。
- BGM：`E:/data/music/Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3`。
  沿用旧版两帧提前量 `0.0666666667s`，具体编码方式参考旧脚本。
- 用户背景根：`E:/data/模之屋/渲染/【夏安】BREAK ME DOWN!! - プレコ feat. 知声`。
- 已解包背景：`E:/project/mmd/work/headswap_xl_codex/lookdev_reference_20261028/author_project/BREAK ME DOWN!! 20260902.blend`。
  旧版已冻结其第 2637 帧布景，清除原人物／镜头／歌曲／歌词／借物表。优先复用现成场景，避免重复整理。
- 柔光角色库：`E:/project/mmd/work/headswap_xl_codex/DELIVER_LOOKDEV/东雪莲x达妮娅_柔光质感.blend`。
  Cycles/AgX，皮肤 SSS/Coat、发丝各向异性、头发投影分离、眼睛补光、轻微 Bloom。
  旧正常成片使用 RTX 5080 OptiX、32 samples＋降噪。

## 当前后台任务：先检查，勿重复启动或终止

本轮物理根目录下文简称 P：
`E:/project/mmd/work/headswap_xl_codex/contact_repair_20261029/surface_proxy_20261029/`。

2026-10-30 08:19 已在宿主权限下核对：

- 后台 worker PID **26948**，脚本 `E:/project/mmd/mmd_repo/scripts/resume_hair_volume_delivery.py`。
- 原生 PPF PID **30460**，自 07:50 恢复运行。
- 实际运行目录 **P/full_feedback_ppf_transport**，不是 compact 目录。
- 当时最新 `vert_819.bin`，约源帧 205.75；最近状态 `state_719.bin.gz`，还有 599、479 等。
  这些只是记录时快照，新对话必须读取当前状态，不能把这些数字当最新进度。
- 原生输出总数目标为 0–1796（120fps），对应源帧 1–450（30fps）。两种帧号不要混淆。

主要监控文件：

- `P/continuous_delivery/worker_status.json`：阶段；RESUMING_NATIVE 阶段不逐帧刷新，须同时看实际输出。
- `E:/project/mmd/mmd_repo/outputs/hair_continuous_delivery_worker.log` 与 `.err.log`：原 worker 的日志／进度。
- `P/full_feedback_ppf_transport/runtime/real_outfit/session/output/vert_*.bin` 与 `state_*.bin.gz`：实际输出及原生检查点。
- `P/continuous_delivery/result.json`：worker 全流程结束后才会生成，不能提前假定存在或通过。

worker 计划：从真实状态 77 恢复，dt=.008，每 120 输出帧保存；原数据精确身体轨迹，保留全部接触。
完成后自动输出 `P/full_resumed_display/PPF_VolumeHair_Candidate_NotAccepted.blend`，
执行全段 1/8 帧碰撞／包含／应变／真发根独立复查、源数据保持检查，
生成 `P/continuous_delivery/review1080` 多角度图。**这些仍是左单束诊断，不是最终正常 MMD 成片。**

后台脚本会拒绝重复 worker。需要恢复时先核对进程／检查点和日志，再使用原生状态，
不要从顶点缓存伪造完整物理状态。不要用全局 terminate 杀掉其他任务。
本机受限命令环境的 Get-Process 可能看不到提权宿主进程；须在同一宿主权限视图核对，
不能仅凭默认 Get-Process 空结果判断任务不存在。

## 已完成的接触修正与真实验收范围

- 身体主次：头／躯干优先固定，普通肢体接触允许改动作。
  抱手 256–321 帧保护，尚未解决，不能拆开手势取得零穿插，也不能宣称已握拳。
- 右 Sidetail：1095 点，旧有限宽发片修正全 1–450 帧独立3593个八分之一帧采样通过。
  是几何修正，不能称全头动力学。新左臂动作窗口下的右束回归也通过。
- 左 Sidetail：1101 点、1654 面，36 个真实头骨硬根。
  时间样条左臂绕行＋局部腕部 LBS/DQ 体积修正，238–252 帧449个1/32帧样本通过。
  腕部皮肤最多改0.998mm；手腕最大偏移9.918cm，峰值速度4.832cm/帧（源4.592），动作自然度另审。
  原10 Actions、231形态键、基础网格、权重保持；新增NLA后下一阶段源Actions为11，不能误判改写了原10个。
- 左单束 PPF 体积代理：325点／864四面体，显示点非负重心嵌入，21体积硬点约束36真实显示硬根。
  没有关闭碰撞／接触豁免。物理CCD不证明最终显示网格CCD。
- 已中断的 compact 连续运行从1帧算到约328.5，留下可验证输出。
  提取其230–325帧，**保存重开761个八分之一帧采样：交线、内部点、超限应变均0**；
  边长比 .92245–1.06029，真根误差约 .004358mm。
  报告：`P/continuous_contact230_display/independent_validation.json`。
  开头1–69帧独立545个八分之一帧样本也通过：`P/compact_prefix70_display/independent_validation.json`。
  这些不是全450帧验收，也不能替代当前恢复运行的新结果。
- **全头其余连通块、发束互碰／自碰、身体其他区域及保护抱手问题没有全验收**。

关键候选：

- `P/body_spline_wrist_volume/Body_Spline_And_LocalWristVolume_Candidate.blend`：身体和腕部修正，保留旧右束。
- `P/feedback_ppf_display/PPF_VolumeHair_Candidate_NotAccepted.blend`：236–254局部物理左束，非完整450帧。
- `P/continuous_contact230_display/PPF_VolumeHair_Candidate_NotAccepted.blend`：230–325连续结果截取。
- `E:/project/mmd/work/headswap_xl_codex/contact_repair_20261029/multi_bundle/left_partial_assembled/SelectedBundle_SurfaceCorrective_NotFullyAccepted.blend`：
  旧完整范围候选，仍有115个碰撞失败、97个应变失败；保留作对照，不能称新完成版。
- `P/full_resumed_display/...blend`：后台将来生成的完整左束候选，必须检查实际存在及报告。

## 新对话推荐执行路线

1. 读取本文件和 `docs/VOLUME_HAIR_FEEDBACK_2026-10-30.md`，检查现有后台任务，继续有效工作而非重复长解算。
2. 打开完整旧 MMD 工程／当前修正候选核对场景。诊断脚本会临时隐藏其他头发、生成灰色双人物，
   不要把诊断场景保存成最终工程；恢复完整角色全部部件、真实材质和舞台。
3. 如果当前修正候选已保留原舞台／镜头／材质，优先就地另存完整交付副本。
   若缺失，以旧正常MMD工程为场景母版合入有效修正，勿重复人物／骨架，勿重复应用舞台位移。
   身体NLA、右发束缓存、左新缓存和腕部缓存必须共存，索引选择蒙版各自独立；外部PC2路径要有效。
4. 后台未完成时先做完整画面的关键帧试渲，检查头发、材质、肤色、地面投影、全身构图、眼睛与表情；
   完成后接入经过复查的左束全段结果。其余头发不能隐藏当成已修复，也不应为等全头通用算法而无限拖延成片。
5. 全角色正常材质多角度看关键动作（例如69、175、242、245、256、310、325.75、375、450），
   有明显问题再做针对性修复；正常片和诊断片分开命名。
6. 新目录渲染450帧1920×1080／30fps，合成指定BGM；逐帧PNG校验、MP4全段解码、帧数／分辨率／音视频15秒核对。
   最终交付新 `.blend`、有效缓存、带音乐的正常 `.mp4` 及残留问题说明。
   成片展示完整角色，不是蓝色单发束／灰模／左右诊断。

## 易复发的问题

- VMD导入前必须回第1帧，否则背景停在2637时会把动作导到2637，得到静止预览；不是重新导动作就必然修好。
- 唯一CAMERA VMD没有人物动作；本文件上方列出的是已验证完整人物VMD。
- 原始发片有静置自交；不可直接当合法自碰物理面；代理无穿插不代表显示发片无穿插。
- root必须按真实绑定证据，不要缩小硬根取得通过；保持原始应变参考，不能用变形后形状算“零应变”。
- 稳定插件ZIP与实验源码分开；有些脚本为本角色适配器，不能冒充换角色后一键通用。
- 原生finished标记也可能来自保存退出；必须检查真实最后输出帧达到请求数。
- 当前所有旧原工程和旧成片保留；不要覆盖。不要恢复关机。

补充历史：`progress.md`、`docs/KNOWN_PITFALLS_2026-10-26.md`。
