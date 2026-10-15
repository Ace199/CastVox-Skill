# M0 环境与接口探测报告

日期：2026-10-14（Asia/Shanghai）。范围：M0；仅本机只读检查、公开官方文档访问和本报告写入。M0 调查完成，M1 未开始。

**历史报告时间边界**：上述为 M0 截止状态。用户最新收敛 V1.2 仅 Codex/Claude Code，其他平台调查不转为开发义务；M1 后续已经实现并完成 49 项离线测试，当前代码状态以 [M1_Implementation_Report.md](M1_Implementation_Report.md) 为准。原 M0 观察保留。

## 1. 结论与证据等级

- **Observed**：本机执行命令实际观测到的结果。
- **Docs-Verified**：已打开的官方文档陈述；不是当前账号调用成功的证明。
- **Assumption / Proposed**：建议设计或待实测判断，不构成验收通过。
- **NOT RUN**：没有执行；不能解读为 PASS。

环境具备开始后续离线开发的基本工具。用户补设并更新配置后，指定 MiniMax 配置存在、可解析，包含非空密钥，最新复查 region=cn 且 Base URL 属于当前国内域名类别。**密钥有效性、实名认证、Voice Design 权限、额度、实际字幕质量仍未验证**。没有发送任何 MiniMax 业务 API 请求，包括音色列表查询；没有上传录音、试听、创建、合成、删除或重试。公开文档访问不使用用户凭据。

## 2. 输入完整性（Observed）

已阅读：

- `../doc/MakeSoundSkill_PRD_V1.2_2026-10-14.md`。
- `../doc/MakeSoundSkill_Codex_Test_Instructions_V1.2_2026-10-14 (1).md`，内容标题为 V1.2；用户所写的无后缀文件名不存在，使用此实际文件。

用户后续补充了 `../doc/MakeSoundSkill_PRD_V1.1_2026-10-14.md`，现已阅读并完成与 V1.2 的冲突检查；原先“缺少 V1.1”的阻碍已解除。V1.2 的作用域、优先级、Voice Design MUST 及分期取代 V1.1 冲突条款，不能恢复旧 Session Preference 或在 M1 接入收费 TTS。

输入 SHA-256（用于报告交付时复核原文未被本次工作改写）：

| 文件 | SHA-256 |
|---|---|
| PRD V1.2 | `62acd60a52e849910091cd174f9e4a89b65fced7d31cb48cbe4add1bb1344602` |
| 测试指令 V1.2 (1) | `5c5bddb366e7d74029fb316dd48ecf094857f9e3447394d19cae5222e85a813a` |
| PRD V1.1（后补） | `63f8a608deffa1eb1221db48b8d1f07f1526e77a665618fbc718e611254a0aa6` |

## 3. 本机环境（Observed）

| 检查 | 结果 | 判断/限制 |
|---|---|---|
| 系统 | Windows 11，build 26200；Python 报告 `Windows-11-10.0.26200-SP0` | 已观测；不是对所有 Windows 11 版本的兼容承诺 |
| `python --version` | Python 3.13.10 | 满足 PRD 的 3.11+；第三方依赖兼容性 NOT RUN |
| Python 解释器 | `C:\Users\63201\AppData\Local\Programs\Python\Python313\python.exe` | 可执行；伴随 `Failed to find real location ...` 警告，原因未定位 |
| `py -0p` | `No installed Pythons found!` | Launcher 未发现安装，与 `python` 可用并不矛盾；后续优先使用明确解释器 |
| 标准库导入 | `ssl, sqlite3, venv, json, subprocess` 成功 | 导入检查 PASS；未创建虚拟环境，未测试 TLS 联网 |
| `python -m pip --version` | pip 25.3，Python 3.13 | 可执行；未安装或升级依赖 |
| `ffmpeg -version` | 8.1.2-full_build-www.gyan.dev | 版本调用 PASS；编解码/拼接准确性 NOT RUN |
| `ffprobe -version` | 8.1.2-full_build-www.gyan.dev | 版本调用 PASS；实际文件分析 NOT RUN |
| `git --version` | 2.47.1.windows.2 | 可用 |
| `git rev-parse --is-inside-work-tree` | `not a git repository` | 当前目录尚非 Git 仓库；没有擅自初始化 |
| `codex --version` | codex-cli 0.149.1 | 版本和相关帮助可执行；CLI 自身提示 arg0 临时目录访问被拒，未修改权限 |
| `claude --version` | Claude Code 2.1.295 | 版本和帮助可执行；登录/推理 NOT RUN |
| `importlib.util.find_spec('makesound')` | `False` | 当前解释器未安装 MakeSound；工作区也只有输入文档，目标 CLI 尚未实现 |

