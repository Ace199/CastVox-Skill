# MakeSoundSkill — 产品需求文档（PRD）

> **版本**：V1.1（项目配置与自动启动修订版）  
> **日期**：2026-10-14  
> **状态**：产品需求基线，待开发环境/API 实测  
> **产品定位**：Agent-Native Audio Generation Skill  
> **首版 Provider**：MiniMax  
> **目标环境**：Windows 11 优先；Python CLI；支持 Codex / Claude Code 等能够读取 Skill 指令并执行本地命令的 Harness  
> **核心交付**：跨 Harness Skill + CLI + 自动启动本地 Voice Studio + 项目/会话/全局配置 + MP3/WAV 音频 + SRT 字幕 + 可续跑任务记录

---

## 0. 文档约定与 V1.1 变更

- **MUST / 必须**：V1 验收条件；**SHOULD / 应当**：优先实现，允许合理简化；**LATER**：暂不实现。
- **Harness**：Codex、Claude Code 等可读取 Skill 指令、获取对话上下文并执行本地命令的 Agent 宿主。
- **Skill**：触发规则、文本整理协议、CLI 使用指令；不依赖独立的文本模型 API。
- **Provider Adapter**：MiniMax HTTP API 封装；不允许把凭据暴露给 LLM 输出。
- **Voice Preset**：模型、音色、声音参数、导出和字幕参数的有效完整集合。
- **Global Preset**：用户跨项目使用的持久默认值；**Project Preset**：当前项目内可持久使用的默认值。
- **Session Preference**：用户明确选择“本会话沿用”的设置；**Task Override**：仅当前一次生成有效的参数；**Job Snapshot**：任务开始后冻结的最终配置，续跑时沿用。
- **Script Manifest**：结构化口播稿与源文本索引；**Output Manifest**：实际音频、字幕、合成 Chunk、缓存、错误、任务状态记录。
- **Project Root**：当前 Harness 传递或经可靠规则确定的项目根目录，绝不能猜测任意目录并写入。

### V1.1 相对 V1.0 的产品决策更新（以本版为准）

1. **删除“每次都询问是否使用默认”的旧规则。** 同一会话或项目存在有效配置，且用户未提出变更要求时直接继承。
2. **增加项目级持久化**：`<project>/.makesound/preset.json`；首次在有效项目中设置时，网页默认勾选“同时保存为当前项目默认”，用户可以取消。
3. **增加全局继承**：项目无默认时优先检查用户全局预设；全局也不存在时，自动启动本地 Voice Studio 并把 CLI 实际返回的可访问地址交给用户。
4. **明确按钮语义**：“应用于本次生成”与“将当前设置保存为默认”仍是两个独立动作；首次配置勾选保存项目默认时，应用本次可以**同时**保存项目默认，但必须让用户明确看见并可取消该勾选。
5. **配置作用域与任务快照分离**：本次覆盖不会污染项目默认；项目默认不会被会话中的临时修改静默覆盖；已启动任务不会被后续改预设影响。
6. **新增网页启动、恢复、超时、会话识别及无项目根目录的降级行为**；不会编造监听地址，也不会声称 Skill 文本自身可以开启服务。
7. 保留 V1.0 其余已经确认的音色库、复刻、口播结构化、剪辑拆分、字幕默认开启及 CLI 安全性要求。

## 1. 产品概述

### 1.1 背景

用户先在 Codex / Claude Code 等 Harness 中生成并确认教学脚本、视频旁白或其他文案，随后才需要语音。在线 TTS 调试平台要求复制文本、重复调整参数、下载/拆分文件，不适合构成 Agent 的日常音频输出能力。同一项目通常需要维持固定的音色和剪辑格式，反复询问默认参数会降低效率。

### 1.2 产品目标

用户确认文案后，只需说“帮我生成音频”，Harness 即可**自动读取现有会话/项目/全局配置**，清理非口播部分、合理安排停顿，再由 Python 调用 MiniMax 生成供剪辑的音频和字幕。若没有任何有效默认配置，Harness 自动启动本地 Voice Studio 并向用户返回真实地址；首次设置默认可保存到当前项目，后续直接复用。

基本原则：

1. **Agent 理解文本，代码可靠执行**；默认复用 Harness 的推理能力，不额外调用其他 LLM API。
2. **有配置则复用、无配置才引导**；不把系统内置初始建议值等同于用户已确认的默认预设。
3. **项目优先、会话可覆盖、全局兜底**；任务参数冻结、持久配置与临时配置解耦。
4. **默认不擅自改写**用户已经确认的文案；清理明确非口播信息，保留原意、术语、版本号和必要步骤。
5. **脚本结构、合成粒度和导出粒度分离**；保留 Document → Paragraph → Sentence 层级，默认按段落导出。
6. **默认生成句级 SRT 字幕**，音频和字幕需依据最终输出时间基准保持一致。
7. **首版只对接 MiniMax**，但 SKILL.md、脚本协议、CLI 不依赖 Codex 专有接口。
8. **本地网页是配置工具而非每次生成的必经页面**；只有首次初始化、主动修改设置和需要修复配置时才打开。

### 1.3 成功标准

- 新项目第一次生成且无项目、全局、会话配置：返回真实本地 Voice Studio 地址；用户完成配置后生成 MP3/SRT。
- 用户首次设置时保持“同时保存为当前项目默认”勾选，第二次及重新打开项目后直接使用该配置，无重复询问。
- 用户明确选择“仅本次”不会写入项目或全局默认；有会话范围选择时，其生效时间被明确告知。
- 已配置项目在 Codex 和第二个兼容 Harness 中都能通过 CLI 读取相同项目 Preset，跨 Harness 核心功能一致。
- 同一脚本支持 whole / paragraph / sentence 三种最终导出。
- 默认字幕开启；失败任务准确报告，缓存、续跑与局部重生成可靠。
- API Key 不出现在 Agent 生成的 JSON、终端日志、网页预览、Git 仓库和下载产物中。

## 2. 目标用户与典型使用场景

**主要用户**：使用 Codex、Claude Code 或其他 Harness 创建教学文案、CG Pipeline 视频、产品演示、旁白或短视频配音的内容制作者。

**场景 A｜项目首次使用，没有任何默认预设**

用户在项目 A 已确认脚本 → 说“帮我生成音频” → Harness 解析项目目录和配置 → 都不存在 → 调用 `makesound studio ...` 启动服务 → **读取 CLI 实际输出的 URL 并发给用户** → 用户设置音色/输出/字幕（“同时保存为当前项目默认”默认勾选）→ 点击“应用于本次生成” → 保存项目 Preset + 本次 Session 快照 → 自动继续生成段落 MP3 与 SRT。

**场景 B｜同一项目第二次生成**

在项目 A 再次说“把这篇生成音频” → 没有特殊要求 → 解析有效项目默认 → **直接提取口播并生成，不询问、不启动网页**。即使退出 Codex 后再次打开该项目，仍然生效。

**场景 C｜同一会话临时修改**

项目默认青年男声，用户说“这次改成女声、逐句生成” → 只覆盖本次任务 → 完成本次任务后项目默认维持原值。若用户说“这次会话后面都用女声”，则保存 Session Preference；下一个新会话回到项目默认。

