# MakeSoundSkill — 产品需求文档 PRD V1.5

> **版本**：V1.5 · 2026-10-15  
> **状态**：产品与 UI 开发基线；火山引擎真实 API、各模型能力及 Harness 恢复链路待验证  
> **上游基线**：V1.4 PRD（Agent 编排、音频/SRT、缓存、续跑）；M1 已实现配置系统；本文件覆盖 V1.4 中与最新 UI、Provider 选择冲突的条款  
> **实现范围**：Windows 本地优先；Codex / Claude Code；Voice Studio 使用 HTML/CSS/原生 JavaScript；Python Core 复用 M1  
> **首个真实合成 Provider**：MiniMax；火山引擎先实现可扩展配置及引导 UI，真实合成不属于本阶段验收

## 0. 产品结论与版本变化

MakeSoundSkill 的职责是 **让 Agent 在项目内复用已确定的声音，完成口播理解、演绎编排、多声音合成、字幕、导出及恢复**，而不是重做各厂商已有的试听/音色设计网站。

用户在官网选择/复刻音色，拿到音色 ID；在 Voice Studio 保存 **厂商 Provider + 模型 Model + 音色 ID + 项目别名 + 分类**。已有有效配置时 Agent 直接工作；缺少配置时，通过 Studio 发起结构化问题，用户提交后恢复原 Job。

### 0.1 本版 MUST 决策

1. **添加项目声音支持切换厂商**：MiniMax、火山引擎（Volcengine），厂商不同则引导、模型、音色字段说明不同。**不代表火山引擎已经可以真实生成**。
2. **模型列表从对应厂商的 `config.json` 读取**；前端不硬编码模型列表。配置不存在 `models` 时提示未配置；不默认回退为随意选择的模型。模型选项来自本地配置，不等于账号实际开通或模型可用。
3. **原有 MiniMax 凭据文件只读**，包含 API Key；网页只读取后端返回的非敏感 Provider/Model 元数据，不向浏览器输出 Key。新增模型的维护应通过受控配置流程，不由项目音色表单覆盖凭据文件。
4. **右侧两个 Tab**：「添加项目声音」（默认）和「More Tools」（仅占位）。不再有「探索更多」「基础设置」大面板、官方声音池、自建试听、克隆/文本设计 UI。
5. **左侧项目音色库**：按男声、女声、其他分类展示紧凑横向短卡；卡片含头像、可用时播放的试听按钮、名称、设置入口；三行声音共享水平滚动位置，左侧分类标签固定。
6. **左侧轻量“当前需求”**：Agent 从此次对话识别角色（如主角 A、主角 B），用户可以选需求按钮并绑定项目音色；这一能力仍然存在，**不是复活独立的复杂角色池管理器**。需求列表独立横向滚动。
7. **项目持久默认声音**与当前角色分配独立；允许只保存 provider+model+voice_id 作为默认而不添加别名。修改默认需确认并原子保存，历史 Job Snapshot 不受影响。
8. **完成设置**是显著的主 CTA，Agent 问答模式下提交结构化回答并请求恢复原任务；主动管理时不伪装成通知了 Harness。提交不直接执行付费 TTS。
9. **情绪、停顿、语气词、语义分段由 Agent 自动判断**；用户可以用自然语言明确覆盖；Python 校验与转换 API 参数，不能擅自插入无依据的笑声、咳嗽或更改已确认原文。
10. 现阶段不开发火山合成、不开发任何平台声音克隆/Voice Design；用户到对应厂商平台获取 ID。保留 Provider Adapter 及未来扩展边界。

### 0.2 从旧版移除 / 保留

| 对象 | V1.5 处理 | 说明 |
|---|---|---|
| 官方音色发现、标签搜索、官方预览 | **移除前端** | 使用厂商官网 |
| 声音复刻、文本创建音色 | **本阶段不实现** | 可以经官网获取 ID；留扩展接口但非 V1.5 MUST |
| 复杂角色池操作、拖拽、轨道编辑 | **删除** | 保留当前对话需求按钮和简单绑定 |
| 情绪、语速、音量、停顿逐项 UI | **删除** | Agent 解析用户要求；Core 按默认值和模型兼容性执行 |
| 项目音色管理、默认声音 | **保留并增强** | 增加分类、Provider/Model 元数据 |
| 多声音分段与合成 | **保留核心** | 由 Agent + Chunk Planner 完成 |
| SRT、whole/paragraph/sentence、缓存与续跑 | **保留核心** | 沿用 V1.2/V1.4 的可靠性要求 |

