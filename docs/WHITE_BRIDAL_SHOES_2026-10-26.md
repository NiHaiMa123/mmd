# 达妮娅完整脚部适配 White Bridal 高跟鞋

本轮按用户指定的 `White_Bridal_Reference_Palette.blend` 替换了原刻晴鞋。目标为保留完整脚部，围绕现成鞋调整穿鞋姿态；原始鞋资源和目标 PMX 均不改写。

## 多角度穿模修复后的当前交付

用户指出穿模后，专门隔离左右脚，各检查正面、背面、内外侧、前斜视、俯视、仰视及鞋头/后跟近景共 12 个角度。旧 `final/` 在中性姿态实际有左 3,113、右 3,104 对三角面交线；旧接地和边长检查没有覆盖这些接触，不能作为贴合通过依据。

最新工程为 `outputs/white_bridal_shoes/checked/Daniya_WhiteBridal_FitChecked.blend`，已通过 Blender MCP 打开，视口对准双鞋近景。`checked/work.blend` 为同几何的批处理输入；上一轮 `final/` 留作对照。

- `checked/review/L_all_angles.jpg`、`R_all_angles.jpg` 为左右脚各 12 角度总览；同目录保存全部原尺寸近景及红色交线诊断图。腿顶端的截面仅用于隔离检查，实际角色没有切腿。
- `checked/contact_verification.json`：完整脚部 8,928 面及对应丝袜 4,968 顶点保留；拓扑、UV、材质和全部形态键位移保留；上半身位置不变，硬鞋网格与鞋底/鞋跟变换不变。
- `checked/review/report.json`：左右脚默认姿态脚/袜对鞋交线均为 0。检测为真实非共面三角形交段，忽略短于 0.02 mm 的交段；不把交线对数解释为穿模面积。
- `checked/motion_sample/report.json`：覆盖整段动作的 28 个采样帧、左右共 56 侧帧，脚/袜对鞋交线均为 0。它不是逐帧穿模或动力学验收。
- `checked/mmd/model.pmx`、`grounded.vmd` 为同步更新的 MMD 产物；`checked/pmx_contact_review.json` 另对实际重导入 PMX 的第 1、121、256、3401 帧检查，交线均为 0。
- PMX 为 226,852 顶点、307,912 面、650 骨、35 材质、372 刚体、435 关节；无缺贴图、未知骨、未加权点或异常权重。接地重算覆盖 4,936 帧，最低约 0.49975 mm，最大根骨抬高约 8.913 mm。

修复使用 `addon/mmd_outfit/shoe_contact.py` 的明确内衬约束，脚与袜子共享平滑位移及形态键平移；最大局部位移约 13.346 mm。鞋内衬由材质筛选，鞋垫仅采用朝上的接触面；开口边缘不作为封闭平面，镜像法线保持指向鞋内。这里的选择规则及对应关系来自本资产，不能自动推广到任意模型。

足部在硬鞋内增加踝骨跟随，重建足袜的权重对应；踝带、珍珠环及后蝴蝶结随小腿骨，避免把整套配件锁死在踝骨上。踝带组件再等比放宽 4%；珍珠环在上一轮基础上等比放宽 20%、上移 30 mm，后蝴蝶结后移 14 mm，保留各自形状。后踝处 318 个丝袜点的悬空量平滑减少最多 0.975 mm，最小净偏移约 0.525 mm，脚和丝袜均未删面。

导出脚本保留每个鞋部件的原骨骼绑定，不能将合并后的整鞋重新全部绑到 `足首D`。接地模块同步覆盖踝骨与小腿骨上的全部刚性鞋部件。新增 3 项契约测试覆盖镜像内衬方向、开放鞋口、层间位移、接缝与形态键；真实资产另做拓扑/UV/形态键/鞋型比较。

仍为 `REVIEW_REQUIRED`，不影响原有宽袖、飘带及原生 MMD 动力学待验收状态。0.9 安装包尚未更新，本次接触修复为可重复执行的专用流程。

```text
blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/correct_bridal_contacts.py -- --source <本资产已适配工程.blend> --out <接触修复目录>
blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/correct_bridal_binding.py -- --source <接触修复目录/work.blend> --out <最终目录>
blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/bridal_multiview_review.py -- --blend <最终目录/work.blend> --out <最终目录/review> --assert-clear
blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/export_bridal_shoes.py -- --fit <最终目录> --size 2048
blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/bridal_motion_review.py -- --fit <最终目录>
blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/review_bridal_pmx_contacts.py -- --fit <最终目录>
```

多角度脚本还支持 `--vmd <动作.vmd> --frames <帧列表> --audit-only --assert-clear`；不能只拍好看的斜前视角。默认 12 方向照片适用于中性姿态，动作诊断需使用其脚骨局部相机变换。`verify_bridal_contact_delivery.py --fit <最终目录>` 读取 `review/` 和 `motion_sample/` 的检查报告并比较原始几何；调用前必须先生成实际检查报告。

## 上一轮基线交付（已被 checked 替代，存在穿模）

- 干净视图工程：`outputs/white_bridal_shoes/final/Daniya_WhiteBridal_Clean.blend`。通过当前 Blender MCP 整理，只显示一套穿衣角色；隐藏骨架、372 个刚体、关节、备份及叠加线，材质预览对准全身。没有删除对象或改几何；之前的可见性记录在 `visibility_before_clean_view.json`。
- 原生 Blender 工程：`outputs/white_bridal_shoes/final/Daniya_WhiteBridal.blend`。保留程序化蕾丝、丝带、珍珠等材质，打开时对准脚部。
- MMD 模型：`outputs/white_bridal_shoes/final/mmd/model.pmx`。
- 配套接地动作：`outputs/white_bridal_shoes/final/mmd/grounded.vmd`；该动作只适配本模型和原测试动作。
- 默认姿势图片：`outputs/white_bridal_shoes/final/oblique.png`、`front.png`、`side.png`、`back.png`。
- 完整脚部与鞋内剖面：同目录 `feet_oblique.png`、`feet_side.png`、`cross_section.png`。
- PMX 动作图：同目录 `motion_review/`；结构、接地、几何与输入摘要见 `verification.json`。