**场景 D｜切换到另一个项目**

进入项目 B → 有 B 的项目默认则采用 B；否则继承全局默认；全局也不存在时才启动 Studio。A 的项目配置不得泄漏或自动应用于 B。

**场景 E｜配置网页主动修改默认**

“打开声音设置” → 无论当前有无默认，打开网页，但**不启动 TTS**。用户切换音色并按“将当前设置保存为默认”，写入其选定的项目或全局范围，不自动开始生成；下次生成自动继承。

**场景 F｜逐句剪辑与局部重生成**

用户“把第三段第二句话单独重新生成” → Agent 更新对应结构化句子；若原合成粒度为 sentence 则只请求该句；若原段落整体合成则提供“替换句素材”或“重建该段落”，绝不假装无损替换整段中间部分。

**场景 G｜复刻音色**

用户上传其有权使用的录音并复刻一次 → 保存 Voice ID → 后续音频仅使用 Voice ID 调 TTS，不重复上传样本（远程 Voice ID 仍需有效）。

## 3. 范围与优先级

### 3.1 V1 MUST（P0）

| 编号 | 能力 | 验收条件 |
|---|---|---|
| P0-01 | 跨 Harness 的 SKILL.md + Python CLI | Codex 和至少另一个 Harness 可运行同一核心命令 |
| P0-02 | 配置解析与作用域覆盖 | 本次覆盖 > 会话偏好 > 项目默认 > 全局默认；新任务读取有效配置 |
| P0-03 | 项目持久配置 | `.makesound/preset.json` 原子保存并在重启后复用 |
| P0-04 | 首次无配置自动启动网页 | 返回实际 URL、等待应用、超时/取消处理 |
| P0-05 | 首次项目设置默认勾选保存 | 可取消；临时修改不得污染持久默认 |
| P0-06 | Voice Studio 三页 | Voices / Settings / Outputs |
| P0-07 | 音色查询/检索/试听与本地缓存 | 缓存命中不发送重复生成请求 |
| P0-08 | 声音参数与模型兼容性显示 | 不支持的情绪可见但禁用，CLI 同步校验 |
| P0-09 | Agent 提取口播、语义分段与停顿 | 默认不改写；保留源文与剔除记录 |
| P0-10 | Script Manifest Schema 与确定性校验 | 严格 JSON，不接受不合法/缺失内容 |
| P0-11 | 三种音频输出模式 | 整篇、段落、逐句；默认段落 |
| P0-12 | 默认开启字幕 | 句级 SRT 默认、时间戳与最终文件一致 |
| P0-13 | 音频缓存、任务记录、续跑和局部重生成 | 有效缓存复用，失败可恢复 |
| P0-14 | 读取已有 MiniMax 本机 API Config | 只读、脱敏、不覆盖未知字段 |
| P0-15 | MiniMax 音色复刻与 Voice ID 复用 | 有授权声明，不重复上传原始录音 |
| P0-16 | 完整安全边界与可靠错误提示 | 回环监听、随机会话令牌、无假地址/密钥泄露 |

### 3.2 V1 SHOULD（P1）

- 术语发音词典的轻量编辑和复用，支持 CG 软件/技术缩写。
- 词级字幕作为可选高级模式；真正支持的模型与返回字段需要集成测试确认。
- Outputs 显示片段播放、错误、完成数、文件路径和局部重新生成。
- LaTeX 朗读、文本规范化、语言增强等高级设置，默认收起。

### 3.3 暂不进入 V1

- 火山及其他厂商的 API 实际对接；仅保留 Provider Adapter 边界。
- 音色设计（文本创建新音色）、音乐/视频/语音识别、混合音色、实时流式对话。
- 多用户云端部署、团队同步、远程音色删除、NLE 工程文件导出、音素级对齐。
- 无可靠时间信息时臆造精确的字幕时间戳。

## 4. Harness 调度与配置决策（V1.1 核心）

### 4.1 触发与输入文本定位

触发示例：“帮我生成音频”“把刚才确认的稿子配音”“逐句输出音频”“给这一段配音”。先定位**最近一份用户已经确认且指向明确**的文本版本。不得擅自把整段对话、代码执行日志或用户没有确认的草稿全部当作口播稿。多个候选文本或版本不明确时只询问源文本，不启动 TTS。

### 4.2 配置继承与覆盖规则

对**新任务**，按字段合并生效配置，顺序由高到低：

1. **Explicit Request / Task Override**：用户本次明确指定的音色、导出模式、字幕等参数，生命周期仅当前任务；明确提出“后续本会话沿用”才提升为会话偏好。
2. **Session Preference**：用户明确设置的当前 Harness 会话偏好（需有效 Session ID，不能拿任意临时任务配置冒充）。
3. **Project Preset**：项目根目录 `.makesound/preset.json` 中持久保存的默认配置。
4. **Global Preset**：`~/.config/makesound/presets.json` 中持久保存的默认配置。
5. **Built-in Suggestions**：首次配置表单所展示的建议值（如按段落、字幕开启），**仅为 UI 初始值，不算“用户已建立的有效默认”**，不能因为它们存在就跳过首次设置。

每层可只覆盖部分字段，缺失字段按下一层继承；但最终运行必须满足 voice/model 等必需参数且通过能力校验。同一字段以最高优先级为准。**创建任务后将合并结果冻结为 Job Snapshot**；重试和续跑从 Snapshot 恢复，不再受之后的默认修改影响。显式用户请求“重新配置本任务”除外。

**适用例外**：如果无任何已保存预设，但用户本次明确提供了所有必需配置参数，并要求直接生成，可以不启动 Studio（仍需调用前校验）；本次设定不自动持久化。默认情况下，任何必需项缺失都应启动 Studio 引导选择。

### 4.3 是否打开 Voice Studio（真值表）

| 状态 / 请求 | 预期行为 |
|---|---|
| 项目有有效默认，用户说“生成音频” | **直接生成**，不询问也不打开网页 |
| 本会话显式已设偏好，用户无新要求 | 使用会话偏好覆盖项目/全局，直接生成 |
| 当前项目无预设，但全局有效 | 直接继承全局，不强制为项目写一份副本 |
| 所有默认都不存在，缺少必要设置 | **启动 Studio**，返回真实 URL，等待用户配置 |
| 项目预设存在但损坏/缺失必需字段，且下层可补全 | 合并后仍有效则继续；提示可修复缺陷，禁止静默忽略不可兼容字段 |
| 解析后无有效音色或配置互相冲突 | **停止收费合成，打开 Studio 修复**或明确报错 |
| 用户说“这次逐句输出” | 覆盖 `export_mode`，其余自动继承，不重复询问 |
| 用户说“这次换声音”但未指定哪种 | 启动 Studio 并等待新音色选择 |
| 用户说“打开设置” | 启动 Studio，不自动合成 |
| 用户说“使用默认设置” | 解析项目/全局等有效默认并生成；不存在时进入首次配置 |
| 用户说“这次别保存” | 强制本次应用，不写项目或全局默认 |
| 用户说“以后这个项目都用这套” | 写入项目默认（若没有可识别项目根则询问保存范围） |
| “继续上次失败任务” | 使用任务 Snapshot 续跑，不重新解析默认 |

