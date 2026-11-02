# 13 秒袖子薄片与跳飞修复

用户指出 `chest_hd` 的 13 秒附近袖子拉成薄片。本轮同时检查解剖左／右两袖，视频 13.0 秒对应 Blender 帧 437；原版保留对照，新工程在 `outputs/cynical_cloth15/sleeve_stable/`。

## 原因与最终方案

旧保形方法直接混合蒙皮参考与布料的顶点坐标。当袖子整体朝向不同，混合会将宽度抵消。13 秒右袖最短边只剩基础长度约 11.7%，同帧解算网格约为 79.8%；12–14 秒连续检查还发现左／右最短边分别降至约 4.6%／7.3%。仅看最大边拉伸或抽几帧，无法发现这种压缩。

另有两项放大问题：每袖有 11 对重合但未连接的接缝点；旧视觉传递含 2,723 个三角面外点，最大重心系数绝对值约 6.55，能把小三角形变形放大到饰件上。

最终保留原有实际 CLOTH 解算缓存及裙摆运动，对袖子加入约束后处理：

1. 每袖将接缝合并为 203 个约束点，输出时再映射回原来的 214 个点。原服装拓扑、UV 与形态键不改。
2. 对齐参考与解算的整体旋转，再混合局部形变，避免相反朝向线性相消。固定点保持参考位置，软固定区逐渐过渡。
3. 迭代限制边长度和三角面面积，保留可控变形，避免袖面塌成细线或过度伸长。
4. 在附着骨的局部坐标中平滑自由部分，限制瞬间变化；保持身体平移和抬臂响应。
5. 对袖饰使用位于三角面内部的重心系数与正交局部偏移，不再用大系数向外推算。
6. 将 1–496 帧结果写入 `StableSleeveShapes.pc2`。此文件是实际布料输入经过约束后的缓存，不是新的纯物理解算，也不是原生 PMX 刚体。

旋转还必须在时间上连续。首版旋转修正的几何尺寸正常，但跨 180° 时最短弧分支改变，造成约 0.6 m 的单帧跳变，已在交付前发现并修正。最终保留四元数半球历史，以连续角度插值，并限制每帧旋转变化；测试覆盖 170° 连续跨到 190°。

## 未采用的对照

实际尝试过独立的 406 点缝合 CLOTH、提高刚度、不同顶点质量，以及额外的裙摆碰撞。它们出现新的局部拉长或自由袖端飞到肩后，未用于交付。不能把这些候选的参数写成成功方案；最终使用原解算加约束后处理，接缝修复发生在输出约束层。

质量参数按顶点计算，改变质量需要同时评估刚度、阻尼和模型尺度，不能当作通用修复开关。[Blender ClothSettings.mass](https://docs.staging.blender.org/api/current/bpy.types.ClothSettings.html#bpy.types.ClothSettings.mass)

## 验证

`sleeve_dense_audit.json` 对照所有 450 个成片帧，含连续 12–14 秒。最终该区间：

| 指标 | 左袖 | 右袖 |
| --- | --- | --- |
| 最短边／基础长度 | 约 0.746 | 约 0.745 |
| 最长边／基础长度 | 约 1.269 | 约 1.265 |
| 13 秒三角面积比 P01 | 约 0.477 | 约 0.458 |

面积比为局部面相对基础网格的面积；不表示衣服全身覆盖率。约束目标为边长 0.75–1.25、面积下限 0.45，迭代存在残差，以上列的是实际测量值，不将目标值写成硬保证。

- 全段目标网格最大单帧位移由约 0.128 m 降至 0.110 m；该数也包含身体带动的裙摆，不能全部解释为袖子相对速度。
- 全部 450 帧的裙摆目标坐标与上一版逐点一致，最大误差为 0。
- 24 个原可见模型网格的基础坐标及全部形态键摘要一致，包括已修胸衣、头身、丝袜与鞋。
- PC2 随机读取和原计算结果逐点误差为 0；原始 CLOTH 缓存保留。
- 12.0、12.5、12.83、13.0、13.17、13.33、13.5、14.0、末帧各拍正面、背面及斜视，共 27 张 1080×1080 近景。
- `blender_sleeve_rotation_blend_contract.py` 验证相反朝向保宽、跨 180° 连续及固定点；`blender_stable_sleeve_transfer_contract.py` 验证有界权重和刚体变换，最大误差约 4.9e-7 m。

新成片仍为原生 1920×1080、30 fps、15 秒，渲染状态及编码结果分别见 `render_progress.json`、`video_report.json`。`Sleeve_12_15s_before_after_1080p.mp4` 是 12–15 秒同步对照，左旧右新，裁掉横向空白后并排，不放大像素。

成片已完成：H.264、1920×1080、30/1 fps、450 帧，视频与 AAC 音频均为 15.000 秒；对照片段为 2160×1080、90 帧、3.000 秒。逐张原始 PNG 尺寸及完整视频解码检查通过，最终报告为 `acceptance.json`，状态 `SLEEVE_CORRECTION_PREVIEW_READY`。Blender 新窗口及 9878 MCP 端口已核对为本工程，检查画面停在帧 437 的背面；白墙只在编辑视图临时隐藏，正式渲染未取消。

## 调用与复现

当前配方的固定入口：

```powershell
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/bake_stable_sleeve_shapes.py
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/review_stable_sleeves.py -- --fit outputs/cynical_cloth15/sleeve_stable
& 'D:\software\blender\5.2.1\blender.exe' -b --python scripts/render_cached_cloth15.py -- --fit outputs/cynical_cloth15/sleeve_stable --width 1920 --height 1080 --step 1 --priority-start 407
python scripts/encode_sleeve_comparison.py
python scripts/encode_cynical_preview.py --fit outputs/cynical_cloth15/sleeve_stable
```

插件通用数学入口为 `sleeve_shape_constraints.rotation_blend`、`project_strain` 和 `stable_sleeve_cloth.bind_clamped_frames`。当前缓存提取脚本中的对象名、骨名、路径与阈值仍针对刻晴／达妮娅；其他模型需要提供自己的参考／解算对应点、固定组与面列表，不能直接复用当前角色索引。

保存或移动工程时需保留同目录 `StableSleeveShapes.pc2` 及 `blendcache_Cynical_Cloth_15s/`。完整头发物理、整首歌和原生 MMD／PMX 仍未验收；腰带内层的小交叠继续保留为已知细节，不据此宣称全模型零穿插。

缓存对应本次动作。修改骨骼动作、换 VMD 或调整服装基础形状后，需重新计算原布料与后处理缓存，不能沿用旧 PC2。
