# MMD Outfit Bridge 0.9（实验版）

2026-10-27 动态接触原型增加 `mmd_outfit.motion_contact`：可检查实际蒙皮表面、给上臂／肘／手腕建立有界避碰修正，并对修正轨迹进行前后帧平滑。它仍是 Python 实验接口，不能称为任意模型一键防穿模。PPF 外部解算器不随插件代码 ZIP 打包。完整来源和验收范围见 `DYNAMIC_CONTACT_RESEARCH_2026-10-27.md`。

Agent 在 Blender MCP 内可直接做只读检查：

```python
from mmd_outfit.motion_contact import audit_current_pose
report = audit_current_pose(
    bpy.data.objects['达妮娅_mesh'], bpy.data.objects['达妮娅_arm'],
    glove_mesh=bpy.data.objects['Cloth'], margin=0.002)
```

对动作的修改须在副本中使用 `skin_regions`、`add_glove_hands`、`ArmContactProjector.capture/solve`，保留原 Action，并在动作变化后使旧 CLOTH／PC2 缓存失效。该接口当前只支持已核对 MMD 名称和分区的上肢修正；衣料反力、连续碰撞保证及通用关节限位尚未成为稳定接口。

2026-10-26 原生扩展快照增加独立丝袜表面、袖子默认下垂更新、上臂权重转移和分区防穿透 API；旧主界面流程保持不变。快照文件为 `mmd_outfit_bridge-0.9.0-native-20261026.zip`，只含代码，不含模型。新增功能在 Blender 5.2.1 实测，运行时修正不能直接导出为 PMX。详细配方、验证边界与 `native_guard.add_skin_guard` 用法见包内 `NATIVE_REPAIR.md`。

Blender 面板、Python API 和 CLI 共用同一后台服务。独立 Blender 进程导入 PMX 并另存结果，当前场景不被清空。0.9 增加默认关闭的试验袖口物理生成，继承 0.8 的袖片静止方向修正、硬鞋保形、平地接地动作及手套覆盖备份。宽袖、飘带等仍有动作穿插，尚未实现任意角色一键无穿模，也未集成 ECF / Wretch。

## 安装与使用

运行 `scripts/build_outfit_addon.py` 生成 `dist/mmd_outfit_bridge-0.9.0.zip`。Blender 4.2+ 的偏好设置 → 插件 → 从磁盘安装 ZIP，启用 **MMD Outfit Bridge**。需要同一 Blender 环境已安装 MMD Tools。侧栏 N → **MMD 换衣**。

1. 选来源角色 PMX、目标素体 PMX、预设和输出目录，点“预检并生成配置”。
2. 成功后自动填入 profile.json。检查其中 selected_materials；可编辑该列表，材质名必须精确匹配。默认排除名称包含头发标记的配件。
3. 点“按配置换衣”。可提供 VMD 进行动作检查。输出每次放在新任务目录。
4. 打开任务目录，查看 result.json、validation.json、preview/ 和 model/。preview 含四个全身视角以及胸口、双手、脚部特写；result.images 列出所有路径，供模型逐张复查。model/work.blend 与 model/model.pmx 为新产物。

`conservative` 不启用角色专用规则。`keqing_daniya` 是本机模型对的实验预设，需要“腿、服、服+jinshu”材质。通用身体遮蔽默认关闭；该预设的闭口鞋模式会明确移除鞋内脚部表面，并在 Blend 中保留隐藏的 `ClosedShoe_FootBackup` 副本。原始输入不改写。设置和移除数量记录在 effective_config.json、target_preparation.json。

Profile 的 target_exclude_materials 明确列出要替换的目标原有服装。刻晴→达妮娅预设排除该输入中的白色躯干衣物“材质”和旧“丝袜”，保留皮肤“Body”；不按名字误删位于头部的“连衣裙通用”。通用预设默认为空，需要按目标实际部件配置。target_preparation.json 记录移除数量。

0.8 新生成的刻晴→达妮娅配置增加 `arm_rest={"method":"anatomical_upper_arm"}`：同侧上臂、腕捩辅助骨和 `袖_` 布料骨链共用肩至肘的刚性静止变换，忽略辅助骨任意的显示轴方向。该变换用于衣服、创建的布料骨和迁移物理，保持尺寸与权重，不改目标已有骨架；adaptations.arm_rest 记录变换及每根骨的差异。旧配置需重新预检才能获得此规则，缺少该字段会沿用原行为。它修复静态适配翻折，不承诺弯肘动态避让；尚有前臂穿袖和飘带交叠。

