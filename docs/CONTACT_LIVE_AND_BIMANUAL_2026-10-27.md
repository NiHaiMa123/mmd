# 实时关节、随动双层衣料与双手接触回归

完整角色系统仍未完成。本轮解决了旧数值底座的实时错位，并通过两类不同的简化接触用例；没有把旧抱拳候选改写成通过。根验收：`outputs/contact_stack/acceptance.json`。

## 实时状态顺序修正

旧 `joint_axis_sync_v1` 只能导出同一时刻的正确骨骼输出，原实时骨架仍穿衣。旧目录与失败记录保留。

在 Genesis 1.4.5 / pyuipc 0.0.29 的实际安装源码中，IPC 路径先解接触，刚体 post-coupling 又执行一次 `substep`，暴露了下一时刻的预测骨架。本次实例级适配改成：电机预测 → 原生接触 → 从相同原生状态恢复关节位置与速度，不在接触后再次积分。未修改第三方安装文件。

`live_joint_feedback_v2` 的原始实时 Genesis 姿态通过：91 个采样，身体／衣料、衣料自碰和层间交叉均为 0；实际骨骼与原生物理体最大偏差 2.762 微米，26 个世界固定点误差 0。有／无衣料最大关节差约 0.52949 rad，证明衣料确实影响动作。适配拒绝未验证的多环境、自由基座、非转动关节、混合动态求解器和梯度模式。

## 头部优先、手臂避让、双层随动衣料

`two_link_head_cloth_v2`：固定头部球体和躯干，肩／肘两个转动关节，两层各 121 点衣料。四个原生 SoftVertexStitch 将根部连接到运动前臂；无世界固定点，无接触豁免。缝接保持初始距离，允许转动，不能解释成刚性保持三维偏移。

使用 SciPy SLSQP 调整目标轨迹，加入关节界限、头部间隙与时间平滑。该规划器只处理偶然扫碰，显式拒绝 `--intent intentional`，不能拿来拆开抱拳；它也不是已经实现的通用沿表面滑动算法。

- 原目标最小头部解析间隙 −127.76 mm，50 个采样存在手臂／头交叉。
- 新目标最小间隙约 8.00 mm，实际解算后最小解析间隙约 10.93 mm。
- 151 个采样：手臂／头、手臂／躯干、上臂／前臂、身体／衣料、主体／衣料、自碰、层间交叉均为 0。
- 头和躯干位移 0，关节越界 0；实际／原生角点最大差 1.710 微米。
- 四附着点最大距离误差 15.04 微米，点自身运动约 8.96–12.23 cm，确认附着跟随运动。

独立 Blender 三角检查见目录 `surface_audit.json`。这是离散简化表面检查，不等于完整 MMD 或连续碰撞证明；实际球面网格与解析球判据分别记录。

## 双手接触：共同移动，保持相对姿态

`bimanual_v3`：两条肩／肘／腕链，共六个转动关节。原生 AffineBodyFixedJoint 在预先声明的持续接触阶段保持两手相对位置和朝向；肢体电机允许偏离独立目标。全部物理体碰撞保持开启，没有删身体来过关。

输入含可行的双手共同抬起轨迹，以及故意冲突的独立关节目标。无约束／有约束使用相同目标和驱动参数。

| 指标 | 无双手约束 | 有双手约束 |
|---|---:|---:|
| 相对手位置最大偏离 | 85.89 mm | 0.2951 mm |
| 相对手朝向最大偏离 | 0.01612 rad | 数值精度内 0 |
| 双手中心共同位移 | 84.57 mm | 41.01 mm |
| 三角交叉采样 | 0/151 | 0/151 |
| 凸包内部重叠采样 | 0/151 | 0/151 |
| 实际骨架／原生表面最大差 | 2.438 微米 | 182.77 微米 |

固定躯干位移、关节越界均为 0。独立检查同时采用三角交线和完整 OBB 分离轴，避免漏掉完全包进另一个实体的情况。

`bimanual_v1`、`bimanual_v2` 的共同运动太小，未作为通过结果；v3 提高双方一致的驱动力后才通过位移大于 2 cm 的验收。固定相对姿态会减少运动自由度、牺牲独立电机跟随，不能应用到整段动作或允许滚动的所有接触。

这是预先声明的持续接触回归，没有手指、真实拳掌表面、进入／退出阶段、接触滚动或自动语义识别；未修复真实角色抱拳。

## 可查看产物与复现

- `outputs/contact_stack/bimanual_v3/Bimanual_Contact_Probe.blend`：实际六骨骼驱动，两组对照，默认显示接触组，骨架隐藏。
- 同目录 `Bimanual_Contact_1080p.mp4`：1920×1080、151 帧、30 fps；1.5 秒仿真慢放约 5.03 秒，无音轨，标注简化用例。
- 骨骼保存重开随机读 1/51/101/151 帧，最大坐标差约 8.415e-8 m；视频尺寸、帧数和完整解码通过。已检查两组末帧。

仓库根使用隔离 Python，替换输出目录避免覆盖已有证据：

```powershell
& tools/contact_stack/venv/Scripts/python.exe scripts/probe_articulated_contact.py --output outputs/contact_stack/new_head_case --plan --cloth
& tools/contact_stack/venv/Scripts/python.exe scripts/probe_bimanual_contact.py --output outputs/contact_stack/new_hands/free --steps 150
& tools/contact_stack/venv/Scripts/python.exe scripts/probe_bimanual_contact.py --output outputs/contact_stack/new_hands/contact --contact --steps 150
```

然后用 Blender 后台和 `--python-exit-code 1` 分别运行 `audit_articulated_contact.py -- --input <head_case>`、`audit_bimanual_contact.py -- --input <hands>`；通过后运行 `preview_bimanual_contact.py -- --input <hands> --render-all`，最后隔离 Python 执行 `encode_bimanual_contact.py --input <hands>`。根验收由 `summarize_contact_regressions.py` 汇总。

## 真实角色仍需接入

MMD 肩腕为多轴旋转，根骨可移动；当前安装版本的 Genesis external articulation 建立器仅接受固定、棱柱、转动关节，本次恢复器进一步限定固定基座转动链。须先解决多轴／自由根骨映射和实际蒙皮反馈，再在原角色接触窗口验证拳掌朝向、手指、交叉次序和动作节奏。随后才是所有衣料层联合解算、空间不足反推动作与完整 15 秒多角度验收。

本轮未更新插件 ZIP，未将实验适配接到旧 fit 按钮。原模型、原动作和用户 Blender 窗口未覆盖。
