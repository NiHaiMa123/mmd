# 进度

> 与 `plan.md` 配套的简短状态区。每完成一批在这里更新，不重写 plan.md。

## 当前状态

- **当前批次**：第 1 批
- **当前任务**：P1-01（服装识别与预览）
- **最近期望产物**：来源角色的服装部件候选清单 + 4 视角预览图
- **已验证功能**：见下方「已验证」

## 已验证

| 任务 | 状态 | 验证方式 |
|---|---|---|
| P1-00 环境与导入导出 | 通过 | `python -m src.cli inspect` / `roundtrip` |

## 主要阻碍

（无）

## 环境事实

- Blender 5.2.1 LTS，`D:\software\blender\5.2.1\blender.exe`
- mmd_tools 以扩展形式安装：`bl_ext.blender_org.mmd_tools`
- 外层 CLI 用系统 Python 3.14
- 测试资产：
  - 来源 `刻晴.pmx`（1 身体网格 / 28882 顶点 / 23 材质 / 316 骨）
  - 目标 `达妮娅.pmx`（1 身体网格 / 294317 顶点 / 30 材质 / 520 骨）

## 踩坑记录

1. `bpy.ops.object.select_all()` 在 Blender 5.x 后台模式报 context 错误 → 改用 view layer 逐个 `select_set`。
2. `mmd_tools.export_pmx` 的 poll 要求活动对象是 `mmd_type == 'ROOT'` 的根 EMPTY，选中根物体即可。
3. 导入后的对象里绝大多数 mesh 是**刚体碰撞代理**（刻晴 184 个），真正的身体网格只有 1 个 —— 统计与拆衣必须按「ARMATURE 祖先」过滤。
4. CLI 拼参数时 `--target` 为 None 会让 `" ".join(cmd)` 抛 TypeError → 参数列表过滤 None。
