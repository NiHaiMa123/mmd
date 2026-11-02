# 右臂与单束头发反馈：局部采样通过

本轮把第 217–220 帧压住固定发根的右手／前臂改成避让路径，再重新运行原生 Hair Dynamics。第 200–250 帧这一束实际发片的 201 个四分之一帧采样无交线。完整头发、头发自碰、髋部和进入抱手段的旧问题尚未解决，原成片未覆盖。

工作目录：`E:/project/mmd/work/headswap_xl_codex/contact_repair_20261028/hair_arm_feedback_20261028/`。

## 成果与代价

| 项目 | 实测 |
|---|---|
| 发束 | 右侧 Sidetail 独立连通分量，1,095 点／1,642 三角形 |
| 发片采样 | 200–250 帧，步长 0.25，共 201 个；交线失败 0 |
| 发片边长比 | 0.948630–1.063312，仍有约 -5.1%～+6.3% 的局部变形 |
| 发根插值误差 | 0.000586mm 以下 |
| 缓存重开误差 | 0.000239mm 以下 |
| 身体修正区间 | 212–228 帧，四分之一帧关键帧，仅右臂链 REPLACE NLA |
| 手腕位置最大改动 | **12.5cm**；不是微小动作修正 |
| 局部旋转最大偏移 | 上臂 27.27°、肘 24.91°、腕 42.43°；腕主要补偿父骨变化 |
| 手腕世界朝向最大误差 | 1.77°，末端另有不超过 5° 的局部避碰微调 |
| 右臂／身体独立复查 | 八分之一帧，修正区间失败 0；不代表身体全部配对通过 |
| 主骨／未受影响蒙皮／区间外误差 | 0 |
| 原 Actions | 8 个摘要全部一致；没有改原关键帧 |
| 抱手保护 | 256–321 不覆盖；另测 256／285／321 完整网格误差 0 |

工程：`guarded_bundle/SingleBundle_CachedCandidate_NotAccepted.blend`，同目录的 `SingleBundle_MeasuredMotion.pc2` 必须保留。文件名中的 NotAccepted 指整个人物尚未验收，局部采样结果见 `guarded_bundle/independent_validation.json`。原生实时求解工程不包含可直接乱序播放的已持久物理结果，审查用上述缓存版。

1080p 对照：`Arm_Hair_Contact_Comparison_1080p.mp4`，1920×1080／30fps／153 帧／5.1 秒，**三倍慢放**，对应源 200–250 帧约 1.7 秒。左为上一轮单束，右为本轮动作反馈加重新解算；只显示该束、皮肤和头部，其他头发为诊断可读性隐藏，不据此宣称其他发束通过。18 张正／侧／斜角静帧在 `review1080/`；已查看关键接触、后段擦过与连续过渡图，以及编码后的画面。手与发束分离，未见此前的根部尖片；动作改幅较大，不能仅凭几张图判为最终自然度通过。

## 算法与复现

通用代码位于 `addon/animation_contact_tools/`：

1. `two_bone_contact_path.py`：解析双骨 IK，长度不变，保留手腕世界朝向，显式保持局部 location／scale。
2. `arm_detour_planner.py`：采样手腕偏移与肘平面方向，按实际蒙皮身体／发根包络筛选；先最小化峰值修正速度，再最小化路径代价。PCHIP 连接只产生候选，仍查子帧。
3. `projector.FrameProjector`：有限差分蒙皮雅可比，限角腕部避碰微调。
4. `native_hair_curves.py`、`skin_collision_cage.py`、`strand_binding.py`：原生 XPBD 曲线、闭合皮肤外壳、真实宽发片映射。本次体素 3mm，接触余量 6mm，60 子步／200 次约束，弯曲 0.005、根部弯曲 0.6。
5. `hair_position_cache.py`：保存骨局部坐标并跟随精确附着骨矩阵，避免世界坐标线性插值导致帧间发根漂移。

