# MakeSoundSkill — 产品需求文档 PRD V1.2

> 版本：V1.2｜日期：2026-10-14｜状态：产品规则定稿；MiniMax API 与 Harness 集成待实测  
> 基线：`MakeSoundSkill_PRD_V1.1_2026-10-14.md`。本版修改或取代 V1.1 中冲突规则；未明确修改的安全、合成、字幕、校验、续跑规则继续有效。  
> 产品：Agent-Native Audio Generation Skill｜首个 Provider：MiniMax｜Windows 11 / Python 3.11+ / Codex、Claude Code 及兼容 Harness

## 0. 本版产品决策与术语

**已确认**：取消“声音配置按 Harness 会话继承”；提供全局创建音色资产库、项目命名音色库和独立默认声音；支持声音复刻与文字设计音色；复刻原始录音本地保留且可删除；项目别名重绑定需确认；用户明确的女声等描述用于预筛选；“帮我选择”表示授权 Agent 从符合条件的可用声音中选择并继续；未知别名引导 Voice Studio 补充，不静默替代；多音色按实际声音边界拆分合成；Studio 提交为本任务最终声音选择，优先于先前对话声音指定；可设置默认而不添加项目音色库。

**术语**：TTS = Text-to-Speech（文本转语音），UI 面向用户统一使用“配音/语音生成”。Voice Asset 为 MakeSoundSkill 管理的已创建音色；Voice ID 为 Provider 侧实际可用于合成的标识；Project Voice Alias 为项目可读名称到 Voice Reference 的映射；Project Default Voice 为未明确指定声音时的回退；Voice Studio Session 是网页提问—回答的临时交易标识，**不是**会话级声音偏好；Job Snapshot 是冻结的任务文本、声音绑定和全部运行参数。

**约束等级**：MUST 必须验收；SHOULD 优先；LATER 未来版本。绝不以系统初始建议值冒充用户建立的默认。不能假装 Studio 已启动或 Agent 已恢复。

## 1. 产品目标与适用场景

用户在 Harness 中确认文案，要求“生成音频”；Skill 借助 Harness 理解口播文本、声音描述、项目别名、段句归属；Python CLI 做确定性校验、资产解析、MiniMax 调用、字幕和合并。配置完整时直接生成；配置缺失时自动启动实际可访问的本地 Studio，通过结构化回答让 Agent 恢复。不要求每次重新配置。

### 1.1 典型命令

- “把刚才确认的稿子按段落生成音频。”→ 项目默认声音 + 句级 SRT。
- “用女声音1配这段，语速 1.2。”→ 项目别名定位 Voice ID；语速只覆盖本次。
- “第一段用女声音1，第二段用男声音1，剩下用默认音色。”→ 各段独立绑定和合成，按选定模式导出。
- “用温柔的女声，帮我选一个。”→ 搜索并约束候选，用户已授权可选中后生成；不能可靠匹配时返回选择界面。
- “用男声音1”；但项目不存在该别名 → Studio 预筛选男声并补充该别名，用户提交后继续；禁止静默找任意男声代替。
- “打开声音设置。”→ 仅打开 Studio，不自动开始新的收费任务。
- 用户第一次选声音，勾“设为当前项目默认声音”，**不勾**“添加到当前项目音色库” → 允许直接保存默认 Voice Reference，不强制命名。

## 2. V1.2 范围

### 2.1 MUST（P0）