### 4.4 项目根目录定位与安全边界

**来源顺序**：用户明确提供的项目目录 > Harness 显式 Workspace/Project Root > 从当前工作目录向上找到且唯一可信的项目标识（例如 Git 根，必须确认与工作目标一致）。不能简单把进程当前路径、`C:\Windows\System32`、用户 HOME、临时目录视为业务项目。调用方需显式传 `--project` 或通过 SDK Adapter 传项目上下文；不可靠时不得擅自写项目目录。

- 同一个项目从子目录调用时，归一化到相同 canonical root。使用受限的目录解析，避免写入意外位置。
- 识别仓库之外的非 Git 项目时允许用户显式指定路径。
- 若无有效 Project Root：仅允许 Session Preference 和 Global Preset；首次设置默认保存**不能假装写入项目**，网页应展示“未检测到项目”，允许本次或全局保存。
- 配置文件不存在、无效与存在但某字段覆盖有效下层配置是三种不同状态。对未知字段保留，对必需字段校验，不静默切换声音。

### 4.5 标准端到端流程

1. Harness 定位已确认文本 + Project Root + Session ID（可用时）。
2. 调用 `makesound config resolve --project ... --session ... --json`，获取状态 `ready | needs_setup | invalid` 和生效配置的**脱敏摘要**。
3. `ready` → 直接完成 Agent 口播处理；`needs_setup` → `makesound studio start --project ... --session ... --purpose setup --json` 并读取**实际返回**的本机 URL；`invalid` → 展示具体可修复项，再进入 Studio 或停止。
4. 首次项目设置页面默认勾选“同时保存为当前项目默认”；用户仍可取消，仅用于本次。
5. 点击“应用于本次生成”后，Studio 校验配置，必要时原子保存项目默认，再生成本次任务快照和 `applied` 会话状态。
6. Harness 从 `studio wait` 或状态查询获取 `applied`，按 Script Manifest Schema 整理文稿；歧义删除必须先确认。
7. CLI 执行 MiniMax 合成、字幕、缓存、导出，并返回真实的文件清单与错误信息。
8. 关闭网页或超时：Session 变为 `cancelled/expired`，**不得**用未确认表单或系统建议值自动启动付费合成。

### 4.6 首次设置后的持久行为

- 首次在项目 A 设置并勾选保存：项目 A 的 `.makesound/preset.json` 必须被写入并可在重启后读取；后续在项目 A 无特殊要求时不再询问。
- 同一个项目 A 在不同 Harness 中只要都能访问相同文件路径，必须得到一致的 Project Preset。
- 项目 B 不得自动读取项目 A 的配置；项目 B 无默认则继承全局或启动首次配置。
- 仅本次设置不得冒充 Session Preference；只有明确选择“本会话沿用”才使后续本会话调用继承这一组临时值。
- 对用户明确指定的“只用一次”“恢复项目默认”“改成新的项目默认”等指令提供可预测的持久化语义。

## 5. Agent Script Processor

### 5.1 输入类别

- 当前消息或最近确认的 Agent 文案；本地 TXT / MD；用户明确选中的脚本片段。
- 可包含 Markdown 标题、代码块、列表、表格、操作说明、分镜备注、镜头切换、停顿标记及正文。
- V1 不强制支持从扫描 PDF、图像、视频中抽取文字。

### 5.2 文本处理模式

| 模式 | 行为 | 默认 |
|---|---|---|
| `narration_only` | 去掉**明确非口播**信息，保留原意、措辞、术语；可修正换行分段 | **是** |
| `verbatim` | 保留原文，不删除，只做安全的段落/句子划分 | 否 |
| `rewrite` | 允许改写口语表达；须获得用户明确授权 | 否 |

**删除候选**：如 `[镜头：切到 Maya]`、执行日志、代码示例（在非代码朗读任务中）、内部注释、纯装饰分隔符。**不能机械删除**：数字、版本号、英文术语、重要标题、必要步骤、发音标记或用户指示朗读的内容。复杂内容的不确定删除项进入 `needs_review`。

### 5.3 结构化规则

- 永久保留 `Document → Paragraph → Sentence` 层级；段落按语义与剪辑逻辑划分，不仅按空行。
- 句子按自然语义与语法拆分，不能在 `v1.2`、`3.14`、文件名、URL、缩写中错误分句。
- 停顿表示为数据字段，不把 `<#0.8#>` 当作口播文字；保留原有合法停顿并优先于自动策略。
- 推荐策略（可在默认设置中调整）：普通句末 300ms、段末 800ms；逗号内部主要由 TTS 韵律处理。数值为产品预设，不代表 API 强制值。
- 对连续停顿标记、首尾无朗读文字的停顿标记做归一化，避免违反 MiniMax 标记规则。
- 生成 `removed_items[]` 审计记录及来源片段定位。原文与整理稿均保存，支持差异对照。
- 若源脚本已经有 `<#x#>`（秒）标记，Parser 需识别并记录成毫秒，出站时再转换为 API 可用表示或在拼接时实施。
- **默认禁止**偷偷修正事实、删减技术步骤、替换术语拼写。

### 5.4 Agent 与代码边界

Agent 在当前 Harness 中执行语义理解，按照 `prompts/extract_narration.md` 输出 JSON。Python 必须完成：JSON Schema 校验、源内容覆盖率检查、模型兼容性校验、API 请求、音频后处理、字幕时间处理与缓存。Python 不再额外调用 LLM；语义不确定交回 Harness 判断。

## 6. 输出模式、剪辑和停顿

### 6.1 三种最终导出模式

| `export_mode` | 文件 | 适用场景 | 默认 |
|---|---|---|---|
| `whole` | `full.mp3` + `full.srt` | 交付完整旁白 | 否 |
| `paragraph` | 每段 `p001.mp3` + `p001.srt` | 视频分段剪辑 | **是** |
| `sentence` | 每句 `p001_s001.mp3` + `p001_s001.srt` | 精细剪辑、替换单句 | 否 |

所有模式均保存 `script.json` 和 `manifest.json`。**逻辑句子编号保持一致**，不能因切换导出模式而变化。音频文件必须是本地实际文件；不可仅返回短期有效的服务端 URL。

### 6.2 分层生成策略

- Script Segment = 用于编辑、标注、缓存索引的逻辑单位。
- Synthesis Chunk = 实际提交给 MiniMax 的文本单元，受 API 文本长度限制以及韵律连续性约束。
- Export Artifact = 用户最终获取的整篇/段落/逐句音频。
- `whole`：优先按自然段或合理长度合成，再按顺序合并。
- `paragraph`：优先一个自然段一个合成请求，超长段落由 Chunk Planner 切分后合并。
- `sentence`：每句单独合成；V1 不承诺与段落合成方式的声学表现完全一致。
- **局部重生成的精确定义**：逐句合成时可只重生成某一句；按段落合成时，重建完整段落需重新合成该段落。若用户只需要拿到一句替换音频，可单独合成该句作为剪辑素材，但不得不经音频对齐便自动覆盖原段落内部的一部分。整篇输出同理只重建受影响的底层 Chunk 与最终合并产物。
- 目标 Chunk 长度由配置决定，应留足 API 上限余量；MiniMax 同步 API 要求文本少于 10,000 字符，超过 3,000 字符建议采用流式，因此 V1 优先切成较短的非流式请求。
- 对多次合成的接缝，在后处理阶段插入停顿或进行安全修边；**不得重复计算** TTS 已含的停顿，且不得直接把语音裁断。

