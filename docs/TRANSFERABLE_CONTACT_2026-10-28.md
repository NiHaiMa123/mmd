# 可迁移的动画接触工具：2026-10-28

新增后续结果：[原生曲线与单束测试](NATIVE_HAIR_CURVES_2026-10-28.md)。最新插件 0.1.2，曲线基准两次独立复测通过；真实单束已改善，仍有右手接触短段未通过。下文保留前阶段身体／头发试验范围。

本轮基于东雪莲头／达妮娅干净素体的 15 秒工程，实现独立检测与普通上肢修正工具。**完整身体及头发尚未验收通过，不能称为整套穿模已解决。** 原固定镜头 1080p 成片与原工程保留，未覆盖为失败的物理候选。

最新头发记录见 [头发测试](HAIR_CONTACT_TESTS_2026-10-28.md)。插件已更新 0.1.1；下文旧 Bullet 数字对应的工程缺失物理世界刚体集合，相关动态对照结论作废。修复后真实连续 450 帧、独立身体表面碰撞对照仍未通过。低应变首帧身体交线可清零，但整段有尖片和穿插。最新状态以 `hair_tests_v2/acceptance.json` 为准。

## 可复用交付

- Blender 独立插件：`E:/project/mmd/mmd_repo/dist/animation_contact_tools-0.1.1.zip`。侧栏“动画接触”，面分类、映射导出、当前帧检测、后台全段检测与普通手臂实验修正；头发入口仍为显式实验。
- 可移植技能包：`E:/project/mmd/mmd_repo/dist/repair-animation-contact-skill.zip`。
- 技能源：`E:/project/mmd/mmd_repo/skills/repair-animation-contact/SKILL.md`，另已安装至 `C:/Users/Administrator/.codex/skills/repair-animation-contact/SKILL.md`。包含独立插件 ZIP、CLI、配置格式、算法／验收与头发后端说明；不依赖本模型路径。
- 核心：`addon/animation_contact_tools/`。`surface.py` 检测，`projector.py` 旋转投影，`track.py` 独立 NLA 层，`adaptive.py` 子帧修正，`worker.py` 通用入口。头发／腿 IK／局部皮肤模块均为未验收实验，不由默认 UI 启用。

迁移实测：无 MMD 插件的英文六骨骼模型，手／头交线 20→0；完整包含反例检测 42 个内部样本；世界坐标按厘米缩放后检测与修正仍通过。打包后 CLI 解包独立 ZIP，另跑 8 帧，累计 160→0，原主骨矩阵差 0。证据：`outputs/portable_contact_contract/`。这证明接口与包装可用，不代表任意骨架一键适配。

## 当前实际结果

所有工作产物位于 `E:/project/mmd/work/headswap_xl_codex/contact_repair_20261028/`。

| 范围 | 实测与结论 |
|---|---|
| 手臂／手扫过头、躯干 | 原检测配对中，整帧累计交线从 66,759 降为 0；全段 1,797 个四分之一帧采样通过。不是独立穿模事件数量，也不是全身通过。 |
| 第 361 帧上臂／躯干残留 | 20°／25° 约束下未解，限定 30° 并做局部多起点，在 1/8 帧采样上消除；最大角度及动作跳变需单列复查。 |
| 扩大到 28 个身体区域配对 | 新发现同侧腕／前臂及髋部／躯干交线。没有因旧检测没覆盖而忽略它们。 |
| 腕部折叠 | 整段修正后，1797 个采样中上肢仅余 22 个失败样本，全部在第 250.25–255.75 帧进入抱手保护的影响渐变区；普通腕折叠其余已消除。未扩大保护窗口掩盖过渡问题。 |
| 髋部折叠 | 双四元数、Corrective Smooth、4 厘米水平足 IK、8 毫米局部皮肤投影均未通过；部分方法新增拉伸。未应用到正式候选。 |
| 抱手 | 原动作第 256–321 帧为本例保护窗口；保留原接触，修正层影响为 0。该窗口不是通用帧号。窗口外双侧碰撞仍需检测，不能全程忽略左右手。 |
| 头发 | 旧 Bullet 动态对照因空物理世界作废。有效 Bullet 与身体表面碰撞试验仍失败；新低应变首帧身体交线 442→0，但 35 姿势仅 12 个目标交线为零，中段有尖片，未通过。 |

`body_track/BodyContact_FinalCandidate.blend` 仅表示原上肢扫碰阶段候选。`final_body_audit.json` 是旧配对通过记录；扩大范围后的真实状态以 `independent_validation.json` 为准。不能拿文件名 FinalCandidate 或旧报告代替全身验收。

最新工程为 `body_track/BodyContact_UpperBodyCandidate.blend`，报告 `upper_body_independent_validation.json`：28 对、1797 样本、0 未映射；还剩上述 22 个上肢过渡样本以及 582 个有髋部交线的样本，全身状态 BODY_UNRESOLVED。头／躯干／足骨矩阵、保护窗口的完整网格与头发网格差均为 0；原 Action、形态键、拓扑及权重与源工程一致，见 `upper_body_source_integrity.json`。

