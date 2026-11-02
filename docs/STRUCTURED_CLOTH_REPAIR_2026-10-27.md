# 15 秒衣服起皱修复

输入为用户已有换装结果与《シニカルナイトプラン》动作、镜头、Shikako 翻唱。旧版 `outputs/cynical_cloth15/trial3/` 保留对照；修复工程在 `outputs/cynical_cloth15/structured_v2/`。

## 实际修改

1. 固定区重绑：左右袖尾分别使用 `腕.R`、`腕.L`，裙片使用一致的 `下半身` 附着；不再在同一固定边混用躯干与旧裙骨。每个岛仍有独立的全固定边和渐变过渡。
2. 缩小固定与释放范围：全固定点从 153 降为 31，部分固定点从 204 降为 100。固定边保持连接，自由区仍运行真实 Blender CLOTH，带人体碰撞、自碰撞。
3. 保持成型版型：增加与附着骨一致的参考网格，裙片取 18%–45%／55% 的模拟位移、袖尾取 35%–75%，按离固定边的距离变化。明确为保形混合，不冒充完全自由的纯物理布料。
4. 布料抗弯由 0.7 提至 9，拉伸／压缩刚度 110、剪切 65，质量步数 12。与固定区重绑共同使用，不能单独把这些数字当通用参数。
5. 用三角面重心坐标和法向距离传递到未蒙皮的视觉载体，再将绝对坐标写回原衣物选区。原衣物拓扑、UV、形态键和固定部件保留；饰件及叠加印花跟随同一物理层。
6. 增加 46 帧预热及姿态过渡。成片仍为原动作前 15 秒；工程可见区间为 47–496 帧，镜头、人物、口型整体同移，BGM 相对可见开头前移 2 帧。

胸衣、腰封及硬质配件的主体未释放为自由软布；它们原有的固定折线／着色不在本次“裙片塌皱”修复的结论内。头发次级物理仍未启用。

## 验证

`scripts/verify_structured_repair.py` 对照旧工程：

- 全部 24 个原角色网格的基础坐标与所有形态键坐标摘要相同，包括身体／头、丝袜和 20 个鞋部件。
- 原动作第 1、270、330 帧与新工程第 47、316、376 帧的身体求值坐标误差为 0。
- 32 条两端 Pin **精确等于 1** 的固定边，抽查最大长度误差约 0.0016 mm。旧问题边原 22.34 mm 被拉至 52.09 mm；新固定边不再受相冲突的骨骼轨迹拉开。
- 模拟目标相对附着参考仍有非零位移，确认未通过关闭布料来获得平整画面。

初次检查把 Pin>0.999 当成全固定，混入近似固定的过渡点；改为区分精确固定和软过渡，没有删除失败样本。代理内部自由区仍存在局部拉伸，应以画面与自由区指标另行评价，不能把“固定边通过”写成全网格无拉伸。

独立数学检查 `tests/blender_cloth_transfer_contract.py` 验证三角面映射在旋转、平移、正／负法向偏移及三角形外点情况下的误差小于 1e-5 m。完整缓存与视频校验分别输出 `cache_reload_report.json`、`video_report.json`。

折角对照 `fold_comparison.json` 计算物理表面相邻三角面夹角相对原版型的增量。主裙在原动作第 270 帧的 P90 从约 42.8° 降至 9.5°，第 330 帧从 34.0° 降至 10.8°；下裙对应约 38.5°→14.2°、36.3°→11.0°。袖尾的大折角 P90 也下降，但中位数增加，仍有更分散的小褶皱。此指标只用于这两个姿态的几何对照，不宣称全部区域、所有帧都无褶皱。

## 复现

```powershell
& 'D:\software\blender\5.2.1\blender.exe' -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/prepare_cynical_cloth15.py -- --out outputs/cynical_cloth15/new_structured --mode structured --no-still
& 'D:\software\blender\5.2.1\blender.exe' -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/simulate_cynical_cloth15.py -- --fit outputs/cynical_cloth15/new_structured --last 496 --render-step 0 --shots 316 376 --bake
& 'D:\software\blender\5.2.1\blender.exe' -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/verify_cynical_cache.py -- --fit outputs/cynical_cloth15/new_structured
& 'D:\software\blender\5.2.1\blender.exe' -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/render_cached_cloth15.py -- --fit outputs/cynical_cloth15/new_structured
python scripts/encode_cynical_preview.py --fit outputs/cynical_cloth15/new_structured
```

插件模块 `structured_cloth.install` 接受已选定的衣片面、附着骨、固定区间和保形强度；当前材质分区与阈值是刻晴／达妮娅的专用配方。其他模型必须重新提供分区与附着规则。当前仍是 Blender 原生版，不代表 PMX／原生 MMD 已验收。

## 新增问题记录

- 负帧预热可计算，但本机点缓存出现负帧记录不完整；本轮改为正帧预热，并将成片范围、人物／镜头／音轨统一偏移。不能只移动人物动作。
- Surface Deform 的“invalid polygons”不等于目标存在零面积三角形。实际目标 978 点、1,518 面，最小面积约 8.6e-6 平方米，仍在绑定中失败；本轮改用显式三角坐标传递，未为绕过报错破坏原角色网格。
- 没有将旧流程认定为“重复蒙皮”根因；Blender Surface Deform 全权重输出本身可替换绝对位置。此处的修复证据是固定权重、保形分区与实际对照，不能仅由修改器排列猜测根因。[Blender 源码](https://raw.githubusercontent.com/blender/blender/main/source/blender/modifiers/intern/MOD_surfacedeform.cc)

此前资料与三组对照见 [起皱研究](CLOTHING_WRINKLE_RESEARCH_2026-10-26.md)，累计问题见 [踩坑记录](KNOWN_PITFALLS_2026-10-26.md)。
