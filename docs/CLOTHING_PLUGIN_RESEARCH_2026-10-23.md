# 刻晴服装 → 达妮娅素体：现成工具调查与插件定位

调查日期：2026-10-23。目标是让不同能力的模型都能通过固定接口完成可检查的换衣流程。

## 结论

找到了相关 Blender 插件，也找到了 B 站中文教程与作者演示。因此不宜以“没有相关插件”为由从零重写几何贴合算法。

但本次没有查到**已验证可以直接完成本项目整条链路**的插件：从刻晴成品 PMX 拆衣，适配不同拓扑的达妮娅素体，保留服装专用骨与 MMD 刚体/Joint/Morph，再导出可用 PMX，并通过动作检查。这是证据边界，不代表这样的产品绝对不存在。

建议先对现成工具做同一资产的对照，再决定自研范围。最有价值的自研方向是：**可复用身体对应配置 + 部件策略 + 确定性 API + MMD 数据迁移 + 验收**。模型负责选择和调用，插件承担几何、权重和文件操作。

本轮为检索、官方文档核对和本地已有记录核对；没有购买或安装新软件，没有上传模型，没有新跑换装实验。下文所有产品能力均区分作者说明与本项目实测。

## B 站重点结果

| 工具/教程 | 可确认内容 | 对本项目的意义与限制 |
| --- | --- | --- |
| [Mesh_Deformer 网格变形传递，神马动画imdjs](https://www.bilibili.com/video/BV1384y1g7pr/) | 作者本人说明：外形接近的网格绑定后可以传递变形、权重和 Shape Key，支持不同顶点数；简介附作者下载地址 | 真正的 Blender 插件候选。仍需验证当前 Blender 版本、分区对应和 PMX 数据保留；不能仅凭简介认定整套换装可用 |
| [《装载万物》一键绑定／系列入口](https://www.bilibili.com/video/BV11Q4y1c74g/) | 作者系列列有“装载万物、装载挂件、转移万物、转移挂件”；包含“1.2.0 一键转移，服饰挂件随心换” | 值得核对的中文工具。此链接为一键绑定视频与系列入口，不能把系列标题当作已验证的跨体型适配能力 |
| [MochiFitter 保姆级入门教程](https://www.bilibili.com/video/BV1Qc746MEpe/) | 中文使用教程，简介附产品及转换配置查询入口 | 与“把复杂经验固化，降低使用者门槛”很接近；主要是 VRChat/Unity 生态 |
| [手把手教你做 MochiFitter 对应文件](https://www.bilibili.com/video/BV1xKCZB2EdG/) | 介绍转换配置制作 | 对固定达妮娅素体很有启发：一次建立可靠配置，后续复用；配置制作本身仍需专业工作 |
| [冷门模急救站——Blender 适配衣服](https://www.bilibili.com/video/BV1hXyrY9EEN/) | 作者完整流程包含改外形、整理/合并骨架、传递/修改权重；列有 CATS、Robust Weight Transfer、SKkeeper | 可用作插件应封装哪些步骤的参考。该视频为人工流程，不能当成自动插件；视频所述旧 Blender 环境也不能直接套用当前环境 |
| [数据传递快速绑定衣服](https://www.bilibili.com/video/BV1bC4y1o7Ha/) | 利用 Blender 数据传递修改器复制顶点组 | 解决权重绑定中的一段；不能替代跨体型形状适配 |

核查限制：部分 B 站页面直接读取返回 412；以上依据搜索可读取的页面标题、作者简介和说明文本。未声称逐帧观看所有视频，也未验证网盘包内容。

## 官方来源与其他现成候选

### 1. Elastic Clothing Fit：优先验证的开源几何后端

[官方仓库](https://github.com/VRC-Staples/Elastic-Clothing-Fit)

作者文档列出代理网格贴合、UV 保留、局部顶点组拟合、保护组、距离衰减、凸包代理和实时预览，声明支持 Blender 3.2+，包括 5.x。

适合先测试鞋头、手套、袜层等局部区域。其整网格拟合与距离衰减不能代替服装部件语义，裙摆、喇叭袖、硬金饰仍需分别处理。没有从官方文档确认 PMX 拆衣、SDEF、MMD 刚体/Joint 的端到端迁移。

本地已经存在 `work/ecf/`、`work/poc_ecf.py`、`work/poc_ecf2.py` 及旧调查 `docs/TOOLS.md`。旧记录声称可绕过预览操作器直接调用 pipeline，但也记录了未压实网格造成异常大位移、压实后待重测。本轮读取到的 `_ecf_poc.txt` 只有网格/鞋面提取阶段输出，不能据此宣布鞋部适配成功。

后续集成要固定版本；直接调用下划线函数属于内部接口，应由适配层隔离。当前本地副本含 MCP 自动启动等代码，不能不经比对就当作未修改的官方发布版。

### 2. Wretch AutoFit：直接针对跨体型衣服迁移

[作者官网与完整入门流程](https://wretch3d.com/wretch_autofit/)

作者明确要求来源身体、目标身体、衣服三个对象；支持保存身体配置、解剖标志点、贴身/宽松/硬结构区域、间隙和保留细节，在副本的 Shape Key 上输出。声明 Blender 4.2+，主要面向 Second Life。

这比单纯把衣服吸到目标体表更贴近任务。其身体配置复用值得借鉴。不过页面未证明支持本项目 PMX/MMD 物理链路，实际效果、调用接口和当前版本兼容性需单独验证。

### 3. Robust Weight Transfer：权重后端

[作者仓库](https://github.com/sentfromspacevr/robust-weight-transfer) · [发布页](https://github.com/sentfromspacevr/robust-weight-transfer/releases)

基于 SIGGRAPH Asia 2023 的权重补全工作，用于身体到服装的权重转移。它解决权重问题，不负责把不同体型的衣服形状变成合适尺寸。发布页区分 Blender/Python 依赖版本，不能只下载任意 ZIP 就认定能在当前环境运行。

对 MMD 仍要区分目标皮肤骨、服装专用骨与元数据组，不能用一次全量身体权重覆盖抹掉裙骨、袖骨等。

### 4. ClothingFit：已经大致对齐后的局部修正

[作者仓库](https://github.com/0doxes0/ClothingFit)

作者将其定位为让“已经基本到位”的衣服贴合身体；支持多种投影、软选择和穿插修正。适合局部修整，不能依据该说明期待自动处理大幅体型、姿态或骨架差异。

### 5. MeshDataTransfer：通用数据传递

[Blender 官方扩展页](https://extensions.blender.org/add-ons/mesh-data-transfer/) · [作者文档](https://github.com/maumemoli/blender/blob/master/packages/MeshDataTransfer/documentation/README.md)

支持不同拓扑间的位置/形状、UV、Shape Key 和顶点组传递。它提供数据采样能力；可靠的身体对应、左右肢体分区和服装设计保护仍需建立。

### 6. FitClick：绑定便利工具

[作者产品页](https://superhivemarket.com/products/fitclick)

页面着重说明服装/配件绑定，并要求先大致对齐。适合降低绑骨操作成本，但不能仅凭“One Click”认定它能完成跨体型几何迁移。

### 7. MochiFitter：最值得借鉴的复用配置架构

[当前使用指南](https://mochifitter-guide.mochimochiomochi310.workers.dev/) · [产品页](https://yamirin.booth.pm/items/7657840) · [社区 Blender 部分重构项目](https://github.com/Mega-Gorilla/MochiFitter-BlenderAddon-kai)

当前指南明确：Super MochiFitter 使用附带可执行程序，不需要 Blender；旧 Blender 换装模式计划废弃。来源需逆向配置，目标需正向配置，可通过公共 Template 进行两段转换。指南还包含对变形、穿插、权重和高跟脚型的后续调整。

因此“先做好目标素体配置，其他模型重复调用”是可参考的产品路线；但不能把它误报为当前 Blender 原生 PMX 插件。本次产品页显示 Private，无法确认当前可购状态；也没有确认刻晴逆向配置和达妮娅正向配置的可得性。

### 8. Alterith：另一种跨体型迁移路线

[作者文档](https://planaria.github.io/AlterithDoc/) · [操作流程](https://planaria.github.io/AlterithDoc/tutorial/) · [参数](https://planaria.github.io/AlterithDoc/parameters/)

要求来源角色、目标角色、对应身体与服装，含贴合和可选权重传递。主要服务 VRChat/Unity；本轮未验证 PMX 输出或 MMD 物理保留。

### 9. PmxDressup：MMD 原生对照基线

[作者演示](https://www.youtube.com/watch?v=_4Ikx19ISjA) · [作者发布包](https://bowlroll.net/file/301915)

虽然不是 Blender 插件，但作者说明直接覆盖按骨长和身体厚度适配、材质选择、Morph、骨骼/刚体/Joint 关系调整，是重要的 MMD 对照。没有确认稳定命令行或开放 API，不能直接承诺接入模型自动调用。

### 10. NullFit：备用商业候选

[作者官网](https://nullcorestudio.com/nullfit/)

页面列出跨体型贴合、权重、穿插热图和修复，并提供限额试用。官网明确说明所选身体和服装的几何会发送到服务端计算；不是纯本地方案。本轮没有上传任何资产，也未验证其 MMD 支持。

### 11. 后续扩词新增线索：HoTools / RBF

用户提出“直搜遗漏、刷视频常有新发现”后，使用本地 B 站项目执行 14 组多视角查询。280 条命中去重为 197 条候选；这些数量包含噪声，不等于 197 条已验证知识。

从 `blender 姿态 传递权重`、`blender RBF 服装 适配` 等查询发现 [BV13m5H6DEGe：Blender-HoTools插件-Rbf素体适配服装](https://www.bilibili.com/video/BV13m5H6DEGe)，UP 主空洞hollow。该条未出现在本轮直搜 `MMD 换鞋 高跟鞋` 的前 20 条中。

视频简介指向 [HoTools 作者仓库](https://github.com/HollowAmeChan/HoTools)。已核对仓库公开存在，README 作者名一致，根目录包含 `Rbf`、骨骼、形态键等模块。没有下载、安装或验证它对当前 Blender/PMX 链路的兼容性，不能据此宣称它已解决刻晴到达妮娅的鞋部适配。

同时新增 [FF14 社区 Tpose 权重传递候选](https://www.bilibili.com/video/BV1Vpe2z9EBC)和 [RBF/wrap4d 服饰传递候选](https://www.bilibili.com/video/BV1ecWBzzEqB)。这说明按“前置姿态、迁移机制、工具名、邻近社区”扩词能带来直搜未覆盖的研究入口；目前仍是候选元数据，没有引用未观看视频的操作步骤。

完整扩词实验与项目接口记录：`E:\project\bilibili\docs\SEARCH_EXPLORATION_2026-10-23.md`。通用工具新增多组计划执行、去重、来源追踪和作者过滤，具体领域词由 Agent 根据真实命中提出。

## 为什么现成插件仍不等于本项目已经解决

当前工程已有完整 CLI 框架：拆件、骨骼映射、适配、权重、遮蔽、导出、特写和动作检查。`progress.md` 与审查文件也记录了形态键未同步、骨骼 roll、错误最近面、裙摆被当作贴身层、鞋部网格密度、权重语义与物理代理重复性等问题。

这些说明“全部交给模型现场写脚本与选参数”容易重复踩坑。也说明“有一个贴合按钮”不能覆盖整个任务。旧 QA 数字仅代表旧方法与旧记录，本轮没有复测，不能用它们为任何新插件背书。

## 针对降低模型能力差距的插件规格建议

这部分是设计建议，不是已经实现的接口。

1. **身体配置一次建立、重复使用。** 达妮娅配置记录骨骼语义、单位/坐标、左右肢体域、关节标志点、皮肤材质与脚型状态；源身体对应关系同样保存并校验。
2. **衣服按策略处理。** 手套/袜层走受限贴合与目标皮肤权重；裙摆/喇叭袖保留体积和专用骨；金饰走刚性或近刚性随动；高跟鞋单独校准脚型与鞋底。
3. **人和模型使用同一核心。** Blender 面板、Python API、后台 JSON 入口调用相同服务，避免把鼠标位置、当前选择、活动窗口和对 UI 的理解能力作为成功前提。
4. **固定输入输出。** 输入源/目标、服装清单、身体配置和策略；输出独立版本的 Blend/PMX、部件映射、变更报告与截图。缺少可靠对应时报告具体部位，避免静默跳过。
5. **流程可重入、可回滚。** 每阶段存档、超时与失败分类；重复请求不累积修改器、灯、骨骼和刚体；保留原模型及 Morph。
6. **验收可检查。** 每部件检查几何、UV、Shape Key、权重、骨架与刚体引用；固定姿态和真实 VMD 输出多视角证据。遮蔽身体和修复服装应分别报告，避免靠扩大遮蔽掩盖衣服未适配。

可考虑的少量服务动作是 `inspect`、`prepare_profile`、`fit`、`validate`、`export`。不要让调用模型先在大量 Blender 操作器中猜正确顺序。

## 选型顺序与停止条件

1. 用同一组“刻晴手套、鞋、袖子、裙摆 → 达妮娅”测试 ECF；如果可获取，再测试 Wretch AutoFit。保持其他步骤一致，按部件比较结果。
2. 以 PmxDressup 作为 MMD 完整换装对照，辨别问题属于几何、权重还是 MMD 数据迁移。
3. 可复用现成后端的环节只写适配层；确认现成工具无法承担的部分再自研。不把尚未验证的商业宣传当作通过。
4. 插件封装完成后，让另一个模型只用文档与固定接口在干净场景重复运行。成功标准是能完成同样产物并准确报告失败位置，过程中不需要为它临时补 Python。
5. 一套衣服成功后增加第二套源角色服装做留出验证，避免仅对刻晴材质名和骨名硬编码。

建议结论：**复用已有几何能力，重点开发固定配置与可验收的 MMD 换装服务层。** 本次没有完成新插件，也没有把已有实验判为已完成的通用方案。