## 1. 用户故事与流程

### 1.1 新项目首次配音

用户在 Codex/Claude Code 中确认文稿并要求生成 → MakeSound Core 检查项目声音/项目默认与 Provider 配置 → 不足则创建 `question_id/job_id`，打开本地 Studio → 用户选厂商、从对应官网获取音色 ID、选该厂商已配置模型、输入别名和分类、添加项目声音或设项目默认 → 点击「完成设置」 → Studio 提交回答 → 等待中的 Harness 获取回答并继续；若 Harness 已退出，则持久化回答，待明确恢复请求领取。

### 1.2 已配置项目

Agent 解析用户指定别名/项目默认 → 从项目声音引用解析 `provider + region + model + voice_id` → 冻结 Job Snapshot → 进行演绎与 Chunk 规划 → 真实合成仅在 Provider 支持、配置有效、任务授权有效时进行；无需打开 Studio。

### 1.3 多声音任务

用户说“主角 A 用男声1，主角 B 用女声1” → Agent 识别角色与引用；如映射完整则直接生成；如缺声音才打开 Studio；左侧当前需求用于辅助补全，绑定只作用于本任务，不静默更改项目音色、默认或历史快照。

### 1.4 主动管理

用户要求“打开声音设置” → 打开 Studio 管理项目声音、默认声音；可保存项目数据；不存在等待中的 Agent 问题时，**不显示虚假的任务恢复成功**，不发送 TTS。

## 2. 信息架构和页面布局

### 2.1 页面只有左右两个区域

**左侧：项目声音管理主区**

- 标题：「项目已有声音」和项目名称/可信项目路径简述。
- 音色三行：「男声」「女声」「其他」。用户自己选择分类，不通过 ID/名称猜测性别。
- 每行紧凑短卡：`头像 | 播放（仅有合法试听资源时） | 音色别名 | 设置`。不恢复旧的大方形展示卡。
- **三行共用一个水平滚动区**，左侧分类标签保持固定；无第三类时可显示空态。
- 「下方添加更多」为提示文本，不需要独立点击行为；可引导注意右侧“添加项目声音” Tab。
- 「当前需求」：Agent 提供若干需求按钮，独立水平滚动；选中角色后，点击项目声音卡片完成绑定。按钮显示已分配/未分配，绑定允许修改。无需在此管理大规模角色资产。
- 「默认声音」：独立固定入口，点击后走项目持久默认的快速确认，不通过当前任务角色绑定修改。
- 「完成设置」：最醒目主按钮；校验本次待回答的必要项后提交回答，不隐式发起计费。

**右侧：双 Tab**

- **添加项目声音**（默认）：Provider、Model、项目声音名称、音色 ID、男声/女声/其他、厂商引导链接、添加到项目库。可以从编辑入口预填已有音色并改名/分类/Voice ID（重绑定确认）。
- **More Tools**：仅占位。不得虚构已经实现的音频编辑、克隆、设计服务。

### 2.2 适配

桌面宽屏左右分栏；窄屏/侧栏宽度自动变为上方项目列表、下方 Tab 表单。表单容器更接近竖向长卡，横向音色列表与需求列表独立滚动，页面无整体横向溢出。文字长 Voice ID 可折行/截断显示但复制必须是原始全文。键盘可操作，具有明显 focus 与错误状态。

### 2.3 视觉基线

沿用已经确认的 **Cel Shading 主风格 + Bauhaus/Mondrian 色彩 + 少量 Neo-Brutalist Playful 反馈**：纯色、粗黑描边、适度硬偏移阴影、紧凑声音卡、少量点缀；不使用玻璃拟态、渐变或大型无关插画；不出现 WEFT/PPL。现阶段优先交互正确，不重新开启视觉探索。

## 3. 右侧「添加项目声音」表单

### 3.1 字段

| 字段 | 必填 | 数据来源/语义 | 校验 |
|---|---|---|---|
| Provider | 是 | UI 选择 `minimax` / `volcengine` | 必须为注册厂商 |
| Model | 是 | 当前厂商 `config.json` 中 `models[]` | 只允许选已配置模型；明确是否可真实合成 |
| 项目音色名称 | 添加到项目库时是 | 用户命名的 alias | 项目内唯一；规范化冲突需提示 |
| Voice ID / 厂商音色标识 | 是 | 用户在厂商平台复制 | 保留原样；不跨厂商共用 |
| 分类 | 是 | `male`/`female`/`other` | 仅 UI 分类，不代表 Provider 断言 |
| Region / Base URL | 不直接表单编辑 | 从 Provider 配置解析 | 需在后端验证配置一致性；不得跨区试 Key |