0.9 可在换衣前勾选“生成袖口物理（试验）”，在 fit 请求中传 `cuff_physics=true`，或 CLI 加 `--cuff-physics`。也可在 profile 中保存同名布尔值，显式请求值优先。默认关闭，仅支持启用物理迁移和上述解剖臂轴规则的 `keqing_daniya` 配置。它识别两侧袖口的布料/金属完整连通层，各生成 8 个碰撞粒子、根部约束和环向约束；将袖口附近的部分上臂权重平滑分配至相邻粒子骨，保留原袖链。两侧合计新增 16 骨、16 刚体、32 关节；顶点位置、拓扑、形态键、鞋子及其他部件不变。

这项功能需要运行物理解算后才显示避让，静态 work.blend、普通 VMD QA 和静态预览不包含碰撞响应。它仍有前臂穿袖和衣层交叠，飘带未新增解算方法，原生 MMD 效果尚待验收。`adaptations.cuff_physics` 记录改权重范围，`validation.cuff_physics` 检查 PMX 重导入后的粒子骨、加权顶点和动态刚体。重复生成或不支持的袖片结构会报错，应从原始输入重新 fit；源码诊断可用 `scripts/outfit_sleeve_contact_review.py --job <任务目录> --out <诊断目录> --frames 61 121 226 256 --physics` 连续推进至末帧并抽查，不等于整段无穿模。

clearance_rules 保存局部适配规则。`radial_order` 在骨骼限定的高度范围内建立角度/高度位移场，同一径向线上不同衣料层获得相同外移量，避免把内外层压到同一表面。超出皮肤参考覆盖范围的顶点保持原位。每条规则记录修正前后间隙与位移上限；数值只检查顶点，不等于三角面或动画无穿插。

surface_patches 用于明确选定的贴肤衣料。`hands` / `legs` 从目标 Body 复制相应表面，继承目标权重、形态键和拓扑，在对应手/腿范围内采样原衣料 UV，保留原材质。include_skin_materials 可显式包括指甲等附属表面；刻晴预设将 Nails 一同覆盖，原指甲保留。腿部可用 lower_offset 调整袜口高度，手腕用 wrist_overlap 将接缝置于袖口内。此方法会改变原贴肤网格拓扑，不适合厚手套、蓬松衣料或必须保留原网格的工作流。UV 最近面采样仍可能拉伸图案、产生接缝；袖口需要看图复核。

0.4 对位置相同的接缝顶点共享外扩位移，避免 UV 拆分处因法线不同而裂开；保留分开的 UV、权重与形态键。手部 UV 采样限制在对应手指或手掌区域，缺失相应来源区域时记录回退面数。胸衣径向位移场补偿分箱衰减，仍保持各衣料层共享同一位移场；仅修正静态控制点间隙，不声明动画无穿插。

0.9 同时修复手套 UV 区域投票使用无序集合处理平票的问题。没有唯一最多票区域的来源面保留在整手参考中，不任意归给某根手指；因此旧版重复生成间可能变化的手套 UV 现在按固定规则采样。该修复独立于袖口物理开关。

0.6 的手部 surface_patches 支持 covered_skin="opaque_backup"，刻晴预设默认启用。仅针对一一对应复制到手套的皮肤面，检查基础、Toon、Sphere 和材质 alpha；基础 UV 整面包围范围及插值邻域都为完全不透明才覆盖，受 UV 形态键影响的面继续保留。移出的皮肤和指甲保存在 Blend 的隐藏 OpaqueGlove_SkinBackup 中，脱离模型父级，不导出 PMX，保留权重、原 UV、全部形态键与原索引。半透明、未知映射、未知着色器及未覆盖区域不处理；丝袜继续保留皮肤。它适用于固定穿着的不透明贴肤手套，不支持自动脱手套或透明度淡出。设为 covered_skin="retain" 并从原始输入重新 fit 可恢复原覆盖方式。skin_coverage 记录处理范围，覆盖后的穿出比例不能与未覆盖版本等同比较；移出的身体点不算通过了穿模测试。

新 UV 图表边界在导出前按 PMX 导出器容差显式拆点，复制全部权重、形态键和法线，避免导出器临时拆点造成回执数量不一致。`uv_seam_split` 记录新增顶点数量；重导入检查仍要求顶点、面和骨骼数量一致。

