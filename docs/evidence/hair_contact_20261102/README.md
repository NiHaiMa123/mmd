# 2026-11-02 头发接触交接的小型证据快照

入口为[最新Astra交接](../../HANDOFF_ASTRA_HAIR_CONTACT_2026-11-02.md)。这些JSON是本机既有回执的原样副本，来源和大小见`manifest.json`。它们用于让Git保留判断依据，不包含模型、工程、视频、PC2、原始粒子数组或逐帧距离大数据。

- `accepted_*`与`long_hair_root_policy.json`：用户认可的无碰撞版、完整参数和根区策略。
- `pr47_result.json`：PR47真实头发225帧检查，23帧超过5cm，最深6.56489cm，未通过。
- `pr47_function_boundary_probe.json`：浅穿越独立复现失败；原基础用例见`pr47_function_probe.json`。
- `pr47_worst_frame_contact_probe.json`：已烘焙f412的静止骨点诊断，不是重建原积分状态。
- `pr47_setup_comparison.json`、`pr47_bake_report.json`、`pr47_cache_integrity.json`：动作保持、社区源码来源及缓存文件头/长度证据；不代表接触通过。
- `upstream_constraint_branch_analysis.json`、`bone_parent_result.json`、`upstream_review.json`：前阶段模式差异与社区接口核对。

社区代码没有在本轮本地修补，也没有合并到官方主线。可用`E:/project/mmd/mmd_repo/scripts/fetch_jiggle_pr47.py --out <新目录>`重新下载固定公开提交，源码SHA256和Git blob SHA1固定校验；该下载脚本不安装插件或运行模拟。

Git克隆只具备代码、文档和小型回执，完整资产仍依赖交接中的本机路径。禁止把这些JSON的通过字段扩展解读为完整角色防穿模通过。