### 6.3 精确时间基准

- 所有内部时长以毫秒或采样点存储，避免浮点秒误差；使用 FFprobe/音频解码实测，而不是仅依赖估算。
- 每个音频文件的字幕时间基准从 `00:00:00,000` 开始。
- 整篇合并时依实际插入的静音样本长度累加字幕时间偏移；无效、越界、倒序字幕视为生成失败，不可静默交付。
- 单句文件默认不强加多余尾部静音，以方便剪辑；需要拼成段落/整篇时才按策略插入间隔。

## 7. 字幕（V1 必须、默认勾选）

- Studio 有 `生成字幕` 复选框，首次安装及新建默认预设均为 **true**。
- 默认 `subtitle_type: sentence`，输出标准 UTF-8 `.srt`，换行规范与时间戳兼容常见 NLE。
- `word` 为可选高级模式，仍应保留原始 JSON 时间戳，以备后续其它字幕格式转换。
- MiniMax 的 `subtitle_enable` 默认值是 false，Adapter 在开启字幕时必须显式传 `true`。
- 非流式 TTS 字幕以 `subtitle_file` 信息返回；本地应下载、解析、校验、转换，**不应将临时 URL 当作永久结果**。
- 字幕文本使用可读的口播原文，不展示 `<#0.8#>` 或发音控制 token。
- 生成任务默认对音频和字幕整体进行验收。若音频已生成但字幕失败，标记 `subtitle_failed`，支持重试；**未经用户明确选择，不将“无字幕音频”伪装成成功任务**。
- 音频合成和字幕粒度由 Provider 实际返回能力决定，需检验 `sentence` 模式对较短脚本及特定停顿的返回表现。

## 8. Voice Studio 信息架构

### 8.1 页面结构（仅三个一级页面）

1. **Voices（音色库）**：搜索/分类、试听、已缓存提示、选择音色；子区分「官方音色」「我的音色」（克隆和文生音色）。可从此创建克隆音色。
2. **Settings（配音设置）**：模型、音色、情绪、语速、音量、音调、LaTeX 朗读、文本规范化、术语发音、停顿参数、导出模式、字幕；底部是本次/默认的两个独立动作。
3. **Outputs（生成结果）**：任务进度、每段/每句音频播放、路径、字幕、失败项、局部重生成、定位文件夹。

不要复制 MiniMax 左侧完整控制台。UI 使用克制的工具型布局，适配窄窗口，设置区可滚动。

### 8.2 Voice Preset

常用字段：模型、音色 ID、情绪、语速、音量、音调、文本处理模式、导出模式、字幕开关与粒度、音频格式、发音词典、停顿策略。`auto` 情绪在内部作为特殊值处理，映射为省略 API `emotion` 字段，而非发送未证实支持的字符串。

初始**建议**预设：

| 项 | 首次建议默认 |
|---|---|
| Model | `speech-2.8-hd` |
| Voice ID | `male-qn-qingse`（仅示例预设，可改） |
| Emotion | `auto` |
| Speed / Volume / Pitch | `1.0 / 1.0 / 0` |
| Export | `paragraph` |
| Subtitle | `true` / `sentence` |
| Audio | MP3 / 32kHz / 128 kbps / 单声道 |
| Script Processing | `narration_only` |
| Pause | 句末 300ms；段末 800ms（推荐值） |
| LaTeX / Text Normalization | 关闭 |

首次发现用户已有预设时绝不覆盖。UI 中参数范围按照**当前模型的有效 API 限制**校验。

### 8.3 兼容性展示

情绪选项在 UI 中**全部展示**，但对当前模型不支持的选项置灰并提供解释；不能传参后静默忽略。例如 MiniMax 调试台目前注明 `whisper` 只适用于 Speech 2.6、`fluent` 适用于 Speech 2.6/2.8。模型变更时需实时重新校验选项；若现有默认预设与目标模型冲突，则阻止保存或要求用户修改，不静默替换。

### 8.4 设置页面：项目默认与本次应用必须分开

**状态提示**：页面顶部展示“配置来源：本会话 / 当前项目 / 全局 / 尚未配置”，并在可以识别项目时展示项目名称及（允许打开详情时）根目录。未加载成功的项目预设需要明显错误提示；不能把内置初始值标为“已保存默认”。

**按钮 A：「应用于本次生成」**：验证设置并提交 Session Snapshot，允许 Harness 继续当前任务；默认不覆盖持久预设。**例外仅限首次项目设置且明确勾选“同时保存为当前项目默认”时**，此次操作会原子保存项目默认，再应用本次。这个复选框初次配置默认勾选、可取消；在已有默认的“调整设置”情境下默认不勾选，避免不小心永久改动。

**按钮 B：「将当前设置保存为默认」**：用户选择保存范围（`当前项目` 或 `全局`，能检测有效项目时默认当前项目），验证后持久化对应预设；不自动生成音频、不自动结束页面、不静默更改其他范围。已启动任务继续使用原 Job Snapshot；需要应用到当前任务可以再点按钮 A。

**「恢复默认」**：重置表单到当前生效的已保存配置，不直接写磁盘，不更改进行中的任务。

**无 Project Root**：隐藏/禁用“保存当前项目默认”并解释原因，允许选择“仅本次应用”或“保存为全局默认”。

**可选 Session Preference**：通过显式“本会话后续沿用”开关保存到当前 Harness 会话的偏好存储，不与“仅本次”混同；关闭会话后应清除或过期。

**保存行为**：成功/失败反馈必须清楚；失败时保留表单。保存默认不会自动消耗 TTS 额度，试听按钮属于另一项明确的付费可能动作。

### 8.5 音色试听缓存

- 试听使用固定、可配置文案。相同 `voice_id + model + text + speed + vol + pitch + emotion + pronunciation + normalization + audio_format` 的组合必须复用缓存。
- 命中缓存 → 直接本地播放；未命中 → 按钮显示「生成试听」，请求 MiniMax，保存并播放。
- 正在生成时禁用重复触发，失败可重试且显示可理解的错误信息。
- 同一 Voice ID 远端失效时展示为不可用，不删除历史试听音频和已生成任务记录。

## 9. 音色管理与复刻

### 9.1 音色列表

通过 `POST /v1/get_voice` 获取系统、克隆、文生音色；API `voice_type` 类型包括 `all`、`system`、`voice_cloning`、`voice_generation`。支持搜索 ID/名称/描述、手动刷新及本地缓存目录。对于新克隆/文生音色，官方列表可能在首次正式合成后才可查询；本地可在创建成功后立即保存 Voice ID，并展示“等待同步”。

### 9.2 复刻操作