原生工程与 PMX 使用不同的材质表达。PMX 用 2048×2048 烘焙贴图近似原程序材质，并启用双面显示；不等于完整复现 Blender 的反射、布料高光和微表面效果。

## 实际处理

1. 由 0.9 工程的坐标来源记录准确移除原鞋：1,774 顶点、1,930 面，未按高度误删其他衣物。
2. 从达妮娅原始输入重建脚部区域共 8,928 面，包含脚趾和趾甲；保留原先手套遮蔽及其他上半身表面，上半身原有可见面丢失为 0。
3. 对足弓和脚跟使用连续的高跟姿态场，前掌保持近似水平。顶点和形态键采用同一变换，保留完整拓扑；脚部没有因适配而删面。
4. 将原先在旧鞋口截断的丝袜延伸到脚背、脚趾和脚跟，保留下面的脚部。新丝袜足部同样包含 8,928 面，替换旧下端 1,876 面，偏移约 1.5 mm。
5. 鞋底、鞋跟、鞋面和蝴蝶结保持冻结后的原始形状，仅作每侧整体等比变换和镜像。踝带、扣件及珍珠环另作 1.1 倍整体等比放宽，以匹配脚踝；没有将鞋底投影、压平或逐顶点拉宽。
6. 穿硬鞋时，前脚掌和脚趾随踝骨运动，保留小腿过渡权重及全部脚部几何。身体与丝袜各调整 3,572 个顶点的绑定；脚趾独立弯曲不作用于这份穿鞋状态。形态键数据保留，但未穷举所有体型、脚趾形态键组合。

固定参数保存在 `fit_report.json`：整体 scale=0.11、增加足弓角 12°、相对旧工程再抬高 6 mm、前掌前移 12 mm/下移 5 mm、局部脚跟宽度 0.9、局部脚跟横移 1.5 mm。它们只针对这套资产和本机达妮娅模型，不是通用的鞋子自动拟合参数。

## 验证与修复

- 新增 7 项 Blender 契约测试，覆盖足部区域限制、前掌姿态、镜像、形态键、完整拓扑及穿鞋绑定的小腿权重保留。
- 修改脚姿时必须同步 `足首` 骨末端、脚趾 IK 参考并重建 MMD 附加变换。否则即使 pose basis 为单位矩阵，也会额外旋转脚部。最终脚部关键骨默认姿势偏差约 0.013 mm，小于 0.1 mm 检查容差。
- 蕾丝与浅棕底边由 `bridal_sole_distance` 网格属性划分；合并导出时必须保留 FLOAT/POINT 属性，不能仅复制位置、UV 和材质名。
- 共享导出器采用 SKIP_EXISTING，重复导出会继续使用旧贴图副本。专用导出脚本会同步自己生成的 atlas 副本并核对哈希，避免新贴图生成后 PMX 仍显示旧颜色。
- PMX 重导入检查权重、未知骨、未加权顶点及缺贴图；本轮没有修改 0.9 发行 ZIP。
- 动作接地测量和重导入验证覆盖全部 4,936 帧。重点视觉与边长检查仅为第 1、121、256 帧，不能表述成全动作无穿模。鞋子 249 个顶点形态键均无变形。

仍为 `REVIEW_REQUIRED / accepted=false`。原有宽袖、飘带物理问题不因本轮换鞋而解决；本轮没有进行原生 MMD 动力学验收。

最终 PMX 为 226,853 顶点、307,912 面、650 骨、35 材质、372 刚体和 435 关节。未加权顶点、未知骨、异常权重及缺贴图检查均为 0。UV 展开为烘焙增加了拆点，不能将顶点数增长理解为鞋型发生变形。

4,936 帧接地复验最低约 0.49975 mm，最大根骨抬高约 8.913 mm；除顶层根骨外，原动作的其他骨记录、表情等后续段均逐字节保留。三个抽查帧的鞋子边长绝对误差最高约 0.291 微米，长度超过 5 mm 的边相对误差最高约 0.004%。这只证明鞋型稳定及平地接地，不证明所有脚、袜、鞋面三角形都没有局部交叠。

最终贴图副本已校验与新 atlas 内容一致，白色蕾丝与浅棕底边恢复正常；珍珠使用白色漫反射近似其原 PBR 反射。鞋口和鞋头的局部接触仍需放大验收，不把结构验证通过写成零穿模。

## 可重复调用

当前是资产专用的脚本流程，供其他模型重复执行，不需要现场手工修改网格：

```text
blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/fit_white_bridal_shoes.py -- --job <0.9任务目录> --asset <White_Bridal_Reference_Palette.blend> --out <新的输出目录>
blender -b --factory-startup --python-exit-code 1 --python scripts/export_bridal_shoes.py -- --fit <新的输出目录> --size 2048
blender -b --factory-startup --python-exit-code 1 --python scripts/bridal_motion_review.py -- --fit <新的输出目录>
```

专用模块为 `addon/mmd_outfit/heeled_foot.py`。本轮尚未将外部 Blend 鞋资源的流程纳入已发布插件面板；0.9 安装包仍用于原有流程。
