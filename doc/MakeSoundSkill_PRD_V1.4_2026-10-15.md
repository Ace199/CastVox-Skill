# MakeSoundSkill — 产品需求文档 PRD V1.4

> **日期**：2026-10-15  
> **状态**：产品决策基线（待 M2/M3 实现及真实 API 验证）  
> **继承基线**：`MakeSoundSkill_PRD_V1.2_2026-10-14.md`；本版取代 `MakeSoundSkill_Voice_Studio_PRD_V1.3_2026-10-15.md` 中与简化方向冲突的 UI 条款。  
> **产品定位**：Agent-Native Audio Generation Skill；**V1.4 支持的 Harness**：Codex、Claude Code；**首个 Provider**：MiniMax。  
> **核心原则**：**用户指定厂商、基准模型与 Voice ID；Agent 自动理解口播与演绎；Python 确定性合成、校验、导出及恢复。**

## 0. 本次决策摘要与变更边界

### 0.1 已确认的决策（MUST）

1. 不在 Voice Studio 重做 MiniMax 官网已提供的**官方音色搜索、筛选、试听、声音复刻、文本音色设计、复杂音频编辑**。用户可在 `https://www.minimax.cn/audio` 选择声音并复制 Voice ID；网页提供明确外链。
2. **删除可视化角色池（角色卡片、绑定按钮）以及“探索更多”音色浏览区/Tab、内置声音池和内置试听生成器。** 这仅是删除 UI；Agent 的多角色识别、按角色/段落/句子分配音色、多声音 Chunk 合成仍属核心功能。
3. Voice Studio 仅围绕**项目声音管理与必要配置**：`Provider（厂商）`、`Model（基准模型）`、`Voice ID`、项目内音色别名、项目默认声音，以及独立的项目输出设置（如格式与默认字幕）。V1 初始 Provider 仅 MiniMax，保留扩展边界。
4. **情绪、语义停顿、必要的语气词及 Chunk 编排由 Agent 根据已确认文本和用户指令生成**，用户不用逐项点击设置。用户显式指定的情绪/停顿/语速优先；禁止擅自添加无依据的表演情节或修改事实。
5. 声音表现参数的未指定值由后端稳定默认提供：如 `speed=1.0`、`volume=1.0`，`emotion=auto` 表示省略 API 字段。`pitch` 不放入网页；兼容旧预设中的 pitch，但不作为新用户必填项。
6. 支持**不命名而直接设为项目默认 Voice ID**；支持为同一项目命名多个声音、别名冲突确认与安全重绑定。不同项目允许别名同名。
7. **“完成设置”是 Agent 问答提交，不是直接发起收费 TTS。** 有待处理问题才展示“完成设置并继续任务”；主动管理时用“保存项目配置”等明确操作。问题/回答和任务快照机制保留。
8. 新创建音色**默认归属当前项目**为目标方向；M1 既有全局资产注册模块暂不直接删除或迁移。具体项目资产存放、跨项目复用、历史引用迁移须另行定 Schema 与迁移方案。
9. 视觉仍采用已确认 Cel Shading + Bauhaus/Mondrian 色彩 + 少量 Neo-Brutalist 交互，但 UI 大幅缩减，强调高效配置而非音色展示型工作台。

### 0.2 版本优先关系

本版对 V1.2/V1.3 的**产品与 UI 冲突条款**优先。V1.2 里与本版不冲突的 Provider 安全、项目隔离、脚本 Manifest、字幕验证、缓存、断点续跑、错误处理及 CLI 契约继续有效。M1 已完成并有离线测试报告（用户报告 49 项通过）；本版不等于上述新功能已经实现。

## 1. 产品定位、用户任务与目标

MakeSoundSkill 主要被 Codex 或 Claude Code 调用，用户在 Agent 中确认脚本，并用自然语言指定声音/角色。系统从项目配置找到对应 `provider + region + model + voice_id`，由 Agent 进行语义编排，再由 Python 合成、缓存、导出音频及句级 SRT。

### 1.1 典型场景