完整并排诊断预览为根目录 `UpperBody_Contact_Comparison_1080p_15s.mp4`，左原动作、右局部修正，原生每侧 960×1080，合计 1920×1080、30 fps、450 帧、15 秒，带原 BGM。尺寸、帧数、时长及全段解码通过，并查看编码后的关键帧；它是灰模诊断预览，未覆盖正式材质成片。正侧背高清图在 `review_upper_body/`。

原始 Action、231 个形态键坐标、68,272 顶点、118,585 面拓扑与权重哈希均与源工程一致，见 `body_track/source_integrity.json`。上肢阶段头／躯干／足骨矩阵差 0，保护段和头发求值网格差 0。原上肢层最大修正帧差约 12.72°，尚需轨迹平滑／动作自然度验收；交线通过不能替代动作质量通过。

## 具体实施路径

1. **语义适配**：显式 FACE 属性分类真实表面，按骨权重映射区域；辅助骨继承最近祖先，混合面保留。不得依据高度排除长发，或让未映射的臀／髋辅助骨退出检测。
2. **接触分类**：主骨稳定、普通肢体避让、有意接触保护分别配置。邻接关节折叠独立比较 REST／POSE，避免把 LBS 折叠当成两个远距离肢体扫碰。
3. **普通运动修正**：实际蒙皮有限差分雅可比、带阻尼投影、受限角度和每步信赖域；可选择腕朝向补偿或有限释放。原 Action 保留，输出 NLA 四元数偏移层。
4. **时间约束**：平滑后重投影，失败子帧加键；独立检测扩大配对。当前已有局部多起点与离散自适应，仍需更强的速度／加速度约束及连续检查，防止碰撞修正突跳。
5. **关节形态与头发**：髋部需接触约束结合局部关节形态／权重适配；不能无限改落脚或平滑皮肤。头发先获得合法初态、精确附着区，再做带伸长／弯曲约束的发片或细杆接触，最后验真实发片而非刚体。
6. **验收**：未映射面、忽略面、配对覆盖、完全包含、采样盲区、主骨、保护动作、拉伸和视觉自然度分别列出。没有全局无穿插保证时明确报告。

## 已遇到的坑

- 只检查旧区域配对，会漏掉同侧手／前臂、手／腿及髋／躯干；已扩展为 28 对。solver 无能力修正的配对继续报告未解决。
- 28 对仍是区域间检测，不包含同手手指或同腿内部自交；插件提供可选 self_collision_regions，当前整段案例未据此作通过声明。
- 只取三个顶点一致归属的三角形会漏掉混合面；辅助骨缺映射曾漏 6,234 个身体三角形，已修正为 0 未映射。
- 只有三角交线不能发现完全包含。闭合区域另查内部点；本模型语义分区多为开口，不能声称包含检验完备。
- 初始旋转偏移也必须限制；只限制每次更新会让多起点超上限。本漏洞已修正，并在通用骨架上验证。
- NLA 浮点规范化会有微米量级差异，应记录容差；源动作、网格和形态键仍须比较，不能以“浮点误差”解释可见变形。
- 保护一个抱手段，不代表全程忽略双侧手臂。默认 protected_pairs 已改为空，意图通常用 protected_windows。
- 修正层进出保护段的线性渐变会重新引入原始穿插；解算后的完整偏移通过，不代表乘上影响系数后仍通过。当前第 250–256 帧正是此类过渡失败，保留在验收中；需要带接触阶段的轨迹约束，不能通过扩大窗口假装解决。
- 代理刚体、骨头尾避碰和骨长保持不证明实际发片无交线或无拉伸。
- 关节平滑与双四元数是变形方法，不是接触保证；本例真实测试失败，未保留为正式修复。
- Windows 的 Python 默认编码会把中文技能元数据写成 GBK 或使验证器解码失败。技能文件统一 UTF-8，验证使用 `python -X utf8`。

## 参考实现与边界

[TrajOpt](https://rll.berkeley.edu/trajopt/doc/sphinx_build/html/)提供轨迹优化与连续约束思路；本插件并非完整 TrajOpt。[JAX-IK](https://github.com/hvoss-tech/JAX-IK)有 SDF 自碰接口，尚未本地适配。Blender 官方的[Armature Preserve Volume](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html)与[Corrective Smooth](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/corrective_smooth.html)说明关节变形方法；不能由其功能推断无穿模。

[SMPLify-X 碰撞损失接口](https://github.com/vchoutas/smplify-x/blob/master/smplifyx/fitting.py)、[torch-mesh-isect](https://github.com/vchoutas/torch-mesh-isect)可供研究碰撞损失，相关专门许可代码未复制或捆绑。头发可适配 [MMD Tools](https://github.com/MMD-Blender/blender_mmd_tools)、[Wiggle 2](https://github.com/shteeve3d/blender-wiggle-2)、[Bone Physics](https://zhang0xf.github.io/bonephysics-docs/en/)；[IPC](https://github.com/IPC-Sim/IPC)是强接触求解底座，需合法初态、表面代理和动画接口，不是直接修复任意 MMD 的成品按钮。
