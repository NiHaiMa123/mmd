# 可下载毛发项目与参数说明：实际获取情况

用户要求查找他人的可下载项目或参数说明。本轮只研究、下载公开资料和只读检查，没有改变当前角色物理，没有安装新插件，没有模拟或渲染。当前仍先看惯性/回摆/重力，不以穿模驱动物理加硬。

资料目录：`E:/project/mmd/work/hair_reference_projects_20261102`。

## 对现有Jiggle最直接的资料

### 作者Hair预设与实际参数定义

- [Jiggle作者仓库](https://github.com/naelstrof/blender-jiggle-physics)
- [Hair.py](https://github.com/naelstrof/blender-jiggle-physics/blob/792db09a22cd5c7dc5b5c1b4eb0ea12c4af3e6b1/presets/jigglebones/Hair.py)
- [同版本源码](https://github.com/naelstrof/blender-jiggle-physics/blob/792db09a22cd5c7dc5b5c1b4eb0ea12c4af3e6b1/__init__.py)
- 当前已用commit对应作者v4.5.3、Blender5.2兼容发布，不是本轮下载后升级。

已读作者文档、预设和相关源码，并保存参考副本。作者仓库当前文件/预设目录未发现可直接下载的完整角色演示.blend；不能把插件包当角色工程。

| 当前插件字段 | 实际作用 | 作者Hair默认值 |
|---|---|---:|
| Root Elasticity | 链起点向动画位置附着的强度，和冻结整段骨不同 | 0.9 |
| Length Elasticity | 维持段长、抵抗伸长，不是弯曲柔顺度 | 0.9 |
| Angle Elasticity | 向原始相对形状恢复的角度弹性 | 0.7 |
| Elasticity Soften | 在接近目标姿态时减弱恢复作用 | 0.6 |
| Gravity | 场景重力的倍率 | 0.25 |
| Air Drag | 整体移动响应及拖尾中的衰减项 | 0.2 |
| Friction | 内部相对运动的衰减，抑制余摆 | 0.5 |
| Blend | 原动画与物理解算输出的混合 | 1.0 |

作者预设为已含重力造型的头发使用较低gravity，并主动压制持续振荡。当前项目额外把root/length设为1，并冻结每链前两根骨；**冻结前两骨不是该预设的内容，是本项目添加的策略**。前轮已测得18束后发对应约14–16cm/骨链约40%的固定区。后续若改根部，应先用作者的起点附着机制做同输入对照，而不是再凭数量冻结两整段。

同名参数不能跨后端照抄：这里的Friction是内部衰减；Bone Physics文档中的Friction指表面接触摩擦。Hair.py注释提及减少Blend，但实际代码值为1.0，复核以代码为准。当前步频依赖仍按`HAIR_WORKFLOW_AUDIT_2026-11-02.md`和时间对照记录理解。

## 参数讲解比较完整的其他作者文档

| 文档 | 已核实内容 | 使用边界 |
|---|---|---|
| [Wiggle 2 RTX作者指南](https://mayalhc.github.io/Wiggle2-RTX/) | v2.4.0说明Stiff/Damp Root–Tip渐变、头/尾设置、角度限制、缓存和烘焙。明确提示Safety Guard过强可使运动变硬。 | 同家族其他求解器，不等于当前Jiggle，参数值不可直接迁移。未安装。 |
| [Wobbly Wiggler作者文档](https://joseconseco.github.io/wobbly_wiggler_docs/) | 质量/刚度与振荡频率的关系，重力随链长度的处理、最大角、混合与烘焙；有参数变化演示。 | 当前文档要求Blender5.2+；没有购买或安装插件，没有声称相同数值适用。 |
| [Bone Physics刚体参数](https://zhang0xf.github.io/bonephysics-docs/en/rigidbody.html)及[关节参数](https://zhang0xf.github.io/bonephysics-docs/en/joint.html) | 质量/转动惯性、线/角阻尼、弹簧和关节限制的说明。 | 使用Blender刚体，README主要测试4.2，未充分验证新版本；不是当前Jiggle接口。 |
| [XPBD-Hair参数指南](https://github.com/ysk424/xpbd-hair/blob/main/PARAMETERS.md) | 当前0.2.2文档写清g/m线密度、N/m刚度、按dt处理阻尼、曲线点约束及根区等。 | Curves输入、独立后端；只读文档，未安装/编译，不据此宣布替换当前方案。 |

## 可取得的完整毛发动态项目

### TressFX-Godot：马尾场景与公开调参配方

- [项目仓库](https://github.com/ismailivanov/TressFX-Godot)
- [作者Tuning说明](https://github.com/ismailivanov/TressFX-Godot/blob/main/docs/Tuning.md)
- [实际马尾场景](https://github.com/ismailivanov/TressFX-Godot/blob/main/addons/tressfx/demo/ponytail.tscn)
- [Blender导出流程及源文件说明](https://github.com/ismailivanov/TressFX-Godot/blob/main/docs/Blender.md)

已通过GitHub连接器读取作者文档和场景。马尾场景将头皮和马尾分成两个物理节点，实际文件对应：

| 区域 | global_stiffness | global_range | local_stiffness | damping | gravity | vsp_coeff |
|---|---:|---:|---:|---:|---:|---|
| 头皮部分 | 0.3 | 0.4 | 0.4 | 0.2 | 1.0 | 沿用默认 |
| 自由马尾 | 0.06 | 0.2 | 0.35 | 0.1 | 1.5 | 0.25 |

作者把发型保持、局部弯曲、根部刚性运动传递和阻尼分开解释，针对长直发、马尾和短竖发分别给配方。重要的是**不同区域的恢复程度不同，而不是把整段全部钉死**。global_range描述恢复原发型的影响范围，不等同于当前禁用发骨的固定长度；这些数值也不能直接填到Jiggle。

项目本身可下载，物理运行在Godot。马尾美术源包含Maya文件、FBX和.tfx。另有一个Blender制作的短竖发示例：本轮已下载并校验它的`blender_hair.blend`，2,300,712字节、SHA256 `f66e46005f25179c7c334e373dfd67e517d88fa3071f7946aff0bf5114e3efb7`，只读打开看到3个Mesh和1个Curves，无Armature。**这个.blend是短竖发美术源，不是上述长马尾模型，也不是Blender内运行的Jiggle工程。**

`TressFX_ponytail_author.tscn`、`TressFX_Tuning_author.md`保存场景及说明；`TressFX_demo_LICENSE.txt`记录头部扫描的CC BY3.0署名要求。没有安装Godot或复跑其动态，不能声称已经验证自然度/稳定性。

### Scthe Unity Hair：Sintel角色与多个发型

- [完整项目](https://github.com/Scthe/unity-hair)
- [作者文章](https://www.sctheblog.com/blog/unity-hair/)
- 作者说明其使用Unity官方`com.unity.demoteam.hair`，包含Sintel及多个Blender发型、Mixamo动作和SDF碰撞场景。

已读取README，实际下载Git LFS中的`unity-hair.blend`，27,850,433字节；SHA256 `2a32f792a27beb8a85cb0be52bbcdc0970b6fcafc1fe31f7f808610166f32e57`与仓库LFS指针一致。普通Git源码中的133字节文件只是LFS指针，不能当成.blend直接打开。

只读打开源文件，包含2个Armature、3个Curves、97个Mesh和7个粒子系统；7个粒子系统`use_hair_dynamics`均为False。这与作者的“Blender制作/导出，Unity运行动态”一致。作者另说明部分大型Hair Asset未入库，需按教程从Alembic生成并重新关联；不是下载后无需任何准备即可播放的包。

本轮没有执行其内置`sintel_rig_props.py`或其他Text，没有启用不明驱动，也没有启动Unity。文件仍可用来研究实际发型、骨架和导出结构；不能宣称已在当前Blender复现其模拟。项目含不同来源的素材，遵守各子目录署名和许可说明。

## 其他线索的真实状态

- **Sextet人物工程**：索引描述提供Actor3.0两个年代的链接，另有作者CC0发布说明。第一条独立文件主机请求返回403，已停止该主机请求，第二条同主机链接未继续尝试。作者原站`characters`页面返回404。本轮未取得其可复跑的头发物理文件；不能将“有下载链接”写成“已经下载并验证”。已读的视频参数证据仍见此前社区研究记录。
- **Blender Secrets Hair Monster**：[作者页面](https://www.3dsecrets.com/secrets/hair-dynamics)提供Google Drive的`20200611 Hair Monster v2.blend`链接。当前工具只读到文件标题/登录入口，未验证能否直接取得，没有宣称必须登录或文件失效。
- **Wiggle2社区附件**：[2023年作者讨论帖](https://blenderartists.org/t/wiggle-2/1454788?page=6)中有78KB的`.blend`。已下载79,826字节，SHA256 `1dfa3b72f790e39ece393ebe0eb620b7d4961b198e8721a5ef8e167591fa9f7d`。只读看到`working`和`not working`两个两骨架例，动态骨tail开启、根骨关闭，刚度0。它是旧版轴向翻转的故障对照，**不是长发自然度样板**，不能用它的0刚度作为当前角色推荐值。
- 本轮B站页面请求返回412后停止平台请求，没有继续调用B站API/下载器。搜索索引描述只作作者链接线索，没有将其当成新观看的视频内容。Blender官方站的部分工具读取返回402，未将其描述成付费内容，也未绕过访问失败。

## 当前适用的下一步

继续现有Blender/Jiggle时，优先按照作者参数语义重新验证根部附着和弯曲起点；不要把本项目额外冻结两骨视为官方流程。RTX/Wobbly文档提供根梢差异化与阻尼的设计参考；Godot/Unity工程提供另一类完整动态链路作比较。**没有找到已经下载、能在当前Jiggle中直接复跑、且自然度已验证的完整角色范例**，不能捏造这种复刻基础。

实际文件、哈希、结构与失败记录分别在`downloads.json`、`source_blend_downloads.json`、`blend_inspection.json`。三份下载.blend均在`--disable-autoexec`、`use_scripts=False`下只读打开并核对源哈希未变。当前角色、缓存和已出视频均未改动。