- **首次配置**：“用 MiniMax 给这段配音” → 未找到有效默认 → Studio 打开简化配置 → 用户去 MiniMax 官网选声、复制 Voice ID → 粘贴、选择模型，明确应用或设为项目默认 → 提交回答 → Agent 继续。
- **已有配置**：“用项目默认声生成教程旁白” → 配置 ready → 不开 Studio，Agent 清理非口播并编排，直接进入校验及生成。
- **多声音**：“主角 A 使用男声1、主角 B 使用女声1” → Agent 将角色与项目别名映射到具体 Voice ID，拆分 Chunk；不要求在网页逐个绑定角色。
- **语气指令**：“第二句惊讶一点，停顿半秒” → 作为本任务显式覆盖，生成结构化表现计划；不改写项目音色默认值。
- **别名缺失**：“主角 A 用男声3”，项目中没有男声3 → 停止收费合成，引导用户到 MiniMax 选择声音并在 Studio 录入/命名；不擅自拿其他声音替代。
- **主动管理**：“打开声音设置” → Studio 打开项目声音列表；增删改、设默认等可保存，不生成音频。

### 1.2 非目标

Voice Studio 不承担官方音色浏览、声音试听播放器、声纹录音上传、Voice Design、逐字音频编辑或可视化角色编排。后续可重新评估，但不能作为 V1.4 首版验收前置。

## 2. 职责划分与架构

| 组件 | 负责 | 不负责 |
|---|---|---|
| MiniMax 官网 | 找声音、官方试听、复刻/设计音色、复制 Voice ID；官网参数可供人参考 | 不替 MakeSoundSkill 保存项目别名或处理 Agent Job |
| Voice Studio | 项目音色别名、默认声音、Provider/Model/Voice ID、少量项目输出参数；提交 Agent 配置回答 | 不提供自建官方音色库、在线试听或角色池 |
| Harness Agent | 定位已确认稿、解析角色、分配 Voice ID、生成情绪/停顿/语气词等结构化计划、处理需要确认的歧义 | 不持有 API Key、不直接拼出未经校验的 API 请求 |
| MakeSound Python Core | 配置解析与权限、Manifest/Schema、Chunk Planner、Provider Adapter、音频/SRT 导出、缓存、续跑、原子存储 | 不擅自选择或替换用户要求的声音 |

**M1 数据模型保持不动**：本阶段通过 UI adapter 映射现有结构；如后续需要项目创建资产注册迁移，另列数据迁移任务。

## 3. 简化后的 Voice Studio 产品要求

### 3.1 页面结构

一页式桌面优先配置界面，窄视口单列可滚动：

1. **当前项目与配置来源**：项目名、可信 Project Root 状态、当前任务是否等待回答；无项目根目录时说明仅本次或全局可用。
2. **项目声音列表**：显示音色别名、厂商、模型（若模型属项目/音色覆盖则准确显示来源）、Voice ID（长 ID 可复制）、默认标记；编辑/重绑定/删除入口。
3. **新增/编辑声音**：Provider（V1 MiniMax）、Model、Voice ID、可选项目别名；`前往 MiniMax 选择音色` 明确打开 `https://www.minimax.cn/audio`。输入时不应猜测、改写或裁剪 Voice ID。
4. **项目默认声音**：允许直接引用当前输入的 Voice ID 而不加入命名库；设为默认需明确保存；新旧 Job Snapshot 不受影响。
5. **项目生成默认**：字幕默认开启、句级 SRT、导出模式默认 paragraph、音频格式 MP3/WAV 等可以保留为**单独、精简、可选的项目配置区**，不与 Voice ID 混同。不显示情绪、停顿标签编辑器、语气词选择器、Pitch、内置试听播放器。
6. **上下文主 CTA**：有 Agent 待回答任务时为 `完成设置并继续任务`；用户主动管理时为 `保存项目配置`，不宣称向 Harness 已成功投递，除非收到了真实确认。

### 3.2 操作和保存

