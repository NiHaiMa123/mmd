# 鞋子适配复核与方法调查

日期：2026-10-23。以下按调查顺序保留记录。后续已实际读取两部专项鞋教程的字幕和关键帧，并实现 0.3 闭口鞋保形流程；最新进展在文末。旧版鞋楦变形已撤回。

## 复核结论

v0.2 鞋子结果不合格。此前只确认正面不露趾，低估了鞋型损坏；“保留拓扑”并不等于保住形状。撤回将该方法当作可用鞋楦适配的判断，停止沿该方向继续调参。

已从原始 PMX 重新渲染同一物理尺度的鞋部特写，未修改输入文件：

- 原鞋正面、斜面、侧面：`outputs/shoe_method_review/source_front.png`、`source_oblique.png`、`source_side.png`。
- 目标脚原始外形：同目录 `target_front.png`、`target_oblique.png`、`target_side.png`。
- 原始骨骼锚点：同目录 `landmarks.json`。
- 失败结果对照：`outputs/outfit_release_v02_hierarchy/20261023T020749Z_0b15d3ccf4/preview/detail_feet.png`、`detail_feet_oblique.png`。

原鞋有明确的斜鞋面、跟部曲线和圆形金属饰件。旧结果的鞋头横向膨胀、鞋面折线变尖、圆形鞋饰被拉长，鞋型已经改变。`foot_last.py` 分别缩放 X/Y、按足先权重混合，并随前后位置改变高度；金属材质也参与同一变形，没有硬部件保护。

## 已核对的非 B 站资料

### 1. Reallusion 官方：CC Shoes Creation Guide

