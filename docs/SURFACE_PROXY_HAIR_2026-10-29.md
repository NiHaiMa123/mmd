# 有限宽度头发的代理、缓存与接触测试

本轮仍是实验分支，不能替代整段 15 秒验收。自动关机保持关闭。

输入为 `contact_repair_20261029/multi_bundle/left_arm_feedback_rig_roots/baked/Body_With_Attachment_Detour.blend`。
只处理左侧一束（1101 点、1654 三角面），保留已通过的右束缓存、原 Action、形态键及身体。
输出根目录为 `E:/project/mmd/work/headswap_xl_codex/contact_repair_20261029/surface_proxy_20261029`。

## 已确认并修复的管线错误

1. 原显示发片焊接到 846 点后，仍有 228 对非邻接初始自交，不能直接当合法物理初态。
   生成 302 点、600 三角面的闭合切片包络，验证表面无初始自交、覆盖显示发束。
   这是单束整体包络，不表示每根头发或各分叉都独立运动。
2. Blender 本机的碰撞距离 RNA 下限为 0.001 单位。原先设置的小值被静默截断，
   大于本束约 0.536mm 的最短边。现在在独立、居中的 10 倍仿真坐标运行，读取真实生效值，
   若仍被截断就直接失败；不缩放原骨架或修改原场景重力。
3. 壳内显示发片的 Surface Deform 产生过大局部变形。改用原生 Mesh Deform，
   再以 Laplacian Deform 重建细节。两者都不能保证最终表面无碰撞。
4. 原生 Cloth 整数帧尚可、直接子帧求值却变形。只做原生 point-cache bake 未消除问题。
   现在先采集原生整数帧代理，转为随头部运动的局部位置缓存，再在子帧驱动显示网格。
   原模型最终接收独立的四分之一帧缓存；不依赖手工运行 Python 回调。
5. 36 个真正完全绑定头骨的点，最后用明确蒙版恢复精确刚性附着。
   作者蒙皮的过渡权重与物理固定策略分别报告；`root_only` 试验只改变辅助代理，原权重不变。

## 实测边界

| 候选 | 检查 | 碰撞失败样本 | 应变失败样本 | 边长比范围 |
|---|---|---:|---:|---|
| resampled_proxy_probe | 1–35，步长 .25 | 0 / 137 | 0 / 137 | .9446–1.0528 |
| 同候选独立重开 | 1–35，步长 .125 | 0 / 273 | 0 / 273 | .9446–1.0528 |
| resampled_worst_window | 230–270 步长 .25，另加第 1 帧 | 25 / 162 | 37 / 162 | .2632–1.4332 |
| root_only_worst_window | 同上 | 20 / 162 | 114 / 162 | .2168–2.1435 |
| strutted_root_worst_window | 同上 | 19 / 162 | 29 / 162 | .3859–2.2521 |

应变验收阈值是原始边长的 .9–1.1，仅统计原长大于 .5mm 的边。
短段缓存重载最大差约 0.358 微米，硬发根约 0.298 微米。短段通过不表示接触难段通过。

实际闭合皮肤诊断发现：第 245 帧，代理也深入约 7.85mm，显示发片深入约 9mm；
第 243 帧代理未穿过身体，而显示发片仍深入约 10.82mm。因此物理壳和显示映射两层都要验收。
不能只加大 Mesh Deform 权重或只提高 Cloth 子步来宣布解决。

内部支撑的依据是 Blender 原生 Cloth 将非缝合的 loose edges 建成结构弹簧；
本轮显式加入切片直径及跨切片斜撑，仍未通过难段，所以没有提升为默认方案。
[Blender cloth 源码](https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/cloth.cc)。

## 接触约束的可行性对照

`probe_surface_contact_feasibility.py` 冻结身体、固定 36 个真实根点，在精确皮肤的闭合代理上
查询有符号距离，约束顶点、边中点和面重心，并检查真实显示三角面交线。
从合法初态顺序推进 240–250 帧、步长 .25，41 个样本的交线均为 0；
但整体边长比仍为 .8121–1.3143，不能验收。这是准静态接触对照，不是动力学成品。

新增 `surface_contact_admm.py` 是小发束的 NumPy 全局约束参考：边差分和重心接触行拆分，
局部投影边长／外部间隙，全局线性求解传播修正，硬根从自由度消去。它没有实现完整 CCD、
发束自碰撞或专业毛发求解器，不能把它称为论文的完整复现。
设计参考 [Projective Dynamics 作者页面](https://users.cs.utah.edu/~ladislav/bouaziz14projective/bouaziz14projective.html)
的局部投影／全局求解思想，具体本轮算法为实验性 ADMM 约束拆分。

## 复用入口和验证

- `addon/animation_contact_tools/mesh_hair_proxy.py`：角色名无关的代理构造、头部运动坐标、皮肤碰撞体和原生 Cloth。
- `addon/animation_contact_tools/hair_position_cache.py`：新增对象锚点，原有骨骼锚点仍支持；禁止两者同时传入。
- `scripts/run_hair_surface_proxy.py`：当前角色的输入适配器，输出设置、点缓存、候选和机器报告。
- `scripts/verify_surface_proxy_cache.py`：独立重开、密采样检查显示表面／边长／缓存误差。
- `scripts/diagnose_surface_proxy_contact.py`：分别定位物理代理、显示发片及固定权重问题。

英文骨架代理测试、对象锚点重开、旧子帧缓存、多个缓存组合均已通过。
正式迁移还需要明确发束、合法初态、真实根点、蒙皮过渡与物理固定政策，禁止只照搬角色路径。
原生模拟通过后，还必须检查整个 1–450 范围、原身体与右发束回归、真实显示面自碰撞、
开始结束接回、速度连续性与至少正／侧／斜三个角度；离散无交线不能证明帧间没有穿越。
