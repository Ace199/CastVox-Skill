# MakeSoundSkill V1.2 — 平台集成计划

日期：2026-10-14（Asia/Shanghai）。最新范围：**V1.2 仅验收 Codex 和 Claude Code，其他平台设计保留但延期。** M1 核心/CLI 已实现并完成离线测试，见 [实现报告](M1_Implementation_Report.md)；真实平台模型任务、安装/上传 Skill 或 Plugin、MiniMax 调用仍 NOT RUN。

## 1. 首批范围与产品身份

| 平台标识 | 首批目标 | 基础接入 | 当前证据与限制 |
|---|---|---|---|
| codex | Codex | Skill + 本地 Python CLI | Observed：此前版本/帮助；实际问答恢复 NOT RUN |
| claude_code | Claude Code | Skill + 本地 Python CLI | Observed：此前版本/帮助；实际问答恢复 NOT RUN |
| kimi_work（延期） | 非本版验收；保留 Windows Work 调研 | 未来可用同一 CLI，本次不开发 | Docs-Verified 仅说明能力，非当前交付 |
| dsh（延期） | 非本版验收；保留调研 | 未来可用同一 CLI，本次不开发 | 文档与本机探测存档，非当前交付 |

首批只有 Codex/Claude Code。Kimi（含 Work/Code/网页）、DSH、WorkBuddy、豆包仅保留扩展研究。下文 Kimi 最小闭环为延期存档，不是当前开发步骤，不安装任何平台插件。

## 2. Kimi Work 官方依据与核实范围

