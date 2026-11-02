# 全头经典Cloth社区流程对照：停止记录

用户在社区调查后回复“开始”，授权按经典Cloth代理流程建立完整头发对照。继续适用埋入连片范围或深度任一超过5厘米才处理；实际明显拉伸/物理失稳则停止报告。脚本接口错误自行修正。

## 实现与保留

- 源：`E:/project/mmd/work/headswap_xl_codex/normal_preview15_20261101/完整角色_现有最佳流程_15秒预览.blend`，未覆盖。
- 新目录：`E:/project/mmd/work/headswap_xl_codex/classic_cloth_20261101/candidate02/`。
- `prepare_classic_full_hair_proxies.py`：全27束、5260代理顶点、9866三角面。合并原作者的同位接缝，原生Decimate简化，原生Surface Deform绑定。辫子两片分离面使用原生Cloth缝合边各3条，初始最大缝隙7.94毫米和0.141毫米。没有通过扩大真实头骨硬根区取得连接。
- 本机未安装Simplicage。已核对官方文档，其链模式属于Lite/Pro；未购买插件。本轮使用已读取的社区原生流程，没有自创物理求解器。
- 参考：Sextet `BV1cD4y1R7U9` 03:15、06:00；启辰_TB `BV1pS9MB8Em2` 02:27–03:12；Simplicage Settings（Cloth/Pin/Surface Deform）。
- 新Action副本仅重置全部27束发骨；旧Action保留。身体和腕部缓存保持，抱手256–321动作数据未改。原始网格、权重、232形态键、银发正常材质、完整脸/眼睛/头饰/全部头发、地库、固定全身镜头保留。
- 无物理控制：初态显示误差0.954微米；刚性头部传递最大误差2.146微米；5度小弯曲控制显示边长P01/P99约.977/1.020。这只证明接口基本可用，不证明复杂动力学形变传递稳定。

## 接口错误及修正

首次 `candidate02/physics/` 把 `settings.vertex_group_mass` 赋值放在创建顶点组之前。Blender会静默清空不存在的组名；后来创建组不会自动恢复。用 `mcp_probe_classic_pin_group.py` 独立小对象复现，临时对象删除。该次结果已保留备份并将 `result.json` 标记为 `INVALID_SETUP_PIN_GROUP_ASSIGNMENT_ORDER`，不能用来判断物理路线。

修正为先创建组、填权重，再赋值并断言实际组名。物理参数未因错误试算而调整。之后在独立 `candidate02/physics02/` 正式计算。

## 修正接口后的真实结果

脚本：`run_classic_full_hair_physics.py`，使用未经修改的Blender经典Cloth修改器。20 quality、12 collision quality；张力/压缩/剪切1000，角度弯曲25，质量.005，空气阻尼5，重力1；真实闭合身体余量3毫米、Cloth余量2毫米。原生Pin固定根，头部几何变换在Cloth之前。各束自碰/互碰未启用，不能宣称全头自碰解决。

**第7帧（原片0.20秒）右侧短发实际显示发片局部拉伸，自动停止。没有检出身体埋入，停止原因不是5厘米接触规则。**

重新打开缓存工程后的独立复核 `review_classic_full_hair_stop.py`：

- 27束实际Cloth固定组全部有效；逐帧最大固定点误差0.381微米，停止帧身体保持误差0。
- `Sidehair1.R` 代理边长P01/P99为.98867/1.02649，最大代理单边延长2.459毫米。
- 原始显示网格源边65234–65235，从3.488毫米变成24.458毫米，延长20.969毫米。该边沿镜头深度变化较大，正面投影只有约2.6像素；不能说整束头发伸长7倍。
- 原始显示网格全头边长P01/P99为.96913/1.06600，与连续计算报告一致。
- 证据指向Surface Deform对这种局部弯折的传递放大；不能据此断言经典Cloth发生全头失稳。

## 新输出与状态

目录：`E:/project/mmd/work/headswap_xl_codex/classic_cloth_20261101/candidate02/physics02/`。

- `完整角色_全头经典Cloth_复查.blend`（约274MB）。
- `查看全头经典Cloth复查.html`、`完整头发_经典Cloth_停止复查.jpg`，包含正常完整角色与头部局部标注。
- `keyframes/f0001.png`、`f0007.png`：1920×1080正常材质。
- `cache/ClassicHair_00.pc2`至`ClassicHair_26.pc2`：27束回放缓存仅1–7帧；身体/腕部3个缓存一并保留，30文件头与长度检查有效。不是可恢复求解器检查点。
- `result.json`、`stopped_review.json`、`review_manifest.json`：真实停止及独立复核。
- 所有模拟/只读检查进程退出，仅GUI Blender PID3400保留。不要重复启动。

7.5秒、11秒、12.5秒尚未验证，5–15秒图集未完成。禁止把第7帧钳制缓存用于后续时刻冒充效果。

按用户要求停下来报告。建议下一步采用社区已经展示的“Cloth代理顶点组→发骨跟踪→原权重蒙皮”，减少原发片局部形状被表面绑定直接放大；尚未实施，不应在用户尚未继续前自行调整参数重跑。任何替代映射仍要用真实显示发片复查5厘米规则。

自动关机保持取消；服装流程保持暂停。