1. 用户在 Voices → 我的音色 →「创建音色」。
2. 显示授权确认：仅允许复刻本人声音或有合法使用授权的录音；提示样本会上传至 MiniMax、可能收费。
3. 校验样本文件：MP3/M4A/WAV，时长 10 秒至 5 分钟、≤20MB；读取时长/格式并校验。
4. 通过 MiniMax 上传接口取得 `file_id`，随后 `POST /v1/voice_clone` 创建自定义 `voice_id`。
5. 记录 `voice_id`、别名、创建时间、来源、试听状态、可用性、授权确认记录（不保存额外敏感录音内容到日志）。
6. 后续 `t2a_v2` 仅提交 `voice_id` 和文字，不再上传原始样本。
7. 官方说明：新复刻音色若 7 天内未正式调用可能被删除；成功创建后提供显式的首次正式合成提醒。失效时提示重新创建，不自动复刻。

V1 不支持删除远端克隆音色、不支持自动上传新的音色数据、不支持模拟未授权第三方声音。

## 10. MiniMax Provider 规范

### 10.1 接口映射

| 能力 | MiniMax API | 备注 |
|---|---|---|
| 语音合成 | `POST /v1/t2a_v2` | V1 主要采用非流式 |
| 列出音色 | `POST /v1/get_voice` | `voice_type` |
| 上传复刻音频 | `POST /v1/files/upload` | 具体字段按官方文档封装 |
| 创建克隆音色 | `POST /v1/voice_clone` | 复用 Voice ID |

音频 API 主要使用 `model`、`text`、`voice_setting`、`audio_setting`、`pronunciation_dict`、`subtitle_enable`、`subtitle_type`。内部 `auto`、`pause_after_ms`、`export_mode` 等**属于 MakeSoundSkill 协议**，不能不经转换直接发给 API。可配置 API 地区/Base URL（国内部署需按用户的密钥所属区域设置），不要混合域名或假定所有 Key 通用。

### 10.2 能力兼容矩阵

Provider Adapter 维护经测试确认的 Model Capability Table：模型 ID、情绪支持、字幕支持、文本规范化支持、发音标记支持、格式/采样率、请求长度等；网页和 CLI 复用同一份能力表，阻止无效请求。MiniMax 近期更新可能变化，表可版本化升级。

### 10.3 网络错误和计费保护

- 对网络断开、超时、429、服务端故障采用限制次数的指数退避，遵循服务端重试建议。
- 对鉴权失败、余额不足、参数无效不自动重试。
- 提供每任务调用数、成功数、缓存命中数、字符使用量及可获得时的费用估算；不要捏造精确收费数值。
- 未收到确定的结果时，识别是否可能产生重复计费，避免无限盲目重发。
- 非流式返回的临时下载地址必须立刻存到本地，并对二进制格式、文件完整性进行验证。

## 11. 本地 Config、Preset、作用域与持久化

### 11.1 MiniMax API Config（凭据文件，只读）

用户指定：

```text
C:\Users\luoxufeng\.config\minimax\config.json
```

跨机器实现为 `Path.home() / ".config" / "minimax" / "config.json"`，**不要写死用户名**。开发时必须确认现有文件真实字段结构并脱敏记录兼容规则；若结构不支持，`doctor` 报错但不覆盖文件。允许显式环境变量优先（只在本地 Provider 进程读取），不得在 stdout、请求预览、日志、脚本 JSON、URL 查询字符串中打印 API Key。API Key 一律不写入项目设置。

### 11.2 配置的物理位置（强约束）

```text
<project_root>/
└─ .makesound/
   └─ preset.json                  # 当前项目默认；不含密钥、音频原文

~/.config/minimax/config.json       # MiniMax 原有凭据；只读
~/.config/makesound/presets.json    # 全局默认与用户命名预设
<user_data>/makesound/sessions/     # 当前会话、网页授权信息（不放进项目）
<user_data>/makesound/cache/        # 试听、合成 Chunk 与字幕缓存
<user_data>/makesound/jobs/         # 任务状态与内部 Manifest
<project_output_or_user_data>/      # 音频、字幕与非敏感导出 Manifest
```

`<user_data>` 用系统标准用户应用数据位置（Windows 可选择 LOCALAPPDATA），不强制使用 Unix `~/.local/share`。项目 Preset 可提交版本控制以共享一致的音色参数（由项目策略决定），但**不能包含 API Key、原始声纹、待朗读的私密文本或本地临时访问令牌**；不自动更改 `.gitignore`，建议将任务结果/Session 目录默认置于项目之外或提供 `.gitignore` 建议。

### 11.3 项目 Preset 结构示例

```json
{
  "schema_version": "1.1",
  "preset_name": "Project Narration",
  "provider": "minimax",
  "model": "speech-2.8-hd",
  "voice_id": "male-qn-qingse",
  "voice": {
    "emotion": "auto",
    "speed": 1.3,
    "volume": 1.5,
    "pitch": 0
  },
  "export": {
    "mode": "paragraph",
    "format": "mp3",
    "subtitle_enabled": true,
    "subtitle_type": "sentence"
  },
  "script_processing": "narration_only",
  "pause": {
    "sentence_ms": 300,
    "paragraph_ms": 800
  }
}
```

此 JSON 为产品内部配置，**不是 MiniMax 原始请求体**。以上音色 ID 与参数仅用于结构示例，实际新用户仍须选定并确认音色，不以示例占位值冒充用户已配置。

### 11.4 配置解析规范

- 全局不存在 + 项目不存在 + 会话不存在 → `needs_setup`，启动 Studio；**不要直接靠内置默认值收费生成**。
- 全局存在 + 项目不存在 → `ready(global)`，静默继承；只有用户点保存/明确要求时才写项目文件。
- 项目存在 → `ready(project)`，可按字段继承全局设置，项目覆盖优先；不能把部分配置的未知字段当作合法 MiniMax 参数透传。
- 当前会话仅在 Harness 提供可信 Session ID 时应用；任务一次性 Override 不持久化。
- 当用户保存为项目默认时，原子写入 `.makesound/preset.json`，不得修改全局；保存全局同理不得回写项目。
- 改变默认只影响之后创建的任务。已有任务使用冻结的 Job Snapshot；`resume` 优先该快照。
- 自定义模型/Voice ID 必须做可用性检查（能离线做的本地验证先做，必要时在线查询），禁止自动回退到其他音色或关闭字幕。

### 11.5 原子写、并发和生命周期

- 对 `preset.json`、全局 `presets.json` 使用版本字段、临时文件 + 原子替换、必要的文件锁或冲突检测；写失败不破坏已有配置。
- 项目路径 canonicalize，隔离不同项目，禁止路径穿越。遇到只读项目时提示并提供本次/全局选项，不擅自落到其他路径。
- 会话内唯一 Session ID；用于 Studio 的一次性授权 token 不得写入项目或业务日志，必须有 TTL。浏览器关闭、取消、超时等状态分别记录。
- 多任务输出使用 job-id 独立目录与安全命名，避免彼此覆盖。任务快照和试听缓存可以清理，但项目默认不能被缓存清理误删。

