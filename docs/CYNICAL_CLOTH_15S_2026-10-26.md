# シニカルナイトプラン：前 15 秒网格布料试验

当前试片：`outputs/cynical_cloth15/trial3/Cynical_Cloth_15s_preview.mp4`；同目录 `Cynical_Cloth_15s.blend` 和 `blendcache_Cynical_Cloth_15s/` 为可重新读取的缓存工程。

目的：验证现有换装模型能否在 VMD 舞蹈中使用真正的布料解算。先做白墙场景的低分辨率试片，不渲染整首歌，也不把试片称为原生 MMD／PMX 运行时验收。

## 输入与修复

- 模型基线：`outputs/stockings_sleeves/review_ready/work.blend`。
- 去除片面后的中性模型：`outputs/cynical_cloth15/clean_model/Keqing_PlateRemoved.blend`。
- 人物动作：`E:/data/模之屋/动作/シニカルナイトプラン/シニカルナイトプラン.vmd`，28,700 个骨骼记录、3,065 个表情记录。
- 镜头：上级目录的 `シニカルナイトプラン_CAMERA@最好带目线跟踪谢谢合作BY 弥歌_by_弥歌_1f7122933ea856d532e740658f0fc689.vmd`，282 个镜头记录，不含人物动作。
- BGM：`E:/data/music/Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3`。

两腿间多余片状物来自旧补裆分支与内部表面的袜层；本轮断开补片，并屏蔽 6,164 个内部来源面，不删除身体。保存中性模型时，对全部 24 个角色网格的坐标和形态键作摘要对照，保持一致。旧版只从外侧抽查臀部，未覆盖裙下低角度，不能沿用其通过结论宣称这处也检查过。

## 求解范围

真实求解器为 Blender `CLOTH` 修改器。网格代理 978 点、1,518 面，包含左右长袖尾和上下裙层；6,821 个视觉顶点，包括重叠金属印花和独立饰件，通过 Surface Deform 跟随代理。

一对重合材质面只取一层计算物理；真实上下裙层分别保留。每个连通岛有自己的固定边，避免下层裙片因为低于主裙腰线而没有 pin 点。固定组由 Armature 上游驱动，自由部分解算重力、阻尼、人体碰撞和自碰撞。当前质量步数 8，布料接触间隙 3 mm，人体厚度 2 mm，自碰撞间隙 2 mm。

本次不叠加 MMD 袖／裙刚体，以免重复驱动。头发及其他次级刚体暂不参与，贴体丝袜仍使用身体跟随表面。动作和表情从 MMD 根对象导入；若只选骨架，口型会漏掉。

计算帧 1–450，30 fps；渲染每隔一帧取一帧，640×360、15 fps 预览，仍是原速 15 秒。第 450 帧另存检查图，不加长视频。缓存放在工程旁的 `blendcache_Cynical_Cloth_15s/`，保留此目录及工程文件名。

音画对齐先核对作者的“う”第二关键帧（VMD 20，即导入后的 21 帧，约 0.667 秒）和音频起音（约 0.75 秒）。预览将音频前移 2 帧，属于起音对齐；翻唱全曲节奏是否一致需另做长段检查。

## 复现

在仓库目录运行，输出另选新目录，不覆盖已缓存的工程：

```powershell
& 'D:\software\blender\5.2.1\blender.exe' -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/prepare_cynical_cloth15.py -- --out outputs/cynical_cloth15/new_run
& 'D:\software\blender\5.2.1\blender.exe' -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/simulate_cynical_cloth15.py -- --fit outputs/cynical_cloth15/new_run --last 450 --render-step 2 --bake
python scripts/encode_cynical_preview.py --fit outputs/cynical_cloth15/new_run
```

公共 API `mmd_outfit.mesh_cloth.configure(proxy, pin_group, colliders, first=1, last=450)` 用于已完成分区的单层代理。调用前检查每个连通岛至少两个全固定点；失败时不添加修改器。完整人物分区和 Surface Deform 绑定仍由当前资产配方处理，不能把其固定阈值直接套到其他模型。

## 检查与限制

`simulation_report.json` 记录连续计算、边长相对初始值变化、包围盒、缓存状态；`video_report.json` 检查视频流、音频流、225 帧与 15 秒时长。必须重新打开工程读取靠后的缓存帧，验证无需从头再算。局部大拉伸、尖折和原始外层袖口交叠应如实保留，不能只以“没有 NaN／爆炸”认定合格。

本轮结果：450 帧顺序计算完成并封存磁盘缓存，MP4 视频和音频均为 15.000 秒。重新打开工程后，乱序读取 450、1、240、150、330 帧，代理包围盒与原计算结果误差为 0，单次读取约 0.30–0.34 秒。另存 1、150、240、270、330、450 帧的全身诊断图，避免配套镜头的近景遮住裙摆问题。

质量仍需调校：第 270 帧的边长比 P99 约 2.60，实际伸长量 P99 约 25 mm；第 300 帧约 20 mm。个别短边比值达到约 9 倍，不能称无拉伸或全部物理通过。当前验收状态为“15 秒试片可查看，布料质量需复查”，头发动态未验收。

本试片只是布料方案可行性验证。还需检查长段动作、袖口接触、裙层交叠、头发／裙／袖之间的碰撞和更自然的丝袜材质。Blender 布料缓存不能直接写成 PMX 修改器；若要回原生 MMD，需另外设计骨骼／顶点动画交付途径。

## 资料与署名

动作作者随包 `Readme.txt` 标注：动作 リングイネ；编舞／描摹源 わに；原曲 Ayase《シニカルナイトプラン》；原描摹模型 YYB式 Hatsune Miku 10th。用户另提供镜头 弥歌、翻唱 Shikako。本试验仅生成本地预览，未发布或重新分发源动作。相关署名应随未来发布的视频保留。

累计问题见 [实际踩坑记录](KNOWN_PITFALLS_2026-10-26.md)。
