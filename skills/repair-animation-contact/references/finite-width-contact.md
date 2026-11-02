# 先检验实际宽发片，再修正它

适用情形：原生杆件／发骨长度稳定，真实发片仍穿过皮肤；继续改中心线半径或全局加迭代不能稳定处理。本流程把动力学输出作为目标，再做可撤销的准静态几何修正。它不重新求解惯性、能量守恒或完整布料动力学，不能标成完整物理系统。

## 原皮肤代理与内外判定

`exact_skin_collider.build_exact_skin_topology(mesh, arm, profile, weld_distance=1e-6)`：在静置姿态保留原始皮肤三角形，只焊微小接缝并补边界环，返回源顶点映射、闭合面和元数据，随后恢复原状态。运行帧的代理点直接取 `surface.coords(mesh)[source_ids]`，不通过体素或重新蒙皮近似。要求米制、稳定求值拓扑及可闭合的皮肤；非流形输入明确失败，不自动删掉问题面。边界盖和微焊仍属近似，需核对初态与动态覆盖。

只测“壳到皮肤”的距离会漏掉壳缺失的皮肤区域。本例反向测“真实皮肤到体素壳”，右臂峰值约 7cm、头部约 14cm；原皮肤代理抽样约微米级。迁移时双向检查，并在实际碰撞区域加密。

`closed_collider_field.ClosedColliderField(world_vertices, closed_faces)` 按连接组件做包围盒与三方向射线判定，取组件并集的内外。与最近面法线翻转无关，也支持闭合组件重叠。固定帧内，仅当点移动小于先前到任一面的距离时复用符号；身体移动后重建字段。不是一般自交模型的严格有符号距离或连续碰撞证明。

BVH 浮点命中可能让下一次查询仍落在同一面。0.1.6 从原始起点用累计距离构造下一起点，重复近零距离命中只推进、不重复计奇偶；独立重复命中测试已通过。达到独立交点／进度上限仍明确失败，不能以异常默认“在外部”。

## 约束层

```python
skin_ids, skin_faces, meta = build_exact_skin_topology(mesh, arm, profile)
field = ClosedColliderField(coords(mesh)[skin_ids], skin_faces)
corrected, metrics = project_surface(
    target_hair_world, rest_hair_world, local_edges, local_triangles,
    root_pin_mask, field, previous_positions=previous_in_current_head_space,
    margin=.006, strain_limit=.05, max_displacement=.06,
    iterations=160, target_strength=.002)
```

参数是本例米制设置，换比例／材质要配置。局部三角形与边索引对应当前发束的顶点数组；`root_pin_mask` 必须明确，不能随意挪发根。案例按合法初始导向的前两段选择了 109 个发根顶点，这不是通用选择规则。主身体和保护动作均不进入自由度。

PBD 在原发片顶点、边中点、三角形中心采样接触，以边着色交替投影边长上下限、接触间隙与硬固定根。修正相对动力学目标有位移上限；上限不足仍报告失败，不能拉开人体或缩小代理取得通过。目标回拉、上一帧修正暖启动和窗口两端淡出控制接回原动画。

只保持各关键时刻边长不够：相邻样本的边方向快速翻转，插值会把边压短。传入上一时刻形状，先用当前附着骨的刚体运动搬到当前空间；`temporal_projection` 默认 0.9，限制边沿上一时刻方向的最小投影。各约束、固定根与位移上限可能冲突，仍需密采样验收，不能把阈值视为保证。

## 缓存与验收

`hair_position_cache.bind_position_cache(..., sample_step=.25, anchor_armature=arm, anchor_bone=name, anchor_matrices=matrices)` 保存骨局部修正。Blender FRAME 模式不按 PC2 文件头间隔播放；稠密缓存使用简单的 `(frame-first)/sample_step` 驱动采样索引。保存重开且 `use_scripts=False` 的独立子帧测试已通过。

先按四分之一帧求解，再独立重开按八分之一帧查实际求值三角形、有效边长与全部固定根，检查原 Actions／形态键／权重／拓扑及保护身体。源皮肤开口区域的完全包含、未采样时刻、发束自碰和其他发束仍单列未覆盖。要看多角度和连续画面，特别是进入／离开修正窗口。

本分支是 Python API；普通 `solve`／`hair-experiment` 以及现有侧栏不会自动运行整套新流程。人物映射、发束提取、修正窗口和验收仍要包装器配置；不需要逐个手 K 接触姿态。

2026-10-29 实测：一束 1,095 顶点发片、完整 1–450 帧，3,593 个八分之一帧独立采样无交线／超限应变；边长比约 0.9039–1.0943，109 个固定根误差 <0.001mm。最大几何修正约 19.63mm，本轮未新增修改人物动作。只覆盖这一束对皮肤，其他发束、自碰、开口区域包含与 CCD 未验收。