已执行可重复的无推理检查：

```powershell
Get-Command py,python,ffmpeg,ffprobe,git,codex,claude -ErrorAction SilentlyContinue | Select-Object Name,Source
py -0p
python --version
python -m pip --version
ffmpeg -version | Select-Object -First 2
ffprobe -version | Select-Object -First 2
git --version
git rev-parse --is-inside-work-tree
codex --version
codex exec --help
codex exec resume --help
codex resume --help
codex app-server --help
claude --version
claude --help
python -c "import ssl,sqlite3,venv,json,subprocess; print('stdlib_imports: PASS')"
python -c "import importlib.util; print(importlib.util.find_spec('makesound') is not None)"
```

这些版本/帮助检查没有启动 Codex 或 Claude 推理会话。Codex 可执行程序自身尝试维护临时目录并报权限警告；本次未手动清理目录或改动账户配置。

## 4. MiniMax 配置二次核验（Observed）

检查位置：`C:\Users\63201\.config\minimax\config.json`；由 `Path.home()` 确认用户目录，没有搜索其他账户或凭据目录。

| 项目 | 最终结果 |
|---|---|
| 初次检查 | 文件不存在；随后用户明确告知已设置 |
| 用户设置后复查 | 文件存在，UTF-8-sig JSON 可解析 |
| 顶层字段 | 原有 `api_key: str`、`base_url: str`；用户后补 `region: str` 已复查 |
| 密钥值 | 仅检查非空，未显示、未复制到报告或其他文件 |
| Base URL 脱敏归类 | 最早检查为 HTTPS 国内旧域名、无路径/查询/userinfo；扩展探测时用户已更新为当前国内域名类别 |
| MiniMax 环境变量 | 当前进程中以 MINIMAX 开头的变量数量为 0 |
| 显式 region 字段 | 本轮扩展探测已复查：`region: str`，规范化值 `cn`；Base URL 属于当前国内域名类别，与声明一致 |
| 凭据修改 | 本次未写入、迁移或规范化此文件 |