- `添加到项目库`：项目内别名必填且唯一；可引用官方 Voice ID 或既有资产引用。
- `设为项目默认`：别名可选；默认设置与添加项目库分开，两者可同时选择，也可只做其一。
- 既有别名改名/重绑定时弹出确认，按 `revision` 做冲突检测；任务快照冻结具体 provider/region/model/voice_id。
- 未收到保存成功，不显示已保存；未提交表单不会启动合成；“保存项目配置”不自动触发付费调用。
- 针对输入 ID 的**格式检查**与**真实可用性验证**区分：只通过本地校验不能声称 Voice ID 已在当前账户可用；列表缺席也不必然意味着 ID 无效。无法确认时显示 `unverified/unknown`，真正合成遇到不合法 ID 不自动换声。
- 官网试听时的情绪、语速、音量等设置**不会随复制的 Voice ID 自动携带**。MakeSoundSkill 只接收 Voice ID 和明确保存的自有参数；无显式参数时使用后端默认/Agent 编排。

### 3.3 窄屏、视觉与可访问性

- 沿用 Cel Shading：粗描边、纯色、适量硬阴影；表单密度优先，彩色只突出项目默认、待保存和主 CTA。
- 不再使用原来的长工作台三区、男/女两行声音探索、声音池方卡、角色池横向拖拽。已确认的横向短卡元素可用于项目声音列表，但视信息密度决定，不强制复杂滚动。
- 适配桌面及 Codex/Claude 侧栏近手机宽度；输入框、保存按钮不溢出；键盘可操作，错误在字段旁清晰提示。
- 不添加 WEFT/PPL 标识；不因美术效果遮挡 Voice ID 或操作状态。

## 4. Provider/Model/Voice ID 与项目配置

### 4.1 选择和继承

用户需要确认的**声音身份必需项**：Provider、基准 Model、Voice ID。当前项目允许多份命名声音及一个持久默认；新任务按显式角色/别名 → 项目默认 → 全局默认解析。有效配置已存在则不再重复开网页。用户明确的硬约束与既有音色冲突时需询问，不静默使用违背要求的默认。

字段按职责分别合并：本次明确覆盖 > 项目所保存的有效字段 > 全局有效默认 > 非声音身份的内置技术建议值；**内置示例 Voice ID 绝不算用户已确认默认**。没有 Session Preference 声音层；网页问答 Session 仅关联一次配置问题。

### 4.2 示例 Schema（概念级，M1 实际 Schema 为准）

```json
{
  "schema_version": "1.2",
  "project_settings": {
    "export_mode": "paragraph",
    "subtitle_enabled": true,
    "subtitle_type": "sentence",
    "audio_format": "mp3"
  },
  "default_voice": {
    "ref": {
      "kind": "provider_voice",
      "provider": "minimax",
      "region": "configured",
      "voice_id": "VOICE_ID_FROM_MINIMAX"
    },
    "model": "speech-2.8-hd",
    "voice_settings": {"speed": 1.0, "volume": 1.0, "emotion": "auto"}
  },
  "named_voices": {
    "旁白男声": {
      "ref": {
        "kind": "provider_voice",
        "provider": "minimax",
        "region": "configured",
        "voice_id": "VOICE_ID_FROM_MINIMAX"
      }
    }
  }
}
```

**注意**：该 JSON 是目标语义示例，不是已实施的数据迁移或 MiniMax 请求体；`model` 字段在具体默认/别名配置中的落点需适配 M1 已有 Schema、并确保同一任务能解析到冻结的有效模型，不自行写入未定义字段。`VOICE_ID_FROM_MINIMAX` 是占位值。

### 4.3 凭据与地域

本机凭据只读：`Path.home() / '.config' / 'minimax' / 'config.json'`。读取 `api_key`、`base_url`、`region`（具体键结构以当前文件和已确认 Adapter 为准），地区与域名冲突阻止请求，绝不把密钥写项目配置或网页、stdout、报告。地域不得写死 `cn`；M0 只证明用户当时本机声明为 `cn`，不等于已鉴权。

## 5. Agent 自动演绎规划（V1.4 核心新增/强化）

### 5.1 决策边界