**注意**：Project Default 独立入口可直接保存 Provider+Model+Voice ID，不要求填写 alias；“添加到项目库”则需要名称。

### 3.2 厂商引导

- MiniMax：展示「到 MiniMax 试听/创建并复制 Voice ID」，链接 `https://www.minimax.cn/audio`；字段名称 MiniMax Voice ID。模型选项只取本地配置。
- 火山引擎：展示火山音色标识的操作说明及官方入口（**在核实正确 URL 后才写入**），说明需要对应 API 资格、资源/模型/授权等条件；这些字段的真正请求契约需 Provider 实测后确认。若 Core 尚未实现该厂商，明确标注「仅保存配置 / 暂不可由本 Skill 生成」。不假装火山一定采用同 MiniMax 的字段。
- 切换厂商：重新加载该厂商模型；不把上一个厂商的模型或 ID 作为新厂商有效值；防止未保存内容无意丢失（可在本地保留每个厂商的草稿或提示确认）。
- 官方页面生成的试听效果参数**不会包含在复制的 Voice ID 中**，不可把 ID 当作包含完整表演设置的预设。

### 3.3 保存动作

- 「添加到项目库」：需要完整字段；写入当前 Project Preset，原子保存，revision 检测；保存成功出现在左侧相应分类。若同名存在，提供查看差异和明确重绑定确认，不能静默覆盖。
- 「设为项目默认」：单独触发确认并原子保存；允许无 alias 的直接引用；历史 Job Snapshot 保持原样。
- 「完成设置」：提交本次 Task Voice Assignment/当前配置回答；不把保存项目、设置默认、生成音频三个动作混成同一个不可撤销操作。
- 首次引导的保存项目默认遵循用户明确勾选或点击的行为；默认是否勾选可按原既定首次规则保留，但必须可见且可取消。
- 若项目路径无法可信确定，不擅自将数据写入工作目录/Home，允许“仅本次”或提示明确项目路径；无效配置禁止付费请求。

## 4. Provider 配置规范（关键）

### 4.1 职责分层

| 层级 | 位置 | 内容 | 写权限 |
|---|---|---|---|
| MiniMax Provider Config | `Path.home() / .config/minimax/config.json` | API Key、region、base_url、`models[]`、可选 default_model | **MakeSound 只读** |
| 火山 Provider Config | 对应厂商专用 `config.json`（路径由部署规范确定） | 对应鉴权/区域、model 列表、必要非敏感元数据 | **MakeSound 只读** |
| Project Preset | `<project>/.makesound/preset.json` | 命名声音、分类、绑定的 Provider+Model+Voice ID、项目默认、项目输出选项 | 原子写、revision 校验 |
| Job Snapshot | 用户数据目录中的 job 存储 | 任务时实际已解析的 Provider、region、模型、ID、参数及分段 | 创建后冻结，续跑时复用 |

**`config.json` 读取模型列表是本版要求，不等于要求 MakeSound 修改旧的只读密钥文件。** 若 `models` 尚不存在，需要由用户或受控配置脚本显式补充；未经允许不可自动覆盖已有字段。不能把 API Key 发送到前端/日志/项目文件。

### 4.2 MiniMax 配置示例（约定格式，不是官方标准）

```json
{
  "api_key": "REDACTED_EXAMPLE_ONLY",
  "region": "cn",
  "base_url": "https://api.minimax.cn",
  "models": [
    {"id": "speech-2.8-hd", "name": "Speech 2.8 HD"},
    {"id": "speech-2.8-turbo", "name": "Speech 2.8 Turbo"}
  ],
  "default_model": "speech-2.8-hd"
}
```

以上展示的是**建议的本地配置 Schema**；示例模型需要通过 Provider 能力表和用户实际配置核实，不能将填写入配置等同于账号已开通。

### 4.3 加载规则

1. `doctor` 检查配置存在、JSON 结构、region/base_url 一致性、`models[]` 形状与 Key 是否非空；仅输出脱敏诊断，不对真实 Provider 做无授权付费验证。
2. `provider list/models --json`（目标 CLI 契约，可据现有代码调整）通过 Python 返回不含密钥的 `provider/status/models/default_model/warnings`。
3. UI 从后端拿取模型数据，不能直接 `fetch` 含凭据的原始 config.json。
4. 缺少 `models[]`：UI 明确提示“该厂商尚未配置可选模型”；不将其误认为 API Key 无效；不能临时硬编码选择列表并默默保存。
5. `default_model` 必须属于 `models[]`，否则配置警告/无默认模型，提示人工修复，不静默换模型。
6. 项目已保存的模型不随着 Provider 配置 `default_model` 改动而自动改变；后端合成时必须仍验证其可用及兼容性。
7. Provider 字段契约差异封装在 Adapter 与配置描述器中；`provider + region + model + voice_id` 为统一解析后的语义，真正 API 参数由各厂商映射。
8. 火山尚未接入真实 Provider 时，允许准备/保存项目引用，但**不可把它当成 `ready-to-generate`**；Job 返回 provider_not_implemented 或其他明确可修复状态，不回退 MiniMax。