**Assumption**：按 Base URL 推断拟使用国内区域；这不是对密钥签发区或权限的认证结论。当前官方国内文档示例已采用 `api.minimax.cn`，历史控制台示例仍见旧域名；不能因此静默替换已有 Base URL，也不能跨区尝试密钥。[国内 TTS 文档](https://platform.minimax.cn/docs/api-reference/speech-t2a-http)、[官方音色控制台](https://solutions.minimaxi.com/voices)。

鉴权探测为 **NOT RUN**：测试指令第 6 节限定 M0 为只读文档调查；即使配置补齐，也未扩大为带 Key 的 API 实测。没有将“配置存在”写成“账号可用”。

**用户已确认**：账号区域应作为配置项，不写死国内。用户现已在只读 MiniMax 配置中补入 region，后续读取它并与 base_url 校验；显式覆盖需记录来源，冲突时阻止请求，不静默修改域名。MakeSound 内部字段属于后续实现设计。本轮没有修改 MiniMax 凭据文件。

## 5. MiniMax 接口核查（Docs-Verified）

详细方法、字段、返回结构、地区与计费见 [Capability_Matrix.md](Capability_Matrix.md)。重要结论：

1. Voice Design 有正式接口；一次请求同时返回 Voice ID 和试听音频，未发现独立的“免费候选预览→正式创建”双接口契约。M0 未调用。[国内设计接口](https://platform.minimax.cn/docs/api-reference/voice-design-design)
2. 国内价格页把音色首次正式合成使用的费用与接口内试听费用区分计量；不能把“生成音色不立即计音色费”解读成整个请求免费。[官方价格](https://platform.minimax.cn/docs/pricing/overview)
3. 查询列表有三类声音；新建音色的列表可见性与正式使用有关，列表缺席不是 Voice ID 无效的充分证据；性别硬筛选不能仅靠名称猜测。[音色查询](https://platform.minimax.cn/docs/api-reference/voice-management-get)
4. 克隆未正式使用的 7 天删除规则有文档依据，但不能直接推广到设计音色或“使用后永久有效”。[复刻接口](https://platform.minimax.cn/docs/api-reference/voice-cloning-clone)
5. 句级字幕有文档支持，但服务默认关闭；当前账号、模型、短句及跨 Chunk 的真实准确性未实测。[TTS 字幕参数](https://platform.minimax.cn/docs/api-reference/speech-t2a-http)

公开文档索引可访问；其列出的三个 OpenAPI JSON（TTS、Voice Design、voice management）经网页读取返回 Internal Error，本机无凭据文档 GET 返回 URLError。因此未获得完整机器可读 Schema；不把折叠子字段的缺失误认为 API 没有这些字段。[官方索引](https://platform.minimax.cn/docs/llms.txt)

## 6. Codex / Claude 等待与恢复

### 已确认事实

- **Observed**：Codex 0.149.1 提供 `exec`、`exec resume <SESSION_ID> [PROMPT]`、交互 `resume` 和实验性 `app-server`。`exec --json` 输出 JSONL；`--ephemeral` 不保存会话，不适合计划中的持久恢复。
- **Docs-Verified**：官方支持以具体 session ID 续跑非交互任务；当前目录非 Git 仓库，默认 CLI 仓库检查还需处理。[非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)
- **Docs-Verified**：app-server 为客户端提供线程/轮次协议及用户输入请求；需要实际客户端接入，不能把任意网页提交等同于该协议。[App Server](https://learn.chatgpt.com/docs/app-server)
- **Observed**：Claude 2.1.295 帮助中有 `--continue`、`--resume`、`--input-format stream-json` 和 `--output-format stream-json`。仅确认本地选项存在；未据此承诺跨 Harness 全链路恢复。

### Proposed：优先使用跨 Harness 的 CLI 等待

`studio start` 实际启动回环服务器并返回 question ID；Agent 调用 `studio wait`；网页只提交结构化回答；wait 读取已提交回答后退出，仍活跃的 Agent 据结果继续。服务器应独立于一次 wait 的生命周期。必须在 M3 验证 Windows 后台进程、浏览器、沙箱网络与进程退出行为。

**不能承诺**：网页唤醒已经结束的 Agent、CLI 保持等待无限长、当前聊天内部 ID 可直接被独立 CLI 恢复，或仅凭 shell 能运行就证明网页问答可用。M0 没有启动 Studio、后台服务器、嵌套模型会话或做实际恢复，均为 **NOT RUN**。

### Proposed：持久待领取 fallback

- 区分 `wait_timeout`（等待器结果）与 `expired`（问题 TTL 已到）；等待超时不能删除问题，也不能覆盖迟到的合法回答。
- 回答保存 `answer_id/question_id/job_id/project_id/revision/selected_voice/explicit_save_intents`，提交幂等，领取采用原子 claim/lease；崩溃后允许恢复。
- CLI/Agent 结束后，网页只显示“回答已保存，待继续”。用户再次进入并明确继续，由 `studio answer get` 或 `jobs resume` 读取；不能显示“Agent 已唤醒”。
- Codex 会话 ID 与 MakeSound job/question ID 分别保存；并发场景禁止以 `--last` 猜目标会话。app-server 适配作为后续选项，核心不依赖其 SDK。
- `applied` 只证明回答生效；收费还必须通过有效的生成授权、冻结快照及单次调度检查。回答重放、保存默认、创建音色和开始配音分别审计。

### 已确认体验：超时后的“继续任务”按钮

用户接受运行中等待、超时后持久待领取，并提出按钮相当于再次发送请求。产品语义可成立：按钮发送**恢复同一个 Job 的请求**，不能重建 Job、重新提交设计/克隆或重发成功 TTS。先校验回答、快照、授权和当前状态；双击、刷新、网络重发使用同一幂等恢复意图。

传输方式仍为 Proposed / NOT RUN：有已接入的本机 Harness 桥接时，由后端校验目标 session/thread 后发送明确的续跑输入；没有桥接时，按钮提供可复制的继续指令，让用户在原聊天再次发送。官方 CLI resume 和 app-server 是可选接入基础，不证明网页已具备向当前 Codex 桌面聊天发消息的权限或接口。[Codex 恢复](https://learn.chatgpt.com/docs/non-interactive-mode)、[App Server](https://learn.chatgpt.com/docs/app-server)。

UI 必须分别显示“恢复请求已接收”和“任务正在继续”；只有运行器实际接管后才显示后者。问题 TTL 已过需重新确认，不能用按钮绕过；等待器超时而问题未过期则可继续。若原生成授权仍有效且内容/参数/费用范围未变，可沿用；仅编辑设置、未知扣费或范围变化不能被一次恢复点击自动升级为收费授权。

## 7. PRD 差异与待决策问题

| 问题 | 已知依据/影响 | 建议；需用户决定 |
|---|---|---|
| 配置区域与域名 | 用户已添加 region，复查为 cn，Base URL 归类国内且一致 | 声明配置已补齐；地区/URL 冲突阻止请求，现有凭据只读；实际账号区域仍未认证 |
| V1.1 基线 | 用户已补充，已阅读 | 文档缺失阻碍解除；仍需实现与实测迁移，不等于迁移验收通过 |
| Voice Design 两阶段 UI | 实际接口把设计和试听放在同一次请求 | 用户已接受“先告知费用并确认→设计且试听→本地采纳/命名”；不是本次收费授权 |
| 女声等硬条件 | 没有已核实的稳定 gender 枚举保证 | 用户已接受有来源标签 + unknown；不明时人工选择 |
| 音色有效期 | 克隆有未使用 7 天规则，设计规则未证实 | 允许本地资产状态 `pending_activation/unknown/expired`；不自动付费激活或重建 |
| 默认字幕 MUST | API 时间戳粒度不保证等于源文句界 | 是否接受无法可靠映射时 `subtitle_failed` 并保留音频；无字幕必须显式选择，不自动引入收费 ASR |
| “SRT 从零开始”含义 | 文件时间轴以零为原点，不保证首个可听字在零毫秒 | 建议解释为各导出独立计时，保留真实首字延迟，不强行将首 cue 移到零 |
| Harness 恢复体验 | 用户已接受持久待领取，要求讨论按钮再次请求 | 采用“继续任务”语义；自动发送需桥接，未接入时复制指令到原聊天；全链路仍 NOT RUN |
| 测试 Python 基线 | 现有 3.13 可用；3.11+ 未做依赖矩阵 | 是否以现有 3.13 开发，并在后续补 3.11 兼容验证；不擅自全局安装 |

## 8. 未验证项与停止点

| 验证项 | 状态/原因 |
|---|---|
| MiniMax Key 鉴权、音色列表、Base URL 实际服务情况 | NOT RUN；M0 保守保持文档调查范围 |
| 账号认证、Voice Design 开通、限额与余额 | NOT RUN；无账户后台检查 |
| 实际 TTS、字幕下载与时间单位、试听计费账单 | NOT RUN；收费或依赖真实合成 |
| clone/design 创建、复用、长期生命周期 | NOT RUN；禁止创建，长期观察另需安排 |
| Studio 真实 URL/网页提交/跨进程领取/重启 | NOT RUN；M3 才实现和验收 |
| Codex/Claude 实际推理与会话恢复 | NOT RUN；仅版本/帮助与官方文档，不消耗新推理额度 |
| makesound doctor、单元测试与目标 CLI | NOT RUN；M1 未实现，不把环境缺包称为产品 Bug |

后续建议及 Schema 草图见 [Testing_Plan.md](Testing_Plan.md)。原始 M0 交付三份 Markdown，本轮修订另增加两份 Adapter/集成设计；未进入 M1，也未修改 PRD、MiniMax 配置或创建产品代码。

## 9. 交付文件验证（Observed）

交付文档以 UTF-8 读取检查；Markdown 代码围栏成对、本地相对链接目标存在；内嵌 JSON 示例可解析。原始输入的 SHA-256 与各自读取时一致；敏感值本机扫描只输出检查结果。最新修订后的工作目录包括三份输入和五份交付文档，新增 KW-01 至 KW-10 覆盖检查。上述为文档验证，不是产品/API/端到端测试通过；Mermaid 架构图仅作为文档源码，未另做渲染验收。

## 10. V1.1 补读结论（Observed / 文档基线）

- §12.1 明确 source_range 是 Unicode 字符的 `[start,end)`，不能可靠定位时允许 null 并保留哈希；后续测试需覆盖 emoji、中文与 JS UTF-16/Python Unicode 索引转换，不能伪造偏移。
- §11.3 提供 1.1 Preset：provider/model/voice_id、voice、export、script_processing、pause。迁移应把声音引用及声音参数迁入 default_voice，把导出/脚本/停顿归入 project_settings；保留模型字段的明确作用域，不丢 preset_name 或未知字段，原文件备份且不覆盖。
- V1.1 没有在示例中给出区域；不得无依据给旧 Voice ID 填 cn。迁移需要已确认的区域配置，否则报告待补配置。
- V1.1 §11.2 要求采用系统用户数据目录（Windows 可用 LOCALAPPDATA），项目内不能保存录音、私密原文或令牌；缓存清理不能误删默认与资产。
- V1.1 的 Session Preference、Voice Design 暂缓、M1 直接接 Provider、旧 `--studio-session` 等与 V1.2 冲突，均按 V1.2 取代。关闭浏览器不撤销已提交回答，wait 超时与问题 TTL 分离，采用 V1.2 和本次用户确认的恢复语义。

## 11. M0 扩展：Kimi、WorkBuddy、豆包、DSH / DeepSeek

本轮按用户要求增加四类 Agent 平台调查，日期同为 2026-10-14。豆包已由用户明确限定为**桌面端／网页版**；不以扣子、TRAE 或火山方舟替代。Kimi 分清普通聊天与 Kimi Code；DSH 采用 DeepSeek 官方 `deepseek-ai/deepseek-harness`，不以第三方同名 CLI 或 DeepSeek 聊天站替代。这是新增调查范围，不代表新增平台都已通过兼容验收，也不自动将全部适配纳入 M1。

**范围更新**：此前曾规划四平台；最新用户决定 V1.2 仅 Codex/Claude Code，Kimi Work/DSH/WorkBuddy/豆包保留研究但不开发 Adapter。历史身份区分仍有效：kimi_work 是普通桌面 Work 模式，不等于 kimi_code。

### 11.1 本机只读结果（Observed）

- `shutil.which` 检查 `kimi/workbuddy/doubao/dsh/codebuddy` 均未在当前进程 PATH 发现。首次 PowerShell Get-Command 无匹配返回非零，随后用逐项 Python 检查确认。**不等于应用未安装**，也不是兼容性失败。
- `Get-StartApps` 命中“Kimi”和“卸载 Kimi”；仅能证明有对应开始菜单条目，未核验可执行程序、版本或是否为 Kimi Code。
- `node --version` 为 v24.12.0；`npm --version` 为 11.6.2；仅版本调用，无安装和下载。
- 没有启动这些平台、读取其账户/历史会话、安装 Skill/MCP、调用模型或发消息。平台登录、版本帮助、长进程等待、真实恢复全部 **NOT RUN**。
- MiniMax 配置本轮复查已含 `region=cn`，Base URL 归类为当前国内域名。此前“缺少 region/旧域名”的记录属于用户修改前观测；当前声明配置一致，仍未发鉴权请求。

可重复命令：

```powershell
python -c "import shutil; print({n: bool(shutil.which(n)) for n in ['kimi','workbuddy','doubao','dsh','codebuddy']})"
Get-StartApps | Where-Object { $_.Name -match 'Kimi|WorkBuddy|豆包|DeepSeek|DSH' } | Select-Object -ExpandProperty Name
node --version
npm --version
```

### 11.2 Kimi Desktop / Kimi Work（修正目标）

**Docs-Verified**：官方将 Kimi Work 定义为 Kimi 电脑客户端 Windows/Mac 的 Work 模式，支持上传本地 Skill、本地文件、浏览器与运行代码的授权控制。[Work 产品介绍](https://www.kimi.com/help/kimi-work/overview)。官方入门与个人插件文档确认可以创建自定义插件。[入门指南](https://www.kimi.com/academy/kimi-work-getting-started)、[个人插件](https://www.kimi.com/en/help/plugins-and-skills/create)。

**Product-Confirmed / Proposed**：使用独立 kimi_work Adapter，首阶段是本地 Skill + 统一 Python CLI，MCP/Plugin 可选，不部署公网服务。Core、音色库、快照、Question/Answer/ResumeIntent 与其他平台相同。此前 Kimi Code CLI 优先的判断不符合用户目标，已更正；其 session 命令、等待上限、Git Bash 默认值不能移用于 Kimi Work。

**Observed** 仍仅是开始菜单“Kimi”条目；**NOT RUN** 为真实客户端版本/Work 模式、Skill 安装/触发、本机 CLI、真实 Studio、等待/恢复与权限测试。代码可执行的产品能力不等于已有外部网页向原聊天投递回答的协议。本阶段不尝试自动发消息；采用短轮询、持久回答、用户再次发送含 job_id 的继续指令，原生消息桥接仅作待验证增强。详见新增设计与 KW-01 至 KW-10 测试计划。

### 11.3 WorkBuddy（Docs-Verified / 推论）

官方说明支持授权的本地任务与 Skill 导入；开放平台同时提供 MCP+Skill 和 CLI+Skill 连接器路径。[产品介绍](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Product-Guide)、[技能](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)、[连接器](https://open.workbuddy.cn/docs/connector)。**本地 Skill 试接入**与**正式市场连接器发布**需要分别验收：后者有跨平台/runtime/auth 元数据要求，不能把 Windows 上能运行 Python 视为市场包合规；长期自填 Token 的接入另有 MCP 规则，不把 MiniMax Key 填进公共包或上传到云端。

补查到正式 Open API：`GET /openapi/v2/localassistant` 查在线；`POST /openapi/v2/localassistant/message` 发送消息，`msg_type=text|permission_response`；OAuth scope 为 `user.localassistant.readable/invokable`，需开发者应用和用户授权。[官方 Open API](https://open.workbuddy.cn/docs/openapi)。这是“继续任务”按钮的**有文档依据的可选桥接**，但请求示例没有证明可定位任意原桌面聊天；投递关联、在线/离线、审批 requestId 与 MakeSound question_id 映射、幂等和费用均待实测。不能用云端 task API 代替本机 Job 恢复。

同站 `/docs/cli/headless` 明确是 **CodeBuddy Code** 的 CLI，不能据此虚构 `workbuddy --resume` 或认定两个产品共享 session ID。[CodeBuddy 文档](https://www.workbuddy.cn/docs/cli/headless)。本轮未申请 OAuth、创建应用、发消息或消耗积分。

### 11.4 豆包桌面端／网页版（Docs-Verified 与未证实项）

字节 Seed 官方公告列出豆包电脑版/App 的“办公任务”入口，但不是自定义 CLI、Skill 导入或恢复协议文档。[官方公告](https://seed.bytedance.com/zh/blog/seed2-1-officially-released-advancing-ai-productivity)。`https://www.doubao.com/` 跳到 `/chat/`，官方 `/download/` 可打开但网页提取均为空；本轮未做登录后 UI 检查，不能凭此判断客户端功能不存在。

没有取得能证明以下能力的官方接口契约：运行本机 Python/FFmpeg、导入自有 SKILL.md、读取宿主项目目录、长等待回环网页、恢复特定 Agent 任务、外部续跑消息入口。全部记为**尚未证实**，不是“明确不支持”。云端代码执行或模型能用工具，也不等于能访问这台 Windows 的配置或 127.0.0.1。

Proposed：先列为待实机确认的平台；若无本机执行连接，只能让用户确认文稿后手动移交 MakeSound 本机 CLI，不能把这称为豆包原生集成。未引用仿冒豆包域名、第三方下载页或未经核实的 CLI；不以新闻所述 GUI 能力替代稳定接口证据。

### 11.5 DSH / DeepSeek Harness（Docs-Verified / 推论）

DeepSeek 官方仓库明确 DSH 是其开源 Agent Harness，目前为 developer preview、可能破坏兼容。[官方仓库](https://github.com/deepseek-ai/deepseek-harness)。官方 help 提供 `dsh --profile headless --session-id <id> "continue"`、`--json`，以及 SDK/ACP 入口；未知 session ID 报错。[官方 CLI help](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cli-help.md)。不能臆造所有 profile 通用的 `dsh resume`，也不在 M0 执行 npx 导致下载或配置初始化。

工具目录含 Bash/PowerShell、文件、后台任务能力；Skills 插件可加载目录 SKILL.md，存在插件组合条件。[工具目录](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/tool-catalog.md)、[Skills provider](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md)。因此 DSH 是优先候选，但必须记录所选 profile、版本及插件：不能把包存在当成当前 Agent 已启用。其非 Git 项目发现会使用 cwd，MakeSound 的可信项目根检查不能交给该默认逻辑。

文档来自当日 master 分支，尚未固定发布版或验证 Windows 执行后端、前台超时、后台完成通知、SDK 精确 session 投递。DSH 自带 Web UI 不是 MakeSound Studio；恢复 Harness session 与恢复 MakeSound Job 也必须分别验证。

### 11.6 差异、优先级与剩余决策

| 平台 | 建议接入层级（非完成状态） | 当前主要阻碍 |
|---|---|---|
| Kimi Work / kimi_work | 已延期，本地 Skill/CLI 方案保留研究 | 真实 Windows 桌面 KW-01 至 KW-10 未执行；不继承 Kimi Code 规则 |
| WorkBuddy 本地桌面 | 保留 M0 调查，暂非首批 | 未实机测试；市场连接器包装单独评估；OAuth 与原聊天定位未验证 |
| 豆包桌面端／网页版 | 保留 M0 调查，暂非首批；必要时人工移交 | 缺少自有 CLI/Skill/续跑的官方契约与账号实机证据 |
| DSH / DeepSeek Harness | CLI+Skill 优先候选 | 未在 PATH 找到；开发预览需固定版本/profile；SDK/Windows 实测 |

平台扩展调研结束时新增了 Adapter/Integration 设计与 KW 测试计划，未安装或执行平台模型任务。随后用户收敛 V1.2 仅 Codex/Claude Code 并授权 M1；其他平台 E2E 仍 NOT RUN、开发延期。当前 M1 核心结果见 [M1_Implementation_Report.md](M1_Implementation_Report.md)，原调研证据不当作当前开发义务。