| 结论 | 证据级别 | 来源/验收边界 |
|---|---|---|
| Windows 客户端 Work 是本地 Agent；有本地 Skills、文件和浏览器能力 | Docs-Verified | [Kimi Work 产品介绍](https://www.kimi.com/help/kimi-work/overview)；不证明本机版本已具备全部能力 |
| 可直接使用本地内容，项目权限可配置；支持自定义插件流程 | Docs-Verified | [官方入门](https://www.kimi.com/academy/kimi-work-getting-started)；不指定未经核实的安装路径 |
| 可用 Plugin Builder 创建/转换个人插件 | Docs-Verified | [官方个人插件说明](https://www.kimi.com/en/help/plugins-and-skills/create)；这是可选包装，不要求调用 Builder 才能使用 Core |
| Skill 是可复用操作说明与可选脚本资源，包含 SKILL.md 结构 | Docs-Verified | [Skills 说明](https://www.kimi.com/help/plugins-and-skills/what-are-skills)；具体桌面上传格式/触发/资源路径须实测 |
| 本机开始菜单有“Kimi”条目 | Observed | 仅先前元数据；客户端实际版本、Work 模式、权限 NOT RUN |
| 等待网页回答、超时后继续、双任务隔离、指定原会话投递 | NOT RUN | 不能继承 Kimi Code CLI 的参数、时间限制、session ID 或 Git Bash 默认值 |

官方所述本地执行足以支持优先评估本地 Skill/CLI，不构成必须部署公网 MCP 的理由。运行代码的可授权能力与某次 Python/FFmpeg 确实可执行、浏览器能访问 localhost、网页能给 Agent 投递消息分别验收。

## 3. 阶段与前置条件

| 阶段 | 内容 | 完成标准 | 当前状态 |
|---|---|---|---|
| 本轮 M0 修订 | 统一 Adapter、平台标识、协议与 KW 用例；同步旧报告范围 | 文档一致、JSON/链接/原始输入检查 | 文档交付；无平台执行 |
| M1 | 统一数据/配置/快照与 CLI 基础、凭据只读、可信项目根 | 49 项临时目录离线测试全部 PASS；无宿主 SDK | 已完成，详见 M1 报告 |
| M2 | 多声音 Chunk、快照、Fake Provider、字幕/缓存/续跑 | 本地 fixture 验证；实际 Provider 零调用 | NOT RUN |
| M3 前置 | 可安装 Skill 包与真实 Studio/Question/Answer/ResumeIntent | 本机 CLI/网页集成准备齐；无虚构地址/ID | NOT RUN |
| 延期扩展 | KW-01 至 KW-10 等其他平台方案 | 不属于本版验收，不投入当前开发 | NOT RUN / 延期 |
| 跨 Harness 验收 | Codex、Claude Code 共用项目/资产/快照 | 运行记录按平台、版本、权限分别保存；CLI 子进程测试不代替真实 Agent 闭环 | NOT RUN |
| 可选增强 | 有正式协议时评估本机 MCP/Plugin 包装或原聊天桥接 | 另行调查与测试，基础手动恢复始终可用 | NOT RUN，不是基础阻塞 |
| M4 | 真实 MiniMax 合成/设计/复刻/字幕 | 显式收费授权与受控预算，独立 Provider 验收 | NOT RUN |

因此，“下一步做最小闭环”是后续执行方向，不能在当前没有 makesound/Studio 实现时写成可立即运行的命令。Fake Provider 模拟音频和时间戳不代表真实声学/API 能力通过。

## 4. Kimi Work 最小闭环计划

前置：真实客户端版本与 Work 模式已确认，权限遵守用户设置；CLI/Studio/Fake 实现可用，使用临时项目和假 Voice ID，阻断 Provider 外部网络。平台推理本身可能消耗 Kimi 额度，执行时记录，不能称为所有服务完全零成本。

1. 按客户端实际入口导入本地 Skill；记录包格式、版本/哈希与触发证据，验证 SKILL.md 被读取。
2. 由 Skill 调用明确的本机 Python，执行只读诊断、配置解析；验证两临时项目音色库独立，不读取真实 Key。
3. 缺声音触发真实 Studio，返回 OS 实际监听地址；在本机浏览器打开并检查 Question/Job 关联。
4. 短 wait 仍在运行时提交答案，验证退出结果与 Agent 后续动作，Fake 调用数符合预期。
5. 独立测试 wait 已结束后再提交，页面仅提示已保存；用户发送含实际 job_id 的“继续配音任务”，领取同一 Answer 并恢复同一 Job。
6. 双击/重复提交/重复继续只产生一次调度；再覆盖两个项目、两个任务、权限拒绝及进程重启。

不模拟用户向原聊天自动发消息；不为了制造“自动恢复”绕过权限、使用未公开内部接口或开启公网端口。若等待上限未知，先测短等待并记录真实行为，不能套用 CLI 文档数字。

## 5. 平台差异、失败与交付记录

- Adapter 显式提供 project_root、解释器和 Shell 信息；宿主不能提供可信根时，仅允许本次/全局选项，禁止随机写目录。
- MakeSound job_id 是业务恢复主键；native_session_ref 可选且平台隔离。手动进入原聊天或新聊天恢复同一 Job，不代表宿主会话已由程序恢复。
- 原网页提交只更新问答/明确保存意图；付费操作由 Core 根据有效授权和冻结快照决定。恢复按钮不能自动重发未知扣费请求。
- 单个平台失败保留原始 Job/Answer、缓存及诊断，不改变共享 Schema、不静默换声或关闭字幕。
- 证据记录平台、产品、版本、Work 模式、审批设置、执行位置、CLI 版本、项目/Job/Question/Answer 关联、Fake 调用数及终态。记录脱敏，不保存 Key、完整 token 或私密原文。
- 每项单列 Docs-Verified / Observed / NOT RUN；PASS 需要实际执行证据，未知与未执行不等同 FAIL。KW-10 若无正式桥接，记录“未验证自动接口，手动路径已测/未测”，不虚报自动恢复。

## 6. 与现有文档的关系

核心规则沿 V1.2 与已确认修订，V1.1 仅补齐不冲突部分。设计见 [Harness_Adapter_Design.md](Harness_Adapter_Design.md)，当前测试见 [Testing_Plan.md](Testing_Plan.md)。M0 扩展研究保留，最新范围均以 Codex/Claude Code 两平台为准；当前核心实现结果见 [M1_Implementation_Report.md](M1_Implementation_Report.md)。原始 PRD 文件保留不改。