- **Voice ID / Provider / Model**：由用户已确认配置确定。Agent 不能擅自换声音、换厂商、换模型。
- **Emotion（情绪）**：根据剧本类型、上下文与显式标注判断；普通技术教程默认自然/中性，可省略情绪参数；不强迫每句赋情绪。
- **Pause（停顿）**：保留原文 `<#0.8#>` 等合法显式标记，其次依据语义与剪辑边界规划；自然 TTS 韵律不机械叠加静音。
- **Vocalization（语气词/非言语发声）**：只有原稿明确标注、用户要求，或戏剧情境确有充分依据时添加；**教程、说明和已确认口播默认不新增咳嗽、笑声、叹气**。
- **Speed**：无明确要求时默认 1.0；可以根据用户本次自然语言调整，但不应随情绪自动大幅改变语速。
- **Volume**：默认 1.0，显式指定才覆盖；Pitch 不提供新 UI 操作。
- **原文保护**：默认 narration_only，不改变术语、数字、步骤、事实；具有歧义的修改或删除进入 needs_review；允许显式授权 rewrite。

### 5.2 文稿类型建议

| 类型 | 默认策略 | 需避免 |
|---|---|---|
| 教学/CG Pipeline | 清晰、自然，尊重版本号/术语和明确停顿 | 擅加戏剧性语气词、改变技术步骤 |
| 产品演示/宣传 | 可按段落调整表达力度 | 过度情绪化、擅自改写承诺 |
| 剧情/动画对白 | 根据角色/场景分配声音，适量情绪与必要非言语发声 | 无来源的表演动作或跨角色串声 |

### 5.3 Manifest 表达（示意，需更新 Schema）

```json
{
  "schema_version": "1.4-proposal",
  "paragraphs": [{
    "id": "p001",
    "sentences": [
      {
        "id": "p001_s001",
        "text": "我今天很开心。",
        "voice_alias": "主角A配音",
        "performance": {
          "emotion": "happy",
          "pause_after_ms": 500,
          "vocalizations": []
        }
      }
    ]
  }]
}
```

**不是完整有效 Script Manifest**：生产 Schema 仍必须含 `source`、哈希、source_range、removed_items、稳定 ID 与 voice_assignments；示例只是说明新增的 `performance` 字段。`voice_alias` 若现有 Schema 规定在独立 `voice_assignments[]` 中，则应沿用现有分离结构，而非把别名强行嵌进句子。

### 5.4 Agent 与 Python 责任分界

1. Agent 先对照用户指令、角色、已确认文本，产出结构化演绎计划与理由/来源标签（如 `explicit_script`、`user_override`、`agent_inferred`）。
2. Python 使用 JSON Schema 校验：有效情绪枚举、模型兼容性、停顿范围、语气词白名单、原文覆盖率、跨角色/声音边界及 Chunk 上限。
3. Emotion 属于一次 TTS 请求的 `voice_setting.emotion`；不同情绪如需分段则拆 Chunk，不能假定彩色情绪标签天然支持在一个请求内切换。
4. 停顿标记和语气词按**目标 MiniMax 模型与当前官方接口已验证的控制语法**转换到 `text`，不把内部字段原样透传。不能放置非法首尾或连续停顿标记。
5. 不能可靠转换或校验的控制指令：删除不被允许；应报错、标记 needs_review 或要求用户澄清；不得静默忽略显式指令。
6. 一旦任务进入生成，冻结实际 provider/region/model/voice_id、表现计划、文本和导出策略；重试/续跑不得受新项目默认配置影响。

### 5.5 用户可控与可审计

用户无需在网页逐条编辑演绎标签，但可对 Agent 说“第二句不要笑声”“停顿更长”“全篇中性”“只保留原稿标记”；用户的明确指令优先。生成前可提供简短演绎摘要；对于会显著改变已确认文案的新增非言语发声，先确认。Manifest 保存内部演绎字段和来源，便于局部重生成及查错。

## 6. 多角色、多声音与合成层级

- 角色由 Agent 从脚本识别；用户通过自然语言指定角色对项目别名的对应关系。**取消角色池 UI，不取消 Voice Assignment 业务能力**。
- Project Alias → 具体 Provider/Model/Region/Voice ID；同一项目可有多个声音，不同角色可用同一个 Voice ID 但不同本次情绪策略。
- 保留 `Document → Paragraph → Sentence`；句内必要换声时增加 span，不破坏源稿索引。
- Chunk 按**实际 Provider、地区、模型、Voice ID、声音参数及情绪兼容性**划分；不同声音不能放入同一普通 TTS Chunk；拼接按真实音频采样与停顿处理。
- 导出 `whole | paragraph（默认） | sentence`；保留 MP3/WAV、局部重生成、缓存键包含实际有效参数；不因别名后来重绑定而覆盖旧任务结果。