| ID | 功能 | 验收要点 |
|---|---|---|
| P0-01 | SKILL.md + Python CLI，跨 Harness | 核心逻辑不依赖特定 Harness SDK |
| P0-02 | 分离全局音色资产、项目别名、项目默认、Job Snapshot | 存储、生命周期、删除含义不同 |
| P0-03 | 复刻声音 | 授权确认、原录音保留/可删、Voice ID 可复用 |
| P0-04 | 文本设计音色 | 正式 Provider Adapter 与资产登记；接口先探测，收费需授权 |
| P0-05 | 全局音色资产名称唯一 | 本地创建资产具有全局唯一稳定 Asset ID 与不冲突的名称 |
| P0-06 | 项目命名音色库 | 同项目别名唯一，不同项目可重复；允许重绑定，需确认 |
| P0-07 | 默认声音独立保存 | 可以不加入命名库而设默认，且不覆盖其他设置 |
| P0-08 | 配置解析和显式覆盖 | Studio 最终提交 > 明确项目别名 > 项目默认 > 全局默认（声音选择）；描述词约束不能被默认覆盖 |
| P0-09 | 关键词预筛选 + Agent 选择 | 女声等显式条件在网页生效，可关闭筛选；用户授权 Agent 选可直接继续 |
| P0-10 | 缺失别名修复 | 打开 Studio，提示待补全别名并候选筛选；不擅自映射 |
| P0-11 | Studio 提问/回答与恢复 | 真实本地 URL；一次性会话与回答；能等待则恢复，不能则持久待领取 |
| P0-12 | 多声音脚本与 Chunk Planner | 声音边界拆分，保留原始段句 ID；不能将不同声音放一个 TTS 请求 |
| P0-13 | 三种导出模式 | whole / paragraph / sentence；默认 paragraph |
| P0-14 | 默认字幕与严格校验 | sentence SRT 默认开启；最终文件真实时间轴，不能估算伪造 |
| P0-15 | 文本提取与源文审计 | 默认 narration_only，不擅自修改已确认文案 |
| P0-16 | 缓存、失败续跑、局部重生成 | 按精确声音/模型/文本/参数复用；快照冻结 |
| P0-17 | 安全与诊断 | MiniMax Key 只读脱敏；最小授权；仅回环监听，不假地址 |

### 2.2 SHOULD（P1）

可选词级字幕（以 API 实测为准）；术语发音词典；Voice Studio 本地试听与状态展示、产物播放和重生成；多音色使用情况可视化；自然语言声音属性推荐的解释；失败音频恢复引导。

### 2.3 LATER

其他 Provider、云端多用户协同、复杂 NLE 时间轴、多轨编辑器、音素级对齐、音乐生成、远程资产删除自动化及泛用 ASR。**音色设计已经进入 V1.2 MUST，不得保留为 LATER。**

## 3. 数据模型与作用域

### 3.1 Global Voice Asset Library（全局创建音色资产库）

全局库管理 MakeSoundSkill 经**录音/上传复刻**或**文本描述生成**的资产，非 MiniMax 官方系统声音列表。资产包含：稳定 `asset_id`、全局唯一的 `display_name`、`source_type: clone|design`、`provider`、`voice_id`、创建时间、可用性、区域、元数据、预览音频（若有）、克隆原始录音本地路径（若保留）、设计提示词/参数（若有）、可选授权证明状态。单个 Provider 的同名 Voice ID 和全局 Asset ID 不是同一概念。

- 用户创建的全局资产存储在**用户级数据目录**，不直接写入 Skill 源码包，以免升级覆盖。源码只存管理程序和内置只读元数据。
- 克隆成功后默认保留原始音频；用户可删除本地样本，需告知删除后可能无法以原样本重新复刻。删除本地样本**不**删除 Voice ID、资产条目、项目引用或历史 Job；不承诺远端删除。
- 首次复刻/设计时的收费 API 操作必须显式说明并取得授权；新 Voice ID 注册本地可先于官方音色列表同步。
- 对失效 Voice ID 显示修复需求，禁止静默换声、重新复刻或对外上传本地录音。
- MiniMax 官方声音由官方列表查询，可直接被项目引用；不必在全局资产库创建重复资产。

建议位置：`<user_data>/makesound/voices/assets.json` 和 `.../voices/samples/<asset_id>/`。这是逻辑路径约定，不要求项目持有全局样本副本。

### 3.2 Project Voice Library（项目音色库）

`<project_root>/.makesound/preset.json` 保存项目别名集合和项目默认设置。别名只在**当前项目内唯一**，不同项目允许同名。别名可引用全局 Asset ID，或直接引用 MiniMax 官方 `provider + region + voice_id`。项目中不复制原始声纹或凭据。项目 A 与 B 数据隔离。

编辑操作：添加、改名、重绑定、移除。重绑定 `女声音1: A → B` 前显式二次确认；历史快照仍用 A；删除别名不删除全局资产、官方远端声音或历史记录。若删除被默认引用的别名，必须同时修复默认引用或拒绝删除，不能留悬挂引用。

### 3.3 声音参数与项目参数分离

**Named Voice**：声音引用与声音表现参数（speed、volume、pitch、emotion 等支持字段），不拥有字幕、导出模式或项目级停顿策略。**Project Settings**：导出、字幕、文本清理、拼接停顿、音频格式等。**Project Default Voice**：保存一个可直接指向 Voice ID / Asset ID 的声音引用及其声音参数，**不要求存在命名别名**。