[官方鞋类开发指南](https://wiki.reallusion.com/Content_Dev:CC_Shoes_Creation_Guide)

正文 General Workflow 和 Foot Binding Pose 明确说明：先旋转踝骨及趾根，使脚适合高跟鞋，再绑定和转移身体权重；地面接触点另行设置。示意图也展示了默认脚姿穿出鞋面、调整脚姿后匹配的区别。

可直接核对的图：[默认脚姿](https://wiki.reallusion.com/images/3/31/Foot_Binding_Pose_01.png)、[调整后的脚姿](https://wiki.reallusion.com/images/2/21/Foot_Binding_Pose_02.png)。未下载这些远程图片。

适用启发：鞋子不能只按裸足包围盒去撑开，高跟鞋需要匹配的脚部绑定姿态。该页面的骨名和接触系统属于 CC，不能直接套进 MMD。

### 2. ZEPETO 官方：Blender 鞋子绑定

[Rigging - Shoes/Expressions](https://docs.zepeto.me/studio-guide/rigging-shoesexpressions?hostName=docs.zepeto.me&title=Prepare+for+3D+modeling)

Alternate Pose Preparations、Weight Painting、Return to T-Pose 三部分给出完整链路：把脚摆到合适姿态，在复制的骨架/参考身体上建立替代绑定姿态；传权重并修正；再转回标准骨架，重新摆出高跟姿态检查错误。

适用启发：将高跟适配姿态与动画使用的标准骨架区分开，不能在绑定后随意修改 rest pose。这里是 Blender/Unity 导出流程，PMX/VMD 的脚 IK 兼容性仍需单独验证。

### 3. 教程作者本人：姿态下转移权重

[fBlah：Weight Transfer Tutorial: Heeled Shoe and similar cases](https://blenderartists.org/t/weight-transfer-tutorial-heeled-shoe-and-similar-cases/1147586)

作者帖子介绍从已摆姿态的骨架转移权重，并以高跟鞋说明如何兼顾适配姿态与 T/A 基础姿态。本文核对了作者的文字说明；未声称已完整观看其外链视频。

### 4. Character Creator 的实际工具流程

[Creating Custom High Heels](https://manual.reallusion.com/Character-Creator-5/Content/ENU/5.0/08-Creating-Custom-Assets/Creating_Custom_High_Heels_OBJ.htm)

官方操作包含必要的鞋网格编辑、侧视鞋底对齐、权重转移及鞋跟高度调整。这说明流程允许有控制的局部修形，不能概括成“别人完全不改鞋网格”；但它也没有支持将鞋子各部分任意缩放作为通用办法。

## B 站本地项目实用验证与缓存教程

项目：`E:\project\bilibili`。执行自检后，用 CLI 搜索 `MMD 换鞋 高跟鞋`（limit=8），首次搜索接口返回 HTTP 412，未获得候选列表。没有切换代理或反复请求。项目 `skills/bilibili/SKILL.md` 要求“B 站风控，停止请求并告知用户，不要换代理重试”。

离线复现并修复了三个客户端问题：

- 显式登录 Cookie 请求头会屏蔽 httpx Cookie jar，导致首页取得的设备 Cookie 未随搜索请求发送；现在合并与请求域名、路径匹配的 Cookie，配置登录值优先且不重复。
- `Config.cookie_header()` 原样读取含注释的登录文件，可能将 `# refresh_token=...` 和换行混入请求头；现在过滤注释、空行和 UTF-8 BOM，统一生成单行 Cookie。
- 首页初始化遇到 HTTP 412/429 仍继续请求搜索接口；现在立即返回不可自动重试的错误。

上一轮补充 7 项纯离线回归，原有 227 项及新增测试共 234 项通过。当时没有再次在线验证，未声称解除 HTTP 412。

后续进展：用户要求继续核查搜索方法后，将搜索迁移到 `/x/web-interface/wbi/search/type`，补齐 nav 口令获取、签名、缓存、验证响应识别及分页处理，新增 20 项测试，共 254 项通过。同一关键词真实搜索返回 `ok=true/count=8`，没有修改代理或失败后自动切换接口。这验证了修复后本机可用，不能证明此前 412 的唯一原因。

新获得的优先研究候选（仅搜索元数据，尚未观看）：

- [BV16VbK6fEf9：Blender 给裸足模型改成高跟鞋，支持裸足高跟鞋切换，快速给鞋子转移权重](https://www.bilibili.com/video/BV16VbK6fEf9)，纯欲怪味豆，05:15。
- [BV1MA4y1S7kS：一学就会的 MMD 换鞋教程](https://www.bilibili.com/video/BV1MA4y1S7kS)，Paper朱，16:16。
- [BV1KpDAYpESm：限制脚的旋转、高跟鞋切换裸足](https://www.bilibili.com/video/BV1KpDAYpESm)，纯欲怪味豆，07:45。
- [BV1xC4y127k6：MMD 穿鞋小技巧，如何让鞋子合脚](https://www.bilibili.com/video/BV1xC4y127k6)，乞山人，24:47。

详细修复与实测记录：`E:\project\bilibili\docs\SEARCH_METHOD_FIX_2026-10-23.md`。

已实际读取的缓存教程：[BV1FW41157y3《【GGpeimary字幕】用Pmxeditor给MMD模型换衣服》](https://www.bilibili.com/video/BV1FW41157y3/)，P1，09:38，UP 主 Kodoku-shi。来源是项目生成的 `hard_subtitle_ocr`，有明显 OCR 噪声，不能据此认定精确快捷键。

- 约 03:17–05:19：通过材质选择裙子及相关要素，再移动和缩放对齐。已查看 04:08 关键帧，可见选择的裙子和骨骼；不应只移动网格而留下配套数据。
- 约 05:41–06:30：切换到身体材质，选择穿出的皮肤并删除，同时保留应露出的皮肤。已查看 05:53 关键帧。这属于有意识的遮挡区处理，不能推广为自动删除所有检测到的穿插顶点。
- 约 07:24–08:25：导入 MMD、载入动作后检查。该教程支持将动态验收纳入流程；它不是高跟鞋绑定或跨体型权重转移教程，不能据此验证新的鞋算法。

本地产物：`E:\project\bilibili\output\BV1FW41157y3\P01_36897122\article.md` 与同目录 `transcript.md`、`assets/`。尚未提取或观看上述高跟鞋专项候选，不能引用其操作步骤。

## 后续扩词带来的研究入口

14 组检索显示：从“换鞋”换到“裸足高跟姿态、姿态传权重、RBF服装适配、VRChat/FF14改模”能找到不同路线。新增值得研究的候选包括 [FF14 的 Tpose 权重传递](https://www.bilibili.com/video/BV1Vpe2z9EBC)、[MMD 足 IK 崴脚修复](https://www.bilibili.com/video/BV1n54y1y7Dd)以及 [HoTools/RBF 素体适配服装](https://www.bilibili.com/video/BV13m5H6DEGe)。尚未读取这些视频内容，不能将它们当作脚姿或权重算法已经验证的证据。

HoTools 视频简介给出作者仓库，已核对 [公开源码](https://github.com/HollowAmeChan/HoTools)确实包含 Rbf 模块。下一步可沿具体代码和少量高相关视频验证方法，不继续泛化扩大鞋子包围盒。

搜索扩词方法、噪声案例与执行接口见 `E:\project\bilibili\docs\SEARCH_EXPLORATION_2026-10-23.md`。本轮 197 个去重候选包含大量无关视频；按作者名精确过滤可去掉其中一组的 19 条无关作者命中。候选数不能作为有用知识数量。

## 对本项目的新设计约束（推论，尚未实现）

1. 从原始 PMX 重取未变形的整只鞋，避免在已被旧 reskin/foot_last 改过的网格上继续修补。
2. 初始对齐仅允许整鞋移动、旋转，以及有明确需要的统一缩放；鞋底、鞋跟和金属饰件作为保形部件。更细的变形必须有局部约束和原鞋对照。
3. 先求目标脚的高跟姿态，使用踝部、前脚掌和趾根锚点；必要时只调整鞋内的目标足部形状。脚姿差异不能转嫁成鞋头膨胀。
4. 在对齐姿态中转移/修正权重。硬鞋跟与鞋底不能跟随各根脚趾乱变形，鞋面需要的弯曲应与硬部件分开。
5. 保持一份原始目标骨架，单独验证绑定姿态补偿、足先 EX、足首和脚 IK 的关系。通用 Blender/CC 教程不构成 PMX/VMD 已兼容的证据。
6. 增加原鞋保形检查：去掉整鞋的刚体变换/统一缩放后，比较鞋底、鞋跟、饰件的相对距离和轮廓；同时检查脚是否穿出、接触地面及动作效果。不能再只以“不露趾”和“拓扑未变”为成功条件。

以上是实现前的调查记录。旧算法保留作历史实验代码，0.3 服务拒绝执行其配置。

## 专项教程实读结果

使用本地 B 站搜索项目完成 inspect、illustrated fetch 和后台任务检查，来源均为 `platform_subtitle` 配合实际关键帧；不是仅从标题推断。

### 纯欲怪味豆，BV16VbK6fEf9，05:15

[Blender 给裸足模型改成高跟鞋](https://www.bilibili.com/video/BV16VbK6fEf9)。已阅读全文并看原始帧：00:00、00:47、01:34、03:03、04:24、05:03。

- [00:13–00:43](https://www.bilibili.com/video/BV16VbK6fEf9/?t=13)：同步调整身体高度及 IK，再调整脚踝/脚趾姿态，记录骨骼形态键。只抬 IK 会让膝盖弯曲。
- [01:23–02:17](https://www.bilibili.com/video/BV16VbK6fEf9/?t=83)：讨论高跟姿态与静置姿态不一致导致的权重转移问题；只改静置姿态也会令网格恢复，不能忽略绑定补偿。
- [02:21–03:16](https://www.bilibili.com/video/BV16VbK6fEf9/?t=141)：先将骨架变形保存在形态键，再应用静置姿态并使用对应网格形状。
- [03:51–04:43](https://www.bilibili.com/video/BV16VbK6fEf9/?t=231)：局部调整脚与鞋，数据传递中采用最近面插值传顶点组，并检查脚背。

这条教程支持“先匹配脚姿/绑定姿态再传权重”，不直接提供 PMX 跨骨架的自动求解器。字幕中“竞技/拳脚”等是明显识别噪声，以上为结合画面的转述。

本地文章：`E:\project\bilibili\output\BV16VbK6fEf9\P01_41665953795\article.md`。

### Paper朱，BV1MA4y1S7kS，16:16

[一学就会的 MMD 换鞋教程](https://www.bilibili.com/video/BV1MA4y1S7kS)。已阅读全文、查看关键帧，并单独查看 12:10、12:20、12:50 附近的权重操作画面。

- [00:00 起](https://www.bilibili.com/video/BV1MA4y1S7kS/?t=0)：按材质提取鞋，清除鞋资产的旧骨骼和物理数据。
- [07:29–09:18](https://www.bilibili.com/video/BV1MA4y1S7kS/?t=449)：脚距不同，需要对整鞋及选定部位移动和缩放；09:00 附近作者明确保留了一些穿模作演示，不能照此认定成品合格。
- [12:05–12:28](https://www.bilibili.com/video/BV1MA4y1S7kS/?t=725)：演示整鞋绑定左右膝骨。局部帧确实显示左ひざ，并非仅字幕误识别。本项目没有照搬，而是使用经动作检查的目标足首D。
- [14:16–15:58](https://www.bilibili.com/video/BV1MA4y1S7kS/?t=856)：检查踩地高度；末尾说明例子选择了本来就接近高跟姿态的脚，不是通用方法。

本地文章：`E:\project\bilibili\output\BV1MA4y1S7kS\P01_712088696\article.md`。

## 0.3 的具体取舍

实际检查刻晴原模型：袜腿网格在脚踝附近结束，鞋内没有完整的裸足网格。对这双闭口硬底鞋，采用替代可见脚面的方式比继续挤整只脚更合适。这是针对当前资产的工程选择，并非上述教程直接给出的算法。

1. 从未改动的来源 PMX 精确分离原鞋，先从旧流程的来源网格中排除，避免被二次适配。
2. 每只鞋只做统一缩放、绕 Z 旋转和平移；用原鞋顶点索引、变换矩阵及边长比例验证鞋型。当前统一缩放为 1.2。
3. 目标网格及形态键、全部骨骼、物理定位一起抬高。最终预设 12 mm；8 mm 的初试在测试动作开头仍有约 3 mm 低于地面的问题，因此补高 4 mm。
4. 用原袜腿真实下边界建立鞋口场，限定在双脚附近，去除闭口鞋内的脚面，不把手或其他身体区域纳入遮蔽。
5. 对保留的下脚踝做平滑 XY 收口，至踝骨以上 45 mm 衰减为零，Z 不变；袜层随后从该表面生成。初试仅遮蔽会留下后跟皮肤碎边，扩大删除会留下缺口；收口试验改善了边界。原脚及受收口影响的区域都在 Blend 保留隐藏副本。
6. 最后把原鞋合并，每只以 BDEF1 绑定目标足首D；鞋底和饰件不参与脚趾权重混合。

源码入口：`addon/mmd_outfit/preserved_shoe.py`，配置入口：`shoe_fit.preserved_closed_shoe`。普通模型调用固定 inspect/fit 接口即可，参数与诊断完整留档。旧配置会明确报 `SHOE_METHOD_WITHDRAWN`。

此方法不提供凉鞋、脚趾弯折或自动裸足切换；隐藏副本用于恢复几何，不是已经绑定好的切换开关。PMX/VMD 抽样检查不包含真实 MMD 动力学；整体衣物仍有其他穿插，不能宣称完整换衣已零穿模。

最终任务、24 帧鞋形测量、动作踩地误差与交付路径见 `OUTFIT_SHOES_V03_2026-10-23.md`。