## 7. 字幕、缓存、续跑与收费保护

- 句级 SRT **默认启用**；实际 MiniMax 请求应明确启用。字幕必须来自可验证的真实时间数据或经过验证的对齐流程；不可按字数臆造句级对齐。
- 音频已生成但字幕不可靠：保留音频并标记 `subtitle_failed`/任务部分失败，不报告整个 Job 完成；用户可明确选择无字幕导出，不自动引入收费 ASR。
- 试听已由 MiniMax 官网负责，MakeSoundSkill 不额外为网页配置触发付费合成；正式生成需任务处于 ready、已完成必要配置及授权校验。
- 网络超时/结果不确定时标记 `billing_unknown`，不可盲目重发；成功 Chunk 缓存复用，局部重做只处理受影响单元。
- CLI `--json` 输出机器可读且脱敏；真实音频文件存在、可解码、SRT 合法后才汇报成功。

## 8. Studio 问答与 Harness 恢复

Studio 的作用收敛为**结构化配置问题回答器**。当项目没有有效默认、Voice ID/别名缺失或用户主动要求更改配置时才打开。流程：

`Agent 请求配置 → Studio 返回真实 localhost URL → 用户在官网取得 ID → Studio 保存/应用 → 持久化 Answer → 仍在等待的 Harness 获取回答并继续 / 已退出时通过同 Job 恢复`。

- Studio `question_id`、`answer_id`、`job_id` 与 Harness Session ID 分离；不引入 Session Preference 声音继承层。
- `wait_timeout` 不等于问题过期；合法迟到答案应能持久领取，网页关闭不撤销已提交结果。
- 只有真实桥接已验证时才声称自动唤醒；否则提示已保存、给出在原会话继续的明确方式。
- “完成设置”提交**当前问题的有效回答**，不是直接收费生成；无当前问题时只执行显式保存。
- 回环监听、随机令牌、CSRF/Origin、项目隔离、并发幂等及敏感日志保护沿用 V1.2。

## 9. CLI/Schema 与 M1 兼容性

M1 已存在的 `doctor`、配置解析、项目别名、默认声音、原子存储、revision 重绑定和基础快照逻辑不得因简化网页而破坏。沿用既有 CLI 接口语义（包括 `config resolve`、`studio start/wait`、`generate`、`jobs resume` 等规划接口），由具体阶段明确哪些已实现。

**需新增/调整的开发项**：

- Voice Studio 简化 UI 模块与 Mock 数据接口；停止开发旧 VoicePool、RolePool、Explore/Preview/Clone UI。
- `ScriptManifest.performance` 或独立 `performance_plan[]` 的 Schema、Agent Prompt、Validator、Chunk Planner 与异常审计规则。
- Provider 能力表：按模型启用 Emotion、Pause、Vocalization 等，不支持的字段不可发送。
- 将 Model 与 Voice Reference 的作用域、继承、快照语义明确映射进现有 M1 Schema；**不要为了适配 UI 静默修改已持久化的文件结构**。
- “项目新建音色归属项目”属于后续模型迁移决策；在未批准迁移方案前，保留 M1 全局资产注册数据和历史引用。

## 10. 分阶段开发与验收

| 阶段 | 交付 | 非目标/门槛 |
|---|---|---|
| M1（已完成，据用户交付报告） | 配置、音色别名、默认值、原子存储、基础 CLI、离线测试 | 不等于真实 MiniMax 验证 |
| M1.5-UI（下一项前端任务） | 简化版项目声音配置：Provider/Model/Voice ID/别名/默认/保存/完成设置 Mock，窄屏和浏览器检查 | 不做音色池、试听、角色池、声纹创建或付费 API |
| M2（核心能力） | Agent 表现计划、Manifest Schema、角色映射、Chunk、FFmpeg/SRT、缓存续跑、Fake Provider 测试 | 不用真实 Key 做单元测试 |
| M3（Studio 集成） | Python 服务提供静态 HTML/JS 和真实配置接口；Question/Answer/Wait/Resume 端到端、Codex/Claude Code 测试 | 不自动承诺外部网页唤醒任意会话 |
| M4（真实 MiniMax） | 经明确授权测试 TTS/字幕与 Voice ID、兼容性、计费边界 | 新声音设计/复刻操作改由官网进行，Skill 不重复实现创建 UI；不无授权请求 |