当保存“设置默认声音”而不勾“添加到当前项目音色库”，存直接默认引用；将来仍可主动加入音色库并命名。若同时勾两项，可选择引用刚创建的命名音色；必须防止半成功写入。

### 3.4 Global Default 与项目无效根目录

保留 V1.1 的 `~/.config/makesound/presets.json` 全局默认设置，但它不同于全局**音色资产库**。没有项目根时允许本次与全局默认，不得假装已保存项目别名。项目根来自明确用户输入、Harness workspace 或可信项目定位，禁止盲写 CWD/HOME/System32。

### 3.5 建议 Schema 示例（示意，非直接 MiniMax Request）

```json
{
  "schema_version": "1.2",
  "project_settings": {
    "export_mode": "paragraph",
    "subtitle_enabled": true,
    "subtitle_type": "sentence",
    "script_processing": "narration_only",
    "audio_format": "mp3",
    "pause": {"sentence_ms": 300, "paragraph_ms": 800}
  },
  "default_voice": {
    "ref": {"kind": "provider_voice", "provider": "minimax", "region": "configured", "voice_id": "EXAMPLE_ID"},
    "voice_settings": {"speed": 1.0, "volume": 1.0, "pitch": 0, "emotion": "auto"}
  },
  "named_voices": {
    "女声音1": {
      "ref": {"kind": "global_asset", "asset_id": "voice_asset_001"},
      "voice_settings": {"speed": 1.2}
    },
    "男声音1": {
      "ref": {"kind": "provider_voice", "provider": "minimax", "region": "configured", "voice_id": "EXAMPLE_MALE"},
      "voice_settings": {}
    }
  }
}
```

`EXAMPLE_ID` 与 `EXAMPLE_MALE` 为非真实占位符，不得作为默认可用音色。旧 V1.1 单 `voice_id` Preset 提供只读兼容解析与显式迁移命令；不得迁移时覆盖用户的原始文件，备份和报告差异。

## 4. 选择音色与参数优先级

**声音选择优先级（同一任务）**：
1. 本任务 Voice Studio **已提交**的具体声音选择（不可用未提交草稿覆盖）。
2. 用户明确点名的项目命名音色；若不存在，进入修复，不把文字“男声音1”当作泛用男声描述。
3. 项目默认声音。
4. 全局默认声音（存在且有效时）。
5. 首次设置：没有用户已确认的有效配置且仍缺必需字段 → Voice Studio。系统内置建议值仅作表单初始值。

**显式描述约束**（如女声、温柔、低沉）优先于默认候选的回退：如果当前默认与硬约束冲突，不能直接继承默认。出现明确别名与明确描述互相矛盾时，应询问或打开 Studio，不能任意选择其中之一。

**本次参数**：用户指明的语速、导出模式、字幕开关等独立覆盖相应字段；网页最终明确提交的本任务参数覆盖之前的同字段描述。合并时使用 Schema-aware 字段合并；数组替换规则在 Schema 明确；非法字段不透传 API。仅用户明确“更新默认/添加项目库/保存全局”才持久化相应范围。

**“帮我选择”**：只有用户明确授权该行为（例如点按钮、文字明确要求 Agent 选择）才自动选最适配音色并生成；查询可用音色及其可信元数据，对硬条件进行过滤、软条件排序；依据不足、匹配不唯一且没有合理可解释选项、或候选均不符合硬约束时，请用户在 Studio 选择，不编造声音特征。不把推荐/选择结果静默保存为默认或项目别名。

**没有会话级声音设置**：移除 V1.1 `Session Preference` 作为合并层。Studio Interaction Session 仅关联一次提问、授权和回答，不能被后续新任务当作默认。**Job Snapshot** 创建后冻结每个合成 Chunk 的实际 provider/region/voice_id/voice_settings，原始声音别名只作为审计信息。

## 5. Agent、Studio 提问—回答与恢复

### 5.1 状态机

`created → config_resolving → [ready | needs_studio | invalid] → script_preparing → [needs_review | ready_to_generate] → generating → postprocessing → [completed | partial_failed | failed]`。`needs_studio → pending_answer → applied/cancelled/expired`，只有 `applied` 才能继续。禁止 `pending_answer`、`needs_review` 状态调用收费 API。