## 12. 数据协议（示例为 MakeSoundSkill 自有结构）

### 12.1 Script Manifest（由 Harness Agent 输出）

```json
{
  "schema_version": "1.1",
  "document_id": "tutorial_mod_srf_001",
  "source": {
    "kind": "harness_confirmed_text",
    "sha256": "<source-text-hash>"
  },
  "processing_mode": "narration_only",
  "paragraphs": [
    {
      "id": "p001",
      "sentences": [
        {
          "id": "p001_s001",
          "text": "Mod 负责模型制作，为资产提供形体和结构。",
          "source_range": null,
          "pause_after_ms": 300
        },
        {
          "id": "p001_s002",
          "text": "Srf 负责材质和 Look。",
          "source_range": null,
          "pause_after_ms": 800
        }
      ]
    }
  ],
  "removed_items": [
    {
      "source_range": null,
      "text": "[画面：切换 Maya 界面]",
      "reason": "visual_direction",
      "needs_review": false
    }
  ]
}
```

`source_range` 为 Unicode 字符的 `[start,end)`；若无法可靠定位则存 `null` 并记录哈希，不得伪造偏移。`paragraphs`、句子 ID、停顿范围、被排除项及原文覆盖率均须严格校验。脚本包含 `<#0.8#>` 等标记时，内部转换为停顿字段，输出字幕不显示控制符。

### 12.2 Config Resolution 响应

```json
{
  "schema_version": "1.1",
  "status": "ready",
  "project_root": "D:/ExampleProject",
  "source_layers": ["global", "project"],
  "effective_summary": {
    "model": "speech-2.8-hd",
    "voice_id": "male-qn-qingse",
    "export_mode": "paragraph",
    "subtitle_enabled": true
  },
  "missing_fields": [],
  "warnings": []
}
```

`status` 固定枚举 `ready | needs_setup | invalid`。此输出只包含非敏感摘要，**不含 API Key 和临时网页 token**。`source_layers` 说明真实采用了哪几层，而不是永远固定的四层。

### 12.3 Studio Session & Job Snapshot

```json
{
  "session_id": "opaque-session-id",
  "status": "applied",
  "intent": "generate",
  "project_root": "D:/ExampleProject",
  "save_scope": "project",
  "saved_as_default": true,
  "applied_config_id": "sha256-of-effective-nonsecret-config",
  "job_id": "job_20261014_001"
}
```

UI 会话状态允许 `pending | applied | cancelled | expired | failed`。Job Snapshot 至少包含 `job_id`、`source_text_hash`、`script_hash`、`preset_snapshot`、`resolved_from`、`task_overrides`、`export_mode`、`subtitle`、`status`、`chunks[]`、`artifacts[]`、`errors[]`；运行中必须使用该快照。

缓存键采用规范化朗读文本 + Provider + Model + Voice ID + 情绪 + 语速/音量/音调 + 词典 + 文本规范化 + 音频参数 + 所需字幕参数的稳定哈希。外层整篇/分段导出需独立记录拼接策略、音频时长与字幕偏移；不得把不同合成粒度混作同一份缓存。

## 13. CLI、Studio 自动启动与 Harness 适配

### 13.1 CLI 最小可用接口（建议稳定下来）

```powershell
python -m makesound doctor --json
python -m makesound config resolve --project "D:\ExampleProject" --json
python -m makesound studio start --project "D:\ExampleProject" --purpose setup --json
python -m makesound studio wait --studio-session "<id>" --timeout 600 --json
python -m makesound voices list --json
python -m makesound generate --script "D:\scripts\narration.json" --project "D:\ExampleProject" --json
python -m makesound generate --script "D:\scripts\narration.json" --session-config "<applied-session-id>" --json
python -m makesound jobs status "<job-id>" --json
python -m makesound jobs resume "<job-id>" --json
python -m makesound jobs regenerate "<job-id>" --segment "p003_s002" --json
python -m makesound clone --file "D:\voice.wav" --voice-id "MyVoice001" --json
```

这些是面向开发的目标 CLI 契约，可调整实现细节，但语义必须保持一致。`generate` 必须接受最终合并的配置快照；对缺少关键设置的调用返回明确状态，不能临时选择随机声音。

### 13.2 Studio 自动启动协议

1. `config resolve` 返回 `needs_setup`，且 Harness 拥有本机执行权限时，运行 `studio start`。
2. CLI 优先**复用已有健康的本地 Studio 服务**，否则启动服务；监听 `127.0.0.1`，端口由 OS 分配，避免固定端口冲突。`start` 应尽快退出并返回 Session 信息，服务要在 CLI 进程结束后保持存活。
3. `start --json` 在 stdout 返回 `{ "status":"running", "url":"http://127.0.0.1:<actual_port>/...", "studio_session_id":"..." }`（只是契约示意，**不能把示例端口冒充实际运行 URL**）。
4. Harness 向用户展示返回的真实链接；只在必要时自动打开本机浏览器（优先尊重 Harness 环境与用户意图）。
5. 用户在网页选择后“应用于本次生成” → 按保存范围选择性写入项目/全局预设 → 将 Studio Session 标记 `applied`。
6. Harness 调用 `studio wait`、查询状态或读入受控的本地会话状态后继续；取消、过期、服务退出和关闭窗口均有明确结果，不得自动合成。
7. `studio start` 不得启动第二个抢占的窗口，且不同项目/不同任务的配置和授权会话必须隔离。
8. 远程 Harness/容器无法直接让用户访问其回环地址时，不得展示不可达的 `127.0.0.1` 冒充已就绪；改为提供可用端口转发或受支持的远程访问说明。V1 **不实现公网暴露**。

**重要**：`SKILL.md` 不会自己打开浏览器或启动服务，只有 Harness 实际调用了 CLI，且命令成功、返回有效监听地址，才可声称“已启动 Voice Studio”。

### 13.3 CLI 输出与错误码

- `--json` 的 stdout 严格机器可读；日志、进度、非敏感诊断写 stderr；异常返回非零退出码。
- 输出 `status`、`file_paths`、`subtitle_paths`、`job_id`、`count`、`failed_segments` 等，不输出 API Key、完整授权 URL 到公开日志。
- `studio wait` 等待不应无限阻塞；支持取消、超时及再次打开同一未过期 Session。
- 所有实际文件路径为绝对路径，且文件存在后才列为 `completed`。

### 13.4 Skill 指令的最小规定

`SKILL.md` 至少包括：触发语义、确定已确认文稿的规则、配置解析优先级、无需反复问默认、何时自动启动 Studio、读取其**真实 URL**、如何等待用户操作、脚本格式化 prompt、禁止擅自改写、CLI 调用和续跑、异常时的用户反馈以及结果路径。核心 Python 实现不依赖任意专有 Harness SDK；各 Harness Adapter 负责上下文注入和指令安装。

## 14. 本地网页服务与安全要求