物理迁移使用 MMD Tools 的排除掩码含义：True 表示禁止碰撞，与 PMX 文件位含义相反。服装组重映射，身体侧的允许/排除关系也同步更新。关节报告区分不属于所选服装的关节与真正缺失的服装端点。物理诊断使用已安装 MMD Tools 的 build_rig，区分模式 1 的变换驱动与模式 2 的仅旋转驱动。0.5 根据全部禁止碰撞对计算距离参数，逐对校验过滤一致；在全新导入的诊断副本上预先记录模式 0 的动画世界变换，再移除残留的静音骨架约束，消除仿真运行阶段的依赖循环。构建阶段仍可能打印临时循环警告；以 PHYSICS_SETUP_READY 后日志为准。代价是省略次级物理对跟随刚体的反馈，具体受影响骨记录在 setup.kinematic_bake.feedback_bones；构建全部排除约束也会增加时间和内存。旧代理不再供 QA 使用，当前结果也不构成原生 MMD 动力学验收。

动作 QA 的 visibility_filter 只排除标准 MMD 基础贴图在面 UV 包围矩形及双线性邻域中均为零 alpha 的面，处理重复 UV；未知着色器、坐标变换、插值和受 UV 形态键影响的面继续保留。模型面数与材质不变，raw_geometry 保存同帧原始计数与独立静态参考。过滤后的比例可能更高；它仍是最近表面符号变化的定位信号，不能直接当作可见穿模证明。异常边长继续检查完整衣料几何，包括透明面。

shoe_fit 的 `preserved_closed_shoe` 从原始来源网格分离整鞋，每侧只进行移动、绕 Z 轴旋转及统一缩放，检查边长比例，避免鞋底和金属饰件被撑扁。刻晴预设 scale=1.2、body_lift=0.012 米：整体抬高目标网格、形态键、骨架及物理定位，根据来源袜腿网格的真实下边界建立鞋口遮蔽场，mask_depth=0.006 米。ankle_rim_scale=0.75 对下脚踝做平滑 XY 收口，至踝骨以上 45 mm 衰减为零，袜层继承此表面；原脚及受影响的脚踝区域都留有副本。鞋子最后合并，每只绑定目标 `足首D.L/R` 单骨，阻止脚趾权重拉坏鞋底。这是闭口鞋替代可见足面的方式，不支持凉鞋、脚趾弯折或自动裸足切换，也不等于完整脚部姿态求解器。副本可恢复几何，不能当作可直接导出的换装开关。

旧 `anatomical_foot_last` 配置明确拒绝执行，需要重新预检。新鞋方法要求关闭旧 fit_limbs、fit_limb_ends、lay_shoe_on_foot、fit_shoe_radius 和 subdivide_shoe；目标袜层要求清空旧 project_layers，冲突会报错。详细变换、原鞋顶点索引、遮蔽数量和保形误差在 adaptation_report.json；所有参数保存在 profile_snapshot.json，供其他模型重复调用。参数目前仅对本机这对资产试验，不保证适合其他鞋型。

0.7 的闭口硬鞋在分离后清除鞋顶点的全部非基础形态键位移，避免表情/体型形态键连带拉坏鞋型；仅作用于鞋顶点，其他身体和服装形态键保留。vertex_morph_lock 记录清除范围，重导入后 validation.preserved_shoes 再检查所有顶点形态键。该硬鞋模式不支持脚趾或鞋型顶点形态键变化。

可选勾选“另存鞋底接地动作”，或在 fit 请求中传 ground_motion=true / CLI 加 --ground-motion。需要提供 VMD 与闭口鞋配置。插件测量动作全部骨骼帧的整鞋最低点，仅为静止的顶层“全ての親”轨道增加平滑的竖直位移，不改腿姿或鞋形。表情、其他骨骼及 VMD 后续段逐字节保留；重新导入生成的动作并逐帧检查高度后才另存 motion/grounded.vmd。返回 effective_motion 和 grounding_report，使用新 PMX 时加载 effective_motion；原 VMD 不覆盖。

当前接地要求动作只有一个第 0 帧顶层根骨关键帧、两只单踝骨硬鞋从该根骨继承，且鞋子没有顶点形态键变形。仅支持 z=0 平地、0.5 mm 间隙、最大 30 mm 抬高，不处理斜坡、脚滑、腿姿重定向或已动画化的根骨。超出条件会明确失败，不静默压平鞋底或改写原动作；此检查不是原生 MMD 动力学验收。

服装骨复制会保留直接加权骨所依赖的完整父骨链，即使中间父骨没有顶点权重。找不到父骨时会明确失败。普通 VMD 检查除身体穿出外，也检查衣面边长相对静态的异常增长；严重拉伸会判 FAILED，避免把爆炸网格当作低穿出率的成功结果。该检查仍只覆盖实际抽样帧。

## 自动化接口

在源码目录将 addon/ 加到 Python 路径；ZIP 安装后也可在 Blender Python 中导入：