### 5.2 提问协议

Agent/CLI 生成明确的 `question_id`、`job_id`（若已创建）、`project_root`、需补的配置项、用户描述关键词、候选过滤器以及用途 `setup|repair|select_voice|edit_default|register_alias`；调用 `studio start`。CLI 优先复用健康的本机服务器；监听 `127.0.0.1` 随机端口；返回**实际** URL 和一次性 Studio Session ID，不能臆造链接。

用户在网页中提交回答后，原子保存已明确勾选的项目/全局改动，记录 `answer_id`、`question_id`、脱敏 `applied_config_id` 和 `applied` 状态，保证幂等：刷新/重复提交不得使付费操作重复发生。

**恢复机制**：Harness 正在等待时通过 `studio wait --question <id> --timeout ...` 读取回答后恢复；Harness 无法保持等待时，安全持久化 `pending answer`，可通过 `studio answer get` 或 `jobs resume` 领取；不要声称任意网页能原生唤醒所有 Harness。浏览器关闭不能错误地覆盖已经提交的回答；取消或超时不得触发 TTS。

### 5.3 Voices / Settings / Outputs

**Voices**：官方声音、我的音色（复刻、文本设计）、项目命名音色分组；搜索、试听、缓存、音色可用性；展示适用的描述筛选（例如女声）且允许用户清除筛选。**Settings**：声音、模型、声音表现参数、文本处理、停顿、字幕及导出参数。**Outputs**：任务状态、音频与 SRT、错误、局部重生成及实际文件路径。

声音设置区有三个互相独立的意图：
- **应用于本次生成**：只提交当前回答，不隐式持久化（首次项目设置时 V1.1 默认勾选“同时保存项目默认”，用户可取消）。
- **添加到当前项目音色库**：复选框 + 必填别名输入，仅在项目根有效时可用；同项目重名需要求用户确认是重绑定而非静默覆盖。
- **设置为当前项目默认声音**：复选框，**不依赖加入项目音色库，不强制命名**。

主动点击“保存默认”属于持久化操作，不自动合成；用户明确修改后以网页最终提交为准。若保存动作失败，要保留表单和已提交意图，不谎称保存成功。首次项目配置的默认勾选延续 V1.1，主动编辑已有设置时不默认改写持久配置。

### 5.4 预筛选

Harness 从明确表述中传入结构化筛选条件（如 `gender=female`），网页只对候选**可见性**施加过滤；用户清除筛选后可选其他候选。最终提交音色优先级最高；界面要清楚告知用户改变了原要求，避免误操作。未知项目别名修复时预填该别名，用户可通过提交同时注册项目别名。

## 6. Script Processor 与多声音分配

### 6.1 文本处理

保留 V1.1 `narration_only`（默认）、`verbatim`、授权 `rewrite` 三模式。移除明确非口播的镜头注释和执行日志，保留事实、术语、数字、版本号；歧义项 `needs_review`。保留 `Document → Paragraph → Sentence` 与 `removed_items[]`、原文哈希/映射；解析 `<#0.8#>` 为控制字段，不让控制字符被读出。内部毫秒 / 采样点时间基准。

### 6.2 Voice Assignment

独立的 `voice_assignments[]` 把区间/段句映射到**可解析的项目别名或直接声音引用**。允许一个段落内换声（例如两角色对白），在不破坏原有段句索引前提下把合成单元切为多个不同声音 Chunk。未明确指定者继承默认；明确别名不存在进入 `needs_studio`，不能自动换声。跨声音的单个 TTS 请求严格禁止。

示例：

```json
{
  "schema_version": "1.2",
  "document_id": "tutorial_001",
  "paragraphs": [{"id":"p001","sentences":[
    {"id":"p001_s001","text":"欢迎来到课程。","pause_after_ms":300},
    {"id":"p001_s002","text":"现在开始操作。","pause_after_ms":800}
  ]}],
  "voice_assignments": [
    {"target":"p001_s001","voice_alias":"女声音1"},
    {"target":"p001_s002","voice_alias":"男声音1"}
  ],
  "removed_items": []
}
```

这里仅示意声音分配扩展；完整 Schema 仍需包含 V1.1 的 `source`、hash、source range 和校验要求。目标粒度或句内换声时增加稳定的 `span_id` / source span，不得伪造源位置。