### 4.4 不改变旧代码的兼容策略

M1 已实现的 config loader、项目预设、资产引用和 revision 是基线。先检查现有 Schema 是否支持模型选项与分类：若需要更改，提供**向后兼容、显式迁移、备份与测试**方案，未批准不得直接覆盖旧格式。用户自己新增字段时，不应迫使此前已保存项目的数据重建。

## 5. Agent 自动演绎与音频生成（继承 V1.4）

### 5.1 输入及表现策略

Harness 定位用户明确确认的口播稿，保持 Document → Paragraph → Sentence 结构；剔除明确不朗读的镜头备注并保留审计记录；保留术语、版本号、原稿停顿标记。

Agent 根据语义/角色设计结构化表现计划：情绪、语义停顿、必要的语气词、分段和声音分配。**不得无依据地增加咳嗽、笑声等动作**；技术教程以清晰自然为优先。用户明确指示高于自动编排。用户不必在 UI 手动勾选情绪/停顿/语气词。

### 5.2 Python 执行边界

- Validate Script Manifest，情绪与模型能力匹配；`auto` 转为省略 Provider 的情绪参数（当该 Provider 适用）。
- 不同 Voice ID/Provider/region/模型/情绪而无法同请求处理的片段，划分为独立 Chunk；不能假设多厂商的一次请求可以混合音色。
- 用户显式的 `<#x#>` 与支持的语气词由 MiniMax Adapter 合法编码；火山未来由自己的 Adapter 定义，不直接透传 MiniMax 私有 token。
- 输出 `whole` / `paragraph` / `sentence`，默认 paragraph；字幕默认 `true`、句级 SRT，使用供应商可靠时间信息及最终音频实测时长；不能按字数猜时间。
- 音频或字幕失败准确标记，保留成功 Chunk、缓存和失败恢复信息；已冻结的 Job 不重新解析新改的项目声音。
- 只有已确认文本 + 有效 Provider 配置 + 授权任务方可收费合成；无法确认是否重复计费时不自动盲重试。

## 6. Harness 问答、恢复与安全

- `question_id`、`answer_id`、`job_id` 均属于 MakeSound；Harness Session ID 是单独的桥接标识，不作为声音会话偏好。
- Studio 仅监听回环、随机端口；实际返回 URL；严格会话令牌、Origin/CSRF、路径与权限限制。未经验证不向云端 Harness 展示不可达地址。
- 用户提交后记录不可变的结构化回答；Agent 尚在 wait 时领取并继续；Agent 已结束则保存待领取，支持再次发送“继续任务”。wait 超时不等于问题 TTL 过期。
- 完成设置不是直接发起 TTS；保存项目默认、添加项目音色、提交 Agent 回答是不同动作。
- 不宣称网页自动唤醒了 Codex/Claude，除非有真实桥接确认；绝不在明文 JSON、前端、日志或 Job Snapshot 中暴露 API Key。

## 7. 项目数据结构（示意，非 M1 已实现的强制 Schema）

```json
{
  "schema_version": "1.5-proposed",
  "project_settings": {"export_mode":"paragraph", "subtitle_enabled":true, "subtitle_type":"sentence", "audio_format":"mp3"},
  "named_voices": {
    "男声1": {
      "category":"male",
      "ref":{"kind":"provider_voice","provider":"minimax","region":"cn","voice_id":"VOICE_ID_EXAMPLE"},
      "model":"speech-2.8-hd"
    }
  },
  "default_voice": {
    "ref":{"kind":"provider_voice","provider":"minimax","region":"cn","voice_id":"VOICE_ID_EXAMPLE"},
    "model":"speech-2.8-hd"
  }
}
```

- 分类只是项目 UI 展示字段，不能作为真实 Voice ID 的自动性别推断。
- `region` 必须来自可信的 Provider 配置/显式设置，而不是因示例写了 `cn` 就无条件迁移旧项目到国内。
- 最终存储格式以 M1 现有 Schema 和兼容迁移方案为准。