```python
from mmd_outfit.jobs import submit

job = submit({
    "action": "inspect",
    "source": "E:/models/source.pmx",
    "target": "E:/models/body.pmx",
    "output_root": "E:/outfit_jobs",
    "preset": "conservative",
}, blender="D:/Blender/blender.exe")
status = job.poll()  # 非阻塞；也可 job.cancel()
```

等待 inspect 完成后，用回执中的 profile 路径提交：

```python
job = submit({
    "action": "fit",
    "profile": "E:/outfit_jobs/<inspect-job>/profile.json",
    "output_root": "E:/outfit_jobs",
    "render": True,
    "timeout": 1800,
}, blender="D:/Blender/blender.exe")
```

提交者需持续调用 poll() 以执行超时检查；`jobs.run()` 提供阻塞封装。CLI 使用 run()，负责轮询与超时。Job 对象只属于启动它的进程，不能跨进程恢复；磁盘上的状态与日志仍保留。

```text
python scripts/outfit_cli.py --blender <blender.exe> --action inspect --source <source.pmx> --target <body.pmx> --output-root <jobs>
python scripts/outfit_cli.py --blender <blender.exe> --action fit --profile <profile.json> --output-root <jobs>
python scripts/outfit_cli.py --blender <blender.exe> --action validate --model <model.pmx> --profile <profile.json> --motion <motion.vmd> --output-root <jobs>
```

也可使用 `--request request.json`。所有输出 JSON 使用 UTF-8。

## 回执与限制

- inspect 完成：COMPLETED，代表配置准备好，不代表适配成功。
- fit/validate 完成且结构检查通过：REVIEW_REQUIRED，ok=true，但 accepted=false。需要人工看图；没有动作时明确标为未检查。
- 输入变更、依赖缺失、未知配置、导出/重导入失败等：FAILED，ok=false。错误有 code/message/stage，日志单独保存。
- 取消或超时：CANCELLED / TIMED_OUT。已写出的中间文件保留，不作为成功产物。
- Profile 对来源和目标 PMX 做 SHA-256 绑定。纹理内容尚未纳入绑定，缺失纹理单独报告。
- 0.4 只支持各一个皮肤网格和骨架、标准共同 MMD 骨名、导入后对象为单位变换。对不支持的布局明确失败。
- 通用预设保留目标原有部件；仅移除 profile.target_exclude_materials 显式列出的材质。身体遮蔽与移除原衣物是独立操作。
- 保留袖口、袜口、鞋型、图案拉伸与宽松衣物的视觉检查要求；本版新增的几何方法仍处于实验阶段。
- 普通 VMD QA 不含 MMD 动力学验收；本版迁移物理数据但不声明动态物理通过。
- 进度为阶段状态；不提供虚假的总百分比。没有续跑检查点，失败后从同一 profile 新建任务重跑。
- 输入资产与贴图只在本机使用；ZIP 不含角色模型、动作、贴图或第三方插件。

2026-10-26 布料试验快照另含 `mesh_cloth.configure(proxy, pin_group, colliders, first=1, last=450)` 与 `hosiery_cleanup.clean(body, stockings)`。前者为明确分区的单层代理添加真实 Blender CLOTH，并拒绝没有固定点的独立衣片；后者移除旧补裆生成分支及不属于丝袜的内部小岛。当前人物分区和 Surface Deform 绑定仍由仓库专用配方处理，未自动集成到旧 fit 按钮。累计问题记录随 ZIP 保存为 `KNOWN_PITFALLS.md`。

2026-10-27 保形扩展提供 `structured_cloth.install(cloth, arm, body, parts, first=1, last=450)`：显式衣片、统一附着骨、物理／版型参考混合、三角坐标视觉传递。需先完成模型分区；仍未接入旧 fit 按钮。完整配方和验证范围见随包 `STRUCTURED_CLOTH_REPAIR_2026-10-27.md`。

动态接触试验新增 `motion_contact.audit_current_pose(body, arm, glove_mesh=cloth, margin=.002)`，检查实际蒙皮后的身体与手套区域；`contact_timeline` 负责加密动作参考与求解器缓存的时间对应。仓库脚本已得到本模型 15 秒身体区域采样通过的动作副本，但改变了部分手势，尚未完成完整衣料层及压力反推动作。此功能仍是 Python 实验接口，旧 fit 按钮不会自动完成动态换衣。PPF 需在本机另行准备，安装包不包含运行时；随包 `DYNAMIC_CONTACT_RESEARCH_2026-10-27.md` 记录经过、失败项与覆盖边界。适配代码的第三方归属见 `THIRD_PARTY_NOTICES.md`。