### 6.3 合成与输出

- Script Segment：编辑/逻辑单位；Synthesis Chunk：同一实际声音、模型及请求兼容参数的合成单位；Export Artifact：whole / paragraph / sentence 最终交付单位。
- `whole` → `full.mp3`+`full.srt`；`paragraph`（默认）→ `p001.mp3`+`p001.srt`；`sentence` → `p001_s001.mp3`+`p001_s001.srt`。其他格式（例如 WAV）可配置且文件后缀相应变化。
- 若声音在句内转换，单句导出文件可由多个声音 Chunk 拼接；必须保持文字次序、可追踪来源及真实字幕时间轴。相同声音可依长度/韵律策略切块，不强制合并。
- TTS 自然停顿与显式 `<#x#>`、Chunk 拼接间隔分别处理；推荐句末 300ms、段末 800ms 为目标参数，不保证每句话直接追加该静音。不得重复叠加；逐句产物默认不强制多余尾静音。
- 可按句或段局部重生；整段请求合成时不得伪称能无损替换其中一句。重建受影响 Chunk 和最终合并产物。

## 7. 字幕与校验

- `subtitle_enabled: true` 初次默认勾选，`subtitle_type: sentence`；调用 MiniMax 必须显式启用字幕相关参数（以当前有效 API 实测为准）。
- 仅依据 Provider 真实句级时间信息或另行受验证的对齐结果生成 SRT；不得按字数均分时长或伪造精准时间戳。若所选生成方法无法提供可靠时间，则报告字幕失败/阻止任务成功，用户可以明确选择无字幕方案；不能静默关闭字幕。
- 下载临时字幕文件并持久化；音频拼接以实际解码时长/采样点计算 offsets；每个独立文件 SRT 从 00:00:00,000 开始，防越界/倒序/文本控制符泄露。
- 字幕失败标记 `subtitle_failed`，保留成功音频 Chunk 与重试信息，任务不能标为完全成功。

## 8. MiniMax Provider 与用户声音创建

### 8.1 保留已确认能力

TTS 同步合成、官方音色列表、音色试听、声音复刻、API 错误与限流、素材上传、Voice ID 可用性校验。Audio API 中 `auto` 情绪是**MakeSoundSkill 内部**的“省略 emotion”语义，不能盲发 `auto` 字符串。能力矩阵由实际 API/模型测试确认，UI 与 CLI 共用；不同地区 Key/URL 不混用。

### 8.2 新增 Voice Design（文字设计新音色）

用户输入想要的声音描述，经 Voice Studio 预览条件和创建确认，调用 MiniMax 官方**实际可用的声音设计接口**并保存所获得的 Voice ID/资产元数据，随后可加入项目库或设默认。创建之前告知任何可能产生的收费、额度和模型/地区限制。严格区分“生成候选预览”与“正式创建音色”的调用与成本；若 API 仅提供一次性生成或需要激活/后续使用，不得假设它与克隆有相同的激活规则。

**不可凭推测实现 endpoint 或 payload**：Codex 首先进行官方文档和只读 API 能力探测；将字段、方法、返回样例、地区、音色是否持久、激活有效期、试听计费条件写入集成报告，再实现 Adapter。官方站点/订阅页出现 Voice Design 功能不代表当前 Key 已开通该 API。

### 8.3 复刻声音

经用户授权的录音样本（V1.1 建议 MP3/M4A/WAV、10 秒–5 分钟、≤20MB，均以官方实际要求校验）上传一次；取得 Voice ID；后续 TTS 仅发 Voice ID。创建的原录音本地保留，用户可删除。原样本是否需要远端重复上传、音色是否 7 天失活等行为依 API 文档及实测，程序不能自动重复上传或复刻。

## 9. 文件位置、版本与并发

- 只读 MiniMax 凭据：`Path.home() / '.config/minimax/config.json'`；真实字段与 Base URL/区域需脱敏检查；环境变量可显式覆盖，不能向 Harness/LLM 输出 Key。
- 全局默认：`~/.config/makesound/presets.json`；全局创建音色资产：`<user_data>/makesound/voices/`；本地原录音：`.../voices/samples/`；任务、Studio 会话、缓存各在 `<user_data>/makesound/` 独立子目录。
- 项目：`<project_root>/.makesound/preset.json`；项目输出路径可配置；不自动提交隐私脚本、录音、临时 token 到 Git。
- 原子写、Schema 版本、跨进程文件锁或冲突检测；项目别名覆盖需确认和审计。一个项目同时两个 Studio 会话不允许静默最后写入覆盖另一人的修改。用户删除全局资产前应检测被引用情况，并提示；不自动删除 MiniMax 远端资源。
- 老版本兼容：保留 V1.1 只读加载与安全迁移策略，迁移需要备份，不要破坏原有效默认。