## 8. 实施顺序与里程碑

| 阶段 | 范围 | 停止点 |
|---|---|---|
| M1（已有） | 本地 Provider 配置、项目别名、默认声音、revision、基础快照 | 不推翻已有 49 项离线通过结果 |
| M1.5-A | 前端影响评估：从 V1.3/V1.4 删除过时组件，页面重排为左侧项目声音 + 右侧双 Tab | 输出差异与数据兼容报告 |
| M1.5-B | Provider-aware 配置读取、模型下拉、项目分类、添加/修改/默认/当前需求绑定的 Mock 流程 | 浏览器自动测试、无真实 API |
| M1.5-C | 与 M1 Core 的非收费接口联通、只读 provider config 读取、脱敏、原子项目保存 | 明确回归结果，停止等待审核 |
| M2 | Agent Script Processor、情绪/停顿/语气词、多声音 Chunk、音频/SRT/缓存/续跑；优先 Fake Provider | 不自动进入真实付费调用 |
| M3 | Studio 本地服务、Question/Answer/ResumeIntent、Codex/Claude 联调 | 跨进程端到端验收 |
| M4 | MiniMax 真实受控验收（需用户付费授权）；火山 Provider 另行规划 | 不因 UI 展示就宣称火山已接通 |

## 9. 验收清单

### 9.1 UI / Config

- [ ] 左侧项目三分类分组正确；三行声音区同步横向滚动，左侧标签固定；当前需求区域独立滚动。
- [ ] 短卡头像、名称、试听（有真实合法资源才可播放）、设置分工明确；无预览时禁用且说明。
- [ ] 默认声音单独快速设置，需明确确认；不强制 alias；修改不影响已有 Job。
- [ ] 当前需求绑定只作用当前任务；完成设置在有 Question 时提交正确 Job/Answer；无 Question 不虚称恢复 Harness。
- [ ] 右侧默认“添加项目声音”；两个 Tab 切换保留未保存输入；More Tools 仅占位。
- [ ] 选择 MiniMax/火山时引导内容、模型列表、提示与音色 ID 草稿不串用；未接入 Provider 明确显示不可合成。
- [ ] MiniMax `models[]` 从只读 config.json 经过后端脱敏接口提供；缺失列表有可修复提示，前端不硬编码。
- [ ] 项目别名唯一，同名更改/跨厂商重绑定需要明确确认及 revision；跨项目同名允许。
- [ ] 分类为用户选择的 male/female/other；无可信依据不自动判断性别。
- [ ] 窄屏无整体水平溢出；基本键盘导航/焦点/错误反馈可用。

### 9.2 Core / 安全

- [ ] M1 原有测试持续通过；旧 Schema 兼容、备份、迁移测试有记录。
- [ ] Provider 配置 key 不进入浏览器、项目 JSON、stdout 或日志；Base URL/region 冲突禁止请求。
- [ ] 只有 MiniMax 真实 Provider 被实现且验收时才能生成；火山只展示配置绝不隐式回退收费。
- [ ] Agent 自动情绪/停顿/语气词保留显式原稿标记，未经用户许可不擅自增加表演内容。
- [ ] 字幕默认开启，时间基准严格，任务失败可恢复，未知计费不盲重试。
- [ ] 不调用真实付费 API 的开发阶段应由 Fake Provider 和请求拦截证明。

## 10. 已知待验证项，不作为前端自行推断依据

1. 火山引擎正确的官方声音管理入口、音色 ID、鉴权体系、模型名称、地区及实际 Provider API 字段；先保留引导位置并标明未验证。
2. 现有 M1 项目 Preset 是否能无损加入 `category`、Provider 对应模型；需要先做兼容审查。
3. 各厂商 `config.json` 的路径、模型列表维护方式（MiniMax 已确定路径；火山路径还需部署规范确认）。
4. Codex / Claude Code 从网页回答恢复原 Agent 任务的真实生命周期，尚不等同于文档设计。
5. MiniMax 的实际句级字幕精度、语气词支持矩阵、收费/账号权限；仍需受控 M4 实测。

---

**V1.5 最终基线**：官网选音色与生成 ID → Studio 选择厂商、读取该厂商 config.json 中的可用模型、输入 ID、别名与分类 → 保存项目音色/项目默认 → Agent 根据当前对话自动识别角色并编排情绪/停顿/语气词 → Python 可靠地分段合成、生成字幕、缓存与续跑。UI 不复制 Provider 平台已有的试听、复刻和音色设计工具。