本角色包装脚本：`plan_bundle_arm_route.py`、`select_cached_arm_route.py`、`bake_arm_detour.py --tag baked_polished`、`verify_arm_detour_source.py`；随后 `probe_native_single_bundle.py` 指向新身体工程，配合本次 `--voxel-size 0.003 --contact-margin 0.006` 等实际报告参数，最后 `verify_native_bundle_candidate.py --run <guarded_bundle> --step .25 --head-local`。源工程、输入包络、候选节点、烘焙路径及逐样本报告均保留。不要对旧目录盲目重跑覆盖证据。

这些包装脚本仍有角色名和本机路径；可迁移核心不依赖这些名字。新反馈分支尚未接入通用 CLI／侧栏的一键按钮，当前交付是可配置模块与技能步骤，不能说只安装插件就自动处理全部头发。迁移入口见 [技能参考](../skills/repair-animation-contact/references/arm-hair-feedback.md)。

使用已保存的身体修正工程，在**新目录**复测本次头发参数：

```powershell
$caseRoot = 'E:\project\mmd\work\headswap_xl_codex\contact_repair_20261028\hair_arm_feedback_20261028'
$replayOut = Join-Path $caseRoot 'guarded_bundle_replay_001'
& 'D:\software\blender\5.2.1\blender.exe' --factory-startup -b -t 4 --python-exit-code 1 --python 'E:\project\mmd\mmd_repo\scripts\probe_native_single_bundle.py' -- --source "$caseRoot\baked_polished\Body_With_ArmDetour.blend" --out $replayOut --first 200 --last 250 --mesh-guide --skin-cage --rod-frames --voxel-size .003 --contact-margin .006 --bendiness .005 --root-bendiness .6
& 'D:\software\blender\5.2.1\blender.exe' --factory-startup -b -t 4 --python-exit-code 1 --python 'E:\project\mmd\mmd_repo\scripts\verify_native_bundle_candidate.py' -- --run $replayOut --step .25 --head-local
```

以上是此角色的复现命令，不是通用角色 CLI；适配其他人物先按技能参考准备映射、发束和合法初态。改变起始帧会改变零初速初态，应作为新实验重新验收。

新测试 `blender_arm_route_contract.py` 用独立合成节点穷举全部路径，核对最小峰值路径与严格速度上限；`blender_two_bone_goal_contract.py` 在独立英文骨架验证目标点、世界朝向、无位移／缩放；`blender_root_envelope_contract.py` 验证胶囊刚体不变性与插值边界。通用路径选择器重放本角色缓存，与已经解算的路径逐节点完全相同。打包版本 0.1.3。

## 本轮踩坑

- 深穿后最近表面法线会翻向错误侧。有限差分法向推离在本例陷入约 -34mm 的根部穿入局部极小值；该实验没成功，不能包装成默认有效算法。
- 单一方向的偏移可把手推向头部；只修手掌也会漏前臂。需要整条链和真实皮肤检查。
- 各帧候选都合法仍可能在节点间跳跃。首条路线四分之一帧仍有 3 个包络失败。增加候选后，6cm／帧的严格修正速度上限无解；本轮选择出的最小可行峰值为 7.084cm／帧。它只是候选图内的最小值，没有全空间最优或自然度保证。
- 保持手掌世界朝向仍有微小指尖蹭脸，腕部限角微调后独立八分之一帧复查为零。
- 旧 NLA 上叠 COMBINE 与期望姿态有约 0.12mm 差异。改为该链的绝对 REPLACE 层并验证最终求值，误差为零。
- 赋 pose matrix 的数值分解会累积微小位置／缩放噪声；每次明确恢复源值。
- 修完动作后必须重算头发。6mm 体素／1mm 余量和 3mm 体素／3mm 余量都在后段留下擦碰；3mm／6mm 的本次组合通过实际发片复查，不能仅凭碰撞壳无交线判断成功。
- 整帧根部正确不等于帧间正确：世界坐标 PC2 线性插值曾带来约 1mm 漂移，骨局部缓存解决了这个坐标系问题。

## 仍未覆盖

当前短段从 200 帧零初速启动，没有完整预滚；不能直接拼为最终完整物理。未证明采样间连续碰撞（CCD）、开口区域完全包含、发束自碰、其他发束、全 15 秒或动作最终自然度。下一阶段应先扩大预滚及时间范围，再接入其他发束，持续检查全头表面和动作改动；不要把局部通过改写为全部解决。