## 10. CLI 与接口契约

```powershell
python -m makesound doctor --json
python -m makesound config resolve --project "D:\ExampleProject" --json
python -m makesound voices list --source official --json
python -m makesound voices assets list --json
python -m makesound voices aliases list --project "D:\ExampleProject" --json
python -m makesound studio start --project "D:\ExampleProject" --purpose setup --json
python -m makesound studio wait --question "<question_id>" --timeout 600 --json
python -m makesound studio answer get --question "<question_id>" --json
python -m makesound generate --script "D:\scripts\narration.json" --project "D:\ExampleProject" --json
python -m makesound jobs status "<job_id>" --json
python -m makesound jobs resume "<job_id>" --json
python -m makesound jobs regenerate "<job_id>" --segment "p003_s002" --json
```

以上是**目标 CLI 契约，不是可直接运行的已实现命令**。开发后补充 `voices clone/design`、`voices aliases add/rebind/remove`、`voices assets sample-delete`、`config migrate` 等正式参数。任何可能扣费的创建、试听、语音合成命令必须有明确用户授权和可检查的计费预警；`doctor`、`resolve`、`schema validate` 默认只读无收费。

JSON stdout 严格可解析、无密钥；诊断在 stderr；非零错误码；真实文件存在后才返回 completed。Studio URL 仅来自运行时返回；一次性授权信息不得出现在公开日志。无需原生 Harness API 的 Python CLI 方案为首选。

## 11. 安全与隐私

- Voice Studio 绑定 `127.0.0.1`、随机端口，随机授权令牌、TTL、Origin/CSRF 防护、路径范围限制；不同项目和 Job 的问答不能串线，重复提交幂等。
- 本地录音保留须让用户能查看路径并主动删除；向 MiniMax 上传录音/声音描述/口播文本前，界面明确第三方处理与潜在成本；未经授权录音不得复刻。
- 读取配置必须脱敏；不输出 API Key、录音二进制、敏感文本或完整会话 token 到 Agent、终端日志、URL 查询参数、项目配置与 Git。
- 收费调用：首次无配置、网页未提交、音色别名缺失、需要用户复核脚本或存在冲突时一律不得直接调用；有效已保存设置且用户发出生成指令时可自动调用。
- 切换到 `0.0.0.0` 或公开网络必须禁止作为默认。容器/远程 Harness 的回环 URL 不可达时报告限制，不冒充已就绪。

## 12. 开发分期

| Milestone | 必交付 | 无收费先验验证 |
|---|---|---|
| M0 探测 | Python/FFmpeg、MiniMax Config 脱敏结构、官方 API 能力/Voice Design 文档、Harness 等待/恢复可行性报告 | 全程 dry-run/只读 |
| M1 核心数据 | 全局 Asset Registry、Project Alias、默认声音、配置解析、旧配置兼容、安全/锁/Schema/CLI | 单元测试 + 虚拟 Provider |
| M2 生成引擎 | Script Manifest、Voice Assignment、Chunk Planner、三种导出、SRT、缓存、Snapshot/Resume | Fake Provider / Fixture 音频 |
| M3 Studio | Voices / Settings / Outputs、问答/恢复、筛选、用户自主选择、保存默认/添加别名分离 | 本机模拟网页交互，无 MiniMax 合成 |
| M4 Provider | MiniMax 正式 TTS/克隆/Voice Design 接口；声音状态和地区；可用性、字幕、跨 Harness | 明确授权、受控低成本小样本 |

M0、M1、M2、M3 的模拟测试可独立于 MiniMax 费用完成。M4 真正收费测试必须由用户显式批准，测试运行结果写入报告。不得用静态网页代替端到端测试。

## 13. V1.2 Definition of Done

### 核心规则