- 服务默认仅监听 `127.0.0.1`，OS 随机可用端口；使用随机且有限有效期的会话令牌，绑定任务/项目，验证 Origin、CSRF；对保存默认、生成试听、复刻上传、启动合成等修改请求要求授权。不能假定回环网络天然安全。
- Studio Session ID 不作为 URL 中唯一鉴权因子；授权 token 不记录在业务日志、历史文件或项目 JSON。URL 传递方案需避免 Referer 外泄、浏览器历史意外长期保留，服务提供可靠失效与退出机制。
- 文件路径必须归一化和受限；禁止通过项目参数或网页请求读取任意本地文件/遍历目录。上传音色文件必须校验类型、时长、大小与授权确认。
- 语音复刻明确告知音频样本上传 MiniMax；生成中的脚本也会发送到 MiniMax，属于第三方处理；不能承诺完全本地生成。
- 凭据只读，绝不复制到项目配置；不向 Harness LLM 主动提供实际 Key 内容。MiniMax API 的响应、调试命令、错误日志需要脱敏。
- 项目预设只允许非敏感参数，Session/任务原文默认存用户数据目录，输出目录可配置；不得把声音录音、原文、密钥或音频文件直接提交仓库。
- 远端不可达时提示本地部署/端口转发条件，不自动绑定 `0.0.0.0` 或公开端口。
- 针对付费 API：无有效设置 / 未应用本次配置 / 明确取消时**不发送收费 TTS 请求**；已经有有效项目默认且用户发出生成指令则可直接执行，无需额外询问。
- 遵守 MiniMax 最新使用规则；服务端无效音色、模型不兼容、字幕缺失均不得静默换声、改模型或关字幕。

## 15. 状态机、异常与恢复

### 15.1 新任务状态

```text
created
  ├─ resolve_ready ────────────> preparing_script
  ├─ needs_setup ──────────────> awaiting_studio_setup
  │                                ├─ applied ──> preparing_script
  │                                ├─ cancelled ─> cancelled
  │                                └─ timeout ───> expired
  └─ invalid ─────────────────> configuration_error

preparing_script ──> needs_review / ready
ready ──> generating ──> postprocessing ──> completed
                          └─ partial_failed / failed / cancelled
```

`awaiting_studio_setup`、`needs_review`、`configuration_error` 均不可发送 TTS 请求。只有用户确定了文本、拥有有效设置且任务处于 `ready` 时才开始收费生成。正在进行的任务拥有独立 Job Snapshot。

### 15.2 错误处理矩阵

| 问题 | 期望反馈 | 程序动作 |
|---|---|---|
| 项目/全局/会话全部无有效配置 | “需要首次选择声音” + 实际 Studio URL | 启动本地服务并等待，不能造 URL |
| 有配置但相互冲突 / 音色失效 | 明确指出需要修复的字段 | 不静默回退；引导 Studio |
| 当前工作目录无法可靠识别项目 | “未找到项目根目录” | 本次/全局可用，不写随机目录 |
| 项目 Preset 只读/写入失败 | 提示未保存及恢复措施 | 保持原数据，按用户选择仅本次继续 |
| Studio 启动失败/端口被占用 | 告知服务启动失败 | 不假称“请点此链接” |
| 网页关闭/Session 取消或超时 | 任务仍待配置或已取消 | 不使用表单中未提交的设置 |
| MiniMax config 缺失/字段未知 | 给出具体路径和诊断 | 不覆盖原有文件 |
| API Key 无效、余额不足 | 清晰错误 | 停止无限重试 |
| 音色 ID 不存在 | 提醒重新选音色 | 不能自动使用其他音色 |
| 情绪和模型不兼容 | 可见禁用原因 | CLI 校验阻止请求 |
| 429/网络断开/超时 | 显示重试/续跑状态 | 有限指数退避、保留缓存 |
| 字幕缺失/越界 | 字幕失败 | 不能误标全部完成 |
| FFmpeg 不可用 | 告知安装依赖 | 保留已完成中间音频 |
| 口播文本有歧义 | 列出需确认的内容 | 暂停歧义段落，不能猜测 |

### 15.3 续跑语义

`resume <job_id>` 使用 Job Snapshot、Script Manifest 与已成功的缓存工件；默认不再次解析用户新改的项目/全局设置。用户明确“用新默认重跑”应创建新任务/配置版本，不得在旧任务上悄悄变更合成参数。

## 16. 推荐项目架构与目录

```text
MakeSoundSkill/
├─ SKILL.md
├─ README.md
├─ pyproject.toml
├─ prompts/
│  └─ extract_narration.md
├─ schemas/
│  ├─ narration.schema.json
│  ├─ preset.schema.json
│  ├─ config_resolve.schema.json
│  ├─ studio_session.schema.json
│  └─ job.schema.json
├─ makesound/
│  ├─ cli.py
│  ├─ config_loader.py           # 只读 MiniMax 凭据
│  ├─ project_context.py        # Project Root 解析
│  ├─ preset_store.py           # Project / Global 原子保存
│  ├─ config_resolver.py        # 覆盖与校验
│  ├─ session_store.py          # Session Preference / Task Config
│  ├─ script_validator.py
│  ├─ chunk_planner.py
│  ├─ provider/
│  │  ├─ base.py
│  │  └─ minimax.py
│  ├─ voice_library.py
│  ├─ preview_cache.py
│  ├─ jobs.py
│  ├─ audio_exporter.py
│  ├─ subtitle.py
│  └─ studio_server.py          # 启动/复用/等待/停止
├─ web/
│  └─ ...                       # Voices / Settings / Outputs
├─ adapters/
│  ├─ codex/
│  └─ claude_code/
└─ tests/
   ├─ fixtures/
   ├─ unit/
   └─ integration/
```

建议 Python 3.11+、`httpx`、Pydantic/JSON Schema、FastAPI（本地服务）和 FFmpeg/FFprobe；可用等效实现替换，但对外 CLI/JSON 协议与验收语义必须不变。Windows 本机为第一优先测试环境，网络不可访问时仍应支持 Schema/配置/FFmpeg 的离线单元测试。

## 17. 开发分期与交付定义

### M1｜可用 CLI + MiniMax Provider + Config Resolver

`doctor`、只读 MiniMax Key、Project Root 判定、Global/Project Preset 读取、优先级继承、原子保存、MiniMax 非流式 TTS、音频文件下载/保存、JSON 退出码、最小单元测试。完成时可以在有持久预设的项目中“一句指令直接生成”。

### M2｜Script Processor + 剪辑音频 + 字幕

Agent Prompt、Script Manifest Schema、合理停顿、三种输出、字幕（默认开启）、时间基准处理、缓存、断点续跑、局部重新生成。至少覆盖一份包含 Maya/Houdini/Markdown/镜头备注/停顿标记的教学文案。

### M3｜自动启动 Voice Studio + 会话交互

Voices / Settings / Outputs；音色搜索/试听缓存；配置来源提示；首次默认勾选“同时保存为项目默认”；“应用于本次”与“保存为默认”分离；启动/复用本地 Web 服务、回传真实 URL、取消/超时/恢复和项目隔离；一套跨进程集成测试。

### M4｜声音复刻 + 跨 Harness 集成验收

克隆音色、Voice ID 复用、失效检测；Codex 与第二个 Harness 的完整流程；跨会话/重启/切换项目、冲突配置与安全测试；README、部署脚本、示例 JSON 和稳定的开发接口说明。

