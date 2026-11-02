# 胸衣恢复与原生高清试片

本次针对用户指出的胸前团皱，实际修改原生模型。输出目录为 `outputs/cynical_cloth15/chest_hd/`，基础工程仍保留 `structured_v2/` 作为对照。新工程设为 1920×1080、30 fps，前 15 秒范围为 Blender 47–496 帧；1–46 为布料预热。

## 发现与处理

团皱在中立姿态、纯灰材质下也存在。原始刻晴衣服平整，当前服装基础坐标已经被旧适配流程改变，重新计算法线没有消除折叠。因此裙摆布料刚度调整不足以修复胸衣。

按材质、UV 和原始连通片恢复刻晴各层衣片坐标，使用三角面重心插值处理适配时新增的细分顶点。原衣片与现有胸衣做最小二乘仿射拟合，只保留整体尺寸变化，消除逐点挤压形成的细小褶皱。白色衣片、紫色束衣、胸前装饰一起恢复，向腰部和领部平滑过渡。皮肤作为间隙约束而非紧身吸附曲面；本轮 3,840 条前向射线命中身体，恢复后的前片已在皮肤外侧，不需要额外局部推挤。

胸口下部排除最近上臂／肩部的蒙皮影响，避免抬手把衣片拉出尖角；上领口保留过渡。恢复原 PMX 的定制法线，并按仿射逆转置变换。法线恢复改善低面数表面的明暗，几何对照另行计算，不能靠法线把折叠藏起来。

源模型复用 UV，不能取“第一个最近 UV 面”。现实现同时核对材质、来源连通片、所有重合 UV 三角面的空间位置。仅凭目标包围盒会误选上臂小饰件，进一步以原骨权重和源坐标筛选；74 个非躯干或不明确片段保留原样，记录在模板中，不删除它们。

## 验证记录

- 实际恢复 9,967 点、14,628 面；最大基础坐标修正约 33.17 mm，拓扑及 UV 不变。
- 白色胸衣 2,767 面的几何折角 P90：23.95° → 11.21°；超过 45° 的内部边：148 → 11；零面积面均为 0。使用几何面法线，独立于材质和自定义法线；只对应中立基础网格，不等于所有动作无穿模。
- 23 个其他原角色网格的基础及全部形态键坐标摘要一致。Cloth 非选区的全部形态键坐标摘要一致，选区 250 个形态键的相对位移保留，最大数值误差约 3.73e-9 m。未新增删除身体、脚或丝袜的操作。
- 503 个被物理传递近邻选择误包含的躯干顶点退出该分支，其中白色胸衣有 11 点；胸衣作为成型上衣蒙皮，裙摆和袖尾继续使用既有真实 CLOTH 与保形参考混合。
- 复制缓存后重开工程，以 496、47、300、210、376 帧随机读取对照原模拟包围盒，最大误差为 0。上游代理、碰撞体和缓存均未改动。
- `chest_review/` 为 1080×1080 近景：中立七角度、原动作第 1／150／240／270／330／450 帧的正面及左右 45°，另有纯灰对照。影片按原镜头输出 1920×1080。

原生渲染状态见 `render_progress.json`；视频完成后的尺寸、帧率、时长、音轨验证见 `video_report.json`。逐帧 PNG 的原始尺寸也在编码前验证，不用放大小视频获得 1080p。

成片已完成：`Cynical_Cloth_15s_preview.mp4`，H.264 1920×1080、30/1 fps、450 帧、15.000 秒；AAC 音轨亦为 15.000 秒。所有输入 PNG 都是原生 1920×1080。完整画面渲染约 1,427 秒；插件 ZIP 的独立引擎导入、胸衣模块导入、面板注册和已有场景保留检查通过。最新 Blender MCP 端口为 9878，实际文件已核对为 `chest_hd/Cynical_Cloth_15s.blend`，当前窗口显示干净胸口近景。

高清末段近景还有三个细小棕色三角块。像素射线将其中两处定位为 `Cloth` 的原连通片 4（腰带内层），另一处为连通片 3；对应身体表面在衣片后约 17–19 mm，不能误判为身体穿出。权重边界混合和 6 mm 身体间隙两组探针没有消除它们，未应用这些试验。当前将内腰带与外束衣的局部相交保留为待细修项，记录在 `corset_pixel_trace.json`，不声称成片所有区域零交叠。

## 复现

```powershell
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/recover_torso_template.py
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/repair_chest_panel.py -- --torso --out outputs/cynical_cloth15/chest_hd
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/verify_cynical_cache.py -- --fit outputs/cynical_cloth15/chest_hd
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/inspect_chest_multiview.py -- --fit outputs/cynical_cloth15/chest_hd --out outputs/cynical_cloth15/chest_hd/chest_review
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/audit_chest_geometry.py
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/render_cached_cloth15.py -- --fit outputs/cynical_cloth15/chest_hd --width 1920 --height 1080 --step 1
python scripts/encode_cynical_preview.py --fit outputs/cynical_cloth15/chest_hd
```

低层恢复入口在 `addon/mmd_outfit/chest_panel.py:restore`，接收衣服、身体、骨架、明确面列表和恢复模板；模板副本在新工程目录 `torso_template.json`。UV 对应提取和本次人体高度／骨名规则仍是刻晴与达妮娅专用配方，不代表其他角色可零配置使用。当前视频仍是 Blender 原生试片，完整头发物理、整首动作、原生 MMD/PMX 运行时仍未验收。