- AT-01：无项目和全局默认 → Studio 返回真实可访问 URL；未提交不产生付费调用。
- AT-02：首次设置可直接设项目默认且**不添加项目命名音色**；新会话/重启后仍复用。
- AT-03：添加项目别名必须命名；A 项目和 B 项目可同名；同一项目重名触发显式重绑定确认。
- AT-04：全局创建资产具有稳定唯一 ID 和全局唯一显示名；不同项目可引用同一 Voice ID。
- AT-05：项目别名被重绑定后新任务用新 Voice ID；老 Job resume 用旧快照。
- AT-06：删除克隆原始录音不会删除 Voice ID / 资产 / 项目别名；删除资产需检测被引用。
- AT-07：创建克隆/文本设计音色都记录创建来源与 Voice ID；后续 TTS 不重新上传原录音。
- AT-08：缺失 `男声音1` 时 Studio 以男声筛选并可创建该别名，不能直接替换。
- AT-09：用户说女声但项目默认男声时，不得直接用男声；网页可取消筛选，用户明确提交选择优先。
- AT-10：用户点击“帮我选择” → 在可验证条件内 Agent 选择后直接生成；不符合硬约束时请求用户处理。
- AT-11：没有明确选择时使用项目默认 → 全局默认；内置建议不会绕过首次配置。
- AT-12：多声音在同一文稿不同段句按实际 Voice ID 分离 Chunk，保留段句 ID、顺序和音色记录。
- AT-13：整篇/段落/逐句三种导出准确；拼接字幕反映真实时间轴，默认句级字幕开启。
- AT-14：Script Processor 对技术术语和源文覆盖率进行审计；歧义待确认，未经授权不改写。
- AT-15：Studio 提交问答有唯一 ID、可恢复且幂等；不能恢复 Harness 时回答可持久领取，不谎报唤醒。
- AT-16：Project Root 不可信时禁止写项目；不同项目/任务/网页 Session 并发隔离。
- AT-17：MiniMax Key 不出现在日志、JSON、网页、版本控制；录音及脚本第三方上传有明确提示。
- AT-18：失败的 Chunk/字幕允许续跑；不重复生成成功缓存；无法确认是否扣费时警示。
- AT-19：MiniMax Voice Design 的真实接口、支持地区、参数和计费经实测记录；没有支持时不假称创建成功。
- AT-20：Codex 与第二个兼容 Harness 读取同一项目的声音别名及默认设置，核心 CLI 一致。

## 14. 开发前须确认的外部事实

1. 当前 MiniMax Key 区域、Provider API base URL、现有 `config.json` 真实字段（仅脱敏结构）。
2. MiniMax Voice Design **具体端点、请求/返回 Schema、收费和激活规则**；与 clone 的差别。
3. MiniMax 官方 voice list 可用分类/描述/性别字段的真实性，如何有效实现“女声”硬条件筛选，音色预览的费用。
4. MiniMax 句级字幕返回准确性、极短句、跨声音 Chunk 对齐效果及下载 URL 时效。
5. Windows 后台 Studio 进程生命周期与浏览器交互、Codex 和 Claude Code 是否提供稳定的 CLI 等待/恢复机制。
6. 碰撞写入、非 Git 项目、中文/Unicode 路径、Windows 进程重启及可靠 Project Root。

探测失败不应擅自降低安全标准；若 Provider 能力与产品 MUST 冲突，提交测试报告和最小变更选项再进入相关收费集成。

## 15. 资料与变更说明

V1.1 参考链接：
- https://platform.minimax.cn/docs/api-reference/speech-t2a-http
- https://platform.minimax.cn/docs/api-reference/voice-cloning-clone
- https://platform.minimax.cn/docs/api-reference/voice-cloning-uploadcloneaudio
- https://solutions.minimax.cn/voices
- https://solutions.minimax.cn/debug/speech

V1.2 补充核验：MiniMax 公开平台展示 Voice Design 功能/计费类别，但具体 API 以实际适用地区的官方 API 文档和运行探测为准： https://platform.minimax.io/subscribe/token-plan

**最终产品基线**：用户给出文稿和声音条件 → Agent 解析项目命名音色/文字描述与脚本结构 → 可解析则直接生成；缺配置/缺别名则本机 Studio 筛选并回答 → 一次性配置冻结为按声音分配的任务快照 → 各声音分别生成 → 对齐字幕、按导出模式合并、缓存与续跑。创建的全局音色资产独立于项目，项目可复用与命名，默认声音无需强制命名。