**分期约束**：M1 可通过手动建项目 Preset 验收，M3 必须打通“完全无预设 → 自动 Studio → 勾选保存项目默认 → 首次生成 → 第二次免设置”的真正产品闭环；任何阶段不可只交付静态 UI。

## 18. 验收清单（Definition of Done）

**配置与首次使用**

- **AT-01**：项目 A + 无全局/项目/会话预设 + “生成音频” → `needs_setup`，自动启动 Studio，Harness 返回真实可访问 URL；尚无 MiniMax 合成请求。
- **AT-02**：首次打开 Studio 时“同时保存为当前项目默认”默认勾选；点击“应用于本次生成” → 创建 `.makesound/preset.json` + 本次快照，成功生成音频。
- **AT-03**：项目 A 同会话第二次请求无特殊设置 → 不问“是否默认”，不打开 Studio，直接生成。
- **AT-04**：退出/重启 Codex 后重新进入项目 A → 读取相同项目 Preset，直接生成。
- **AT-05**：项目 B 无 Project Preset，但有 Global Preset → 使用 Global，且不自动为 B 写项目副本。
- **AT-06**：项目 B 无项目和全局有效配置 → 启动 Studio；不得沿用 A 的 Project Preset。
- **AT-07**：首次取消“同时保存为当前项目默认” → 仅本次应用，项目目录无新 preset.json；下个新会话无默认则再次进入首次配置。
- **AT-08**：显式“本会话后面都使用女声” → 同会话后续覆盖项目音色；新会话恢复项目默认。
- **AT-09**：用户说“这次逐句、换语速” → 本次覆盖导出粒度和语速，其他配置继承，原项目/全局 JSON 不变。
- **AT-10**：点击“将当前设置保存为默认”，选择项目 → 只更新项目 Preset，不自动合成，也不修改 Global；选择全局则相反。
- **AT-11**：项目没有可信根目录 → UI 提示无项目，禁止随机写入；可选择本次或全局保存。
- **AT-12**：项目 Preset 部分字段缺失 → 能从有效全局正确合并；冲突/非法参数不得静默回退。
- **AT-13**：Studio 关闭/Session 超时/服务启动失败 → 明确取消或失败，不生成付费音频，不虚构 URL。
- **AT-14**：两个项目、两个 Studio Session 同时设置 → 不串配置、不串 token、不覆盖彼此默认。
- **AT-15**：已经开始生成的 Job，随后修改项目默认 → 当前 Job 使用原 Snapshot；重新启动新 Job 才使用新默认。

**文本、合成与字幕**

- **AT-16**：混合 Markdown、`[镜头]`、技术术语与 `<#0.8#>` → 保留朗读正文/术语，移除非口播，停顿结构化并保存审计记录。
- **AT-17**：不确定的删除/改写必须进入审核；默认不得擅自重写已确认的技术步骤。
- **AT-18**：同一 Script Manifest 在 whole / paragraph / sentence 下，导出数量、文件名、逻辑段句索引正确。
- **AT-19**：句级 SRT 默认为 true；MiniMax 请求明确启用字幕，并按最终音频时间校验 SRT。
- **AT-20**：合并时新增 800ms 间隔，合并字幕按实际样本长度平移且不越界。
- **AT-21**：逐句改 `p003_s002` 只重生成受影响句；段落整合时不声称无对齐即可无损修改内部一个句子。
- **AT-22**：试听同参数同文本两次，第二次命中本地缓存，不再发送新 TTS 调用。
- **AT-23**：429/断网后可重试/续跑，成功 Chunk 不重复收费合成；无法判断是否已计费时明确提示风险。
- **AT-24**：字幕缺失或越界时标记 `subtitle_failed`，不得在字幕开启的任务上输出 `completed`。

**Provider、复刻、跨 Harness、安全**

- **AT-25**：使用 `~/.config/minimax/config.json`，即使结构未知也不会覆盖原文件或输出密钥。
- **AT-26**：不兼容情绪在网页可见但禁用，CLI 禁止透传无效参数。
- **AT-27**：用户授权的声音复刻成功后保存 Voice ID；之后 TTS 只传 ID，不再次上传原始音频。
- **AT-28**：Codex 与第二个 Harness 对相同项目配置读取结果相同，均可运行核心 CLI。
- **AT-29**：Studio 监听与会话令牌符合安全要求；本地 HTTP 无法越权访问任意本地文件。
- **AT-30**：`--json` 命令 stdout 有稳定 Schema，真实文件存在后才能汇报成功，敏感日志脱敏。
- **AT-31**：FFmpeg 缺失/编码失败时清晰告知，并保留已生成的原始 Chunk。
- **AT-32**：内置建议音色/模型即使存在，第一次无用户确认配置时也不能冒充 Project/Global Preset。

**V1 限制**：句级与段落级合成的韵律可能不同；不支持自动音素对齐、完整 NLE 时间轴或多用户线上共享。所有限制需要在 README 中明确。

## 19. 实施前需核实的集成细节

1. `C:\Users\luoxufeng\.config\minimax\config.json` 的真实键结构、密钥地区与 base URL：只检查**脱敏字段结构**，不把密钥贴到对话、文档或日志。
2. MiniMax 目标模型的字幕返回格式、精度、最短句情况；需确认 `.srt` 转换和最终时长一致。
3. `get_voice` 的实际返回分类字段、新克隆音色可查询时机、voice_id 失效与授权要求。
4. `config resolve` 项目根推断在 Codex、Claude Code 的实际工作目录表现；不同 Harness 的会话 ID 是否持久可用。
5. Windows 本机 Service 生命周期：由 CLI 启动的 Web 服务如何常驻、退出、复用及恢复；随机端口能否可靠回传。
6. 无 Git 仓库但明确指定项目根的场景；只读项目、同步盘、Unicode 路径和多进程并发写入的原子性。
7. MiniMax 非流式调用的实际媒体编码、字幕文件传递形式及复刻服务支持地区；若官方字段变化，Provider Adapter 更新且能力表 versioned。

这些属于开发探测事项，不改变已经确定的产品体验规则。

## 20. 官方参考资料与最终基线

- MiniMax 同步语音合成：<https://platform.minimax.cn/docs/api-reference/speech-t2a-http>
- MiniMax 声音复刻：<https://platform.minimax.cn/docs/api-reference/voice-cloning-clone>
- MiniMax 上传声音样本：<https://platform.minimax.cn/docs/api-reference/voice-cloning-uploadcloneaudio>
- MiniMax 音色管理：<https://solutions.minimax.cn/voices>
- MiniMax 语音调试台：<https://solutions.minimax.cn/debug/speech>

> **MakeSoundSkill V1.1 最终产品基线**：Harness 定位已确认文案 → 解析本次 / 会话 / 项目 / 全局配置 → **有有效默认则直接继续，无默认则自动启动本地 Studio 并提供真实 URL** → 首次设置可默认勾选保存为项目预设 → Agent 提取口播、按语义分段和安排停顿 → Python 调用 MiniMax → 整篇/段落/逐句输出音频与默认开启的 SRT → 缓存、可续跑、可单段或单句重新生成。