### 10.1 验收清单（必测）

- **UI-01**：有现成默认时新任务直接运行，不强制打开 Studio；无默认时出现简化配置。
- **UI-02**：可以复制粘贴官方 Voice ID；不会变更大小写/下划线/空格；可显示用户是否已真实验证。
- **UI-03**：添加项目别名与设置项目默认是独立动作；不命名也可设默认。
- **UI-04**：同项目重名有确认及 revision 检测，不同项目可同名；旧 Job 的具体 Voice ID 不变。
- **UI-05**：没有角色池、探索更多音色库、内置试听/复刻/设计 UI；官网外链正确。
- **UI-06**：完成设置只提交有效回答；断开/取消/超时不生成收费音频；无 Harness 桥接不谎称已唤醒。
- **AGENT-01**：教程朗读不会无依据加入咳嗽/笑声，不修改事实与专业术语。
- **AGENT-02**：明确指令“第二句惊讶、停顿 0.5 秒”准确生成结构化计划；不支持模型则阻断或请求用户确认。
- **AGENT-03**：已存在的显式 `<#x#>` 按合法语法保留，非法边界有错误提示，无双重静音。
- **AGENT-04**：多角色→各自 Voice ID；声音/情绪变化正确拆 Chunk；完整输出顺序不乱。
- **OUTPUT-01**：whole/paragraph/sentence 及默认句级 SRT，严格使用真实时间；字幕失败不得报告 completed。
- **RESUME-01**：缓存命中、失败续跑、billing_unknown 防重复收费、两项目并发隔离。
- **SAFE-01**：MiniMax 凭据只读且脱敏；Web 不读取任意路径；任何付费操作有正确授权边界。

## 11. 待开发验证、尚未拍板的边界

1. MiniMax 官网每个声音复制出的 ID 对当前账户、地区和目标模型的真实兼容性需受控验证；**Voice ID 本身不包含官网调好的声音演绎参数**。
2. MiniMax API 对情绪/语气词/停顿的支持及准确表现需要按实际模型和最新文档/实测维持 Capability Table；不应凭一次网页截图假定所有效果一致。
3. 项目创建音色资产的最终存储、跨项目复用与 M1 全局资产表的迁移细节仍待单独设计，不能把“新资产归项目”当作代码已经实现。
4. `Model` 是项目级默认还是允许命名音色级覆盖，须对齐 M1 Schema 并明确定义合并策略；本版只锁定**生成前必须解析到唯一基准 Model**。
5. 自适应演绎的测试集必须分别覆盖教程、产品演示与动画对白，明确哪些可推断、哪些必须二次确认。

## 12. 参考与后续文档维护

- MiniMax 官方产品入口：<https://www.minimax.cn/audio>
- MiniMax 官方 TTS API：<https://platform.minimax.cn/docs/api-reference/speech-t2a-http>
- 已有基线：`MakeSoundSkill_PRD_V1.2_2026-10-14.md`
- 旧 UI（替代）：`MakeSoundSkill_Voice_Studio_PRD_V1.3_2026-10-15.md`
- M0 能力调查：`M0_Discovery_Report.md`、`Capability_Matrix.md`、`Testing_Plan.md`
- M1 实现/测试：以用户本机仓库中的 `M1_Implementation_Report.md`、实际测试报告为准。

> **最终产品主线**：用户去 MiniMax 选择音色并复制 Voice ID → MakeSoundSkill 保存 Provider / Model / Voice ID 和项目别名/默认 → Agent 根据脚本编排情绪、停顿和必要语气词、多角色声音映射 → Python 根据已验证规则生成音频、句级字幕、缓存及可恢复任务。网页只在配置或问答时介入。
