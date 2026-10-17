# 聊天选声与已有工作流

本文件只处理主 Skill 的选项 1/2。`choices()` 返回项目音色菜单；选项 3 仅按主 Skill 和当前可用工具决定，无需先调用 choices()，选择后转到该应用的 native-audio 说明，不把内置工具伪装成项目厂商。用户选项 3 时不执行本文件的配置、候选入库和绑定接口。

## 两条入口

**帮我选声音**用于快速完成简单音频：Agent 推荐 → 所有候选入项目库 → 用户选择生成哪些试听 → 审阅及付费授权 → 分别播放 → 用户明确选定 → 保存最终绑定。默认每角色推荐 2～3 个有区别且合适的音色，最多 3 个，标明主选和备选及各自差异；任务简单或文案短不构成只给一个的理由。只有用户明确要求直接定一个，或核实后确实只有一个合适候选时，才只给一个；候选不足须说明原因，不编造或凑数。

**使用我的声音**用于已有工作流：已有项目绑定、明确指定音色或默认直接解析，不再要求推荐或打开网页。缺少厂商、区域、模型等必要信息时只补缺项；新 Voice ID 先通过 `core.add_voice` 加入项目库。信息歧义时不猜测。用户主动希望管理库时才启动 Studio；管理模式不创建假的绑定任务。

MiniMax `get_voice` 只按类型列出音色，不接受角色性格推荐条件。Agent 从官方目录/当前账号查询结果核实名称、ID 和描述后做推荐，明确区分厂商描述与自己的匹配理由。没有实时查询就不能宣称账号已验证可用。不爬取官网播放器，不编造 ID，不自动创建或克隆新音色。模型应来自用户当前配置，不能根据音色名称猜测模型。

## 先按实际配置选择厂商

用户已选择项目音色路径且需要确定厂商时，保留 **1、自己配置声音；2、推荐音色**。此时才读取本地安全配置摘要，不打印原始 JSON 或密钥：

- 仅一家已配置且已适配：推荐默认使用该厂商，保留自行绑定入口。模型优先使用该厂商有效 default_model；多个模型未设默认时请用户选择，不猜测。
- 两家均无可用配置：推荐下显示 **2.a、需要配置 MiniMax API Key（自动创建并打开配置文件）**。用户选择后调用配置入口；不要求把 API Key 发到聊天。
- 两家都已配置且都已适配：推荐下显示 **2.a MiniMax；2.b 火山引擎**，请用户选择。不能因为文件存在就推断应当使用哪家。
- 当前火山引擎未适配，因此暂不提供可执行推荐入口，即使其 JSON 已存在也不自动选用。配置齐全不等于已接入，也不等于线上鉴权成功。

API Key 占位符、空模型列表、错误 JSON、无效默认模型不算配置完成。配置打开后等待用户保存，随后重新读取摘要；打开编辑器本身不表示配置完成。已有文件只打开，不覆盖；API Key 仅由本机编辑器填写，不保存在项目任务、选声记录或日志中。

读取入口 `choices()` 只返回脱敏状态和菜单，不打开编辑器、不联网。使用返回的 options、default_provider 和 config_required，不自行以文件存在判定配置完成：

```text
python -X utf8 -c "import json; from makesound.voice_selection_entry import choices; print(json.dumps(choices(),ensure_ascii=False))"
```

确定厂商后才读取其访问说明。当前选择 MiniMax 时，转到 [MiniMax 配置与访问](minimax.md#本机配置与访问入口) 执行创建/打开配置、目录核实及生成；本文件不维护厂商专用调用。火山未适配，不读取其文档。打开配置文件不需要网页，因此不触发宿主文档读取。

## 数据与操作边界

使用 [通用接口配方 B](workflow-api.md#b-创建可恢复的绑定任务) 保存完整原稿 Question。候选不是最终角色绑定，候选试听不回答这个 Question，也不改变项目默认。每个角色的候选使用同一句原稿和相同基础参数；中文选句遵守主 Skill 的试听选句规则。比较用唯一句子 ID 与原句来源映射分开保存，不修改原稿。角色较多时逐角色准备试听，每个 Job 最多三个候选，因此不超过五段限制。

以下接口均位于 `makesound.voice_selection`，不联网、不生成音频、不授权付费。使用真实返回的 selection_id、project_voice_id 和路径，不手写 `.makesound` 状态。

### 1. 候选入库

`create(core, question_id, recommendations, revision)` 接收按角色 ID 分组的候选：

```json
{
  "r1": [
    {
      "name": "温润男声",
      "category": "male",
      "source": {
        "provider": "minimax", "region": "cn",
        "model": "speech-2.8-hd",
        "voice_id": "Chinese (Mandarin)_Gentleman"
      },
      "settings": {"speed": 1.0, "pitch": 0},
      "reason": "温润儒雅，适合文学爱好者；这是 Agent 的匹配判断",
      "evidence_url": "https://github.com/MiniMax-AI/skills/blob/main/skills/frontend-dev/references/minimax-voice-catalog.md"
    }
  ]
}
```

示例模型必须替换为实际已配置模型。category 是音色库分类，不是从角色名字推测出的性别；推荐请求已明确男声/女声时可沿用要求填 male/female，在 reason 标注“分类依据：请求要求”，不能称为厂商已核实。厂商目录/描述或用户已有分类也可作为依据；只有未知或特殊音色才用 other，不因缺少厂商 gender 字段而把明确的男声/女声请求统一归 other。若厂商信息或实际试听明显不符，应换推荐或核对，不硬贴分类。source 的四个字段与有效参数相同才复用已有活动项目声音；已有分类为 other 时可据上述依据补全，保留原 ID、试听和绑定。已有明确 male/female 不自动覆盖，有冲突先核对；不自动复活删除记录、不覆盖同名不同来源声音、不设置默认。

```text
python -X utf8 -c "import sys,json; from pathlib import Path; from makesound.core_v16 import ProjectCore; from makesound.voice_selection import create; data=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8-sig')); result=create(ProjectCore(sys.argv[1]),sys.argv[2],data,int(sys.argv[4])); print(json.dumps({'selection_id':result['selection_id'],'question_id':result['question_id'],'candidates':{r:[{k:c[k] for k in ('project_voice_id','name','category')} for c in cs] for r,cs in result['candidates'].items()}},ensure_ascii=False))" "<project>" "<question_id>" "<recommendations.json>" "<reviewed_revision>"
```

保存返回记录，向用户展示候选名称、ID、理由和候选的项目声音 ID。推荐记录包含来源链接，不代表代码已联网核实该来源。

### 2. 准备候选试听

`audition(core, selection_id, role_id, sentence_id, voice_ids=None, *, provider_directives=None, inline_controls=None)`：省略 voice_ids 表示该角色全部候选；传入用户选择的候选 project_voice_id 列表表示只准备这些声音。展示候选后明确提供“试听一个、部分或全部”，用户尚未选择范围时等待。用户已明确试听范围时不重复问；“推荐一下”不代表全部付费生成，准备请求不代表付费许可。

为本次选定原句准备 `<audition-performance.json>`：只含 `provider_directives` 和 `inline_controls`，例如 `{"provider_directives":{"emotion":"angry"},"inline_controls":[]}`。按原稿和角色演绎选择正式目标，仅使用所选厂商 reference 已支持的字段；适合自然表现时可用 `{"provider_directives":{},"inline_controls":[]}` 表示自动，不强制指定情绪，也不统一强制自动。同角色所有候选共用该文件及相同语速/声调；代码逐个校验模型能力，不能为某候选单独更换情绪来比较音色。不为准备这几句额外创建或确认整稿演绎单。

```text
python -X utf8 -c "import sys,json; from pathlib import Path; from makesound.core_v16 import ProjectCore; from makesound.voice_selection import audition; performance=json.loads(Path(sys.argv[6]).read_text(encoding='utf-8-sig')); print(json.dumps(audition(ProjectCore(sys.argv[1]),sys.argv[2],sys.argv[3],sys.argv[4],voice_ids=json.loads(sys.argv[5]),**performance),ensure_ascii=False))" "<project>" "<selection_id>" "<role_id>" "<original_sentence_id>" "null" "<audition-performance.json>"
```

读取返回 request_path 对应的直接生成请求，结合其原句映射展示逐候选试听单：角色、原句编号、声音名称/ID、完整原文、实际速度/声调、目标情绪（未指定则标自动）及发声控制位置，显示调用数、字符数与厂商/模型。保存此次返回的 review_hash。用户确认该具体内容后，调用 `freeze_audition(core, audition_id, review_hash, confirmed=True)`，内部复用 production.plan；冻结前重新检查候选参数、原文和审阅哈希，拒绝静默变更，固定输出 WAV。不可跳过此检查直接冻结旧 request_path：

audition 返回的 `chunks`、`characters` 为本次候选数和实际编译请求字符数（包含控制标签），直接汇总展示；不要让 Agent 手工逐字计数或擅加余量。冻结返回的同名字段用于最终核对，各 Job 使用各自范围，所有 Job 合计不得超出已获授权。

```text
python -X utf8 -c "import sys,json; from makesound.core_v16 import ProjectCore; from makesound.voice_selection import freeze_audition; print(json.dumps(freeze_audition(ProjectCore(sys.argv[1]),sys.argv[2],sys.argv[3],confirmed=True),ensure_ascii=False))" "<project>" "<audition_id>" "<displayed_review_hash>"
```

冻结后展示返回 Job ID 与实际调用/字符范围，按主 Skill 的授权规则和 MiniMax reference 的既有授权入口生成。若用户此前已明确授权相同内容和范围，沿用授权，不重复询问。每个候选独立展示完整音频；生成结果自动复制进项目库试听，不调用额外 TTS，也不裁成十秒。合并播放不能替代独立试听。

生成后仅需取试听结果时执行下列只读入口一次；即使 run 返回 `export_incomplete / subtitle_unavailable`，音频也可能全部成功：

```text
python -X utf8 -c "import sys,json; from makesound.core_v16 import ProjectCore; from makesound.voice_selection import audition_results; print(json.dumps(audition_results(ProjectCore(sys.argv[1]),sys.argv[2]),ensure_ascii=False))" "<project>" "<audition_id>"
```

`audition_results` 校验任务映射、冻结快照、成功状态、音频哈希和时长，直接返回候选名称/ID、原句、逐条音频路径与字幕状态；不联网、不合成、不依赖 SRT 导出成功。`audio_ready` 就按交付规范的 `publish-audition` 入口交付；需要可读副本时可直接调用它代替先调用 `audition_results`，内部完成相同核验，避免重复读取或手写复制脚本。不手抄缓存哈希、不逐层 ls 或反复读取 snapshot/state。`partial` 只报告并保留已成功部分，失败项按实际状态处理；`billing_unknown` 不自动重试。字幕缺失时选声继续，不依次尝试 export→repair-audio→retry-subtitles；正式需要字幕时才读厂商恢复说明。链接只列一套，不在同一回复的交付清单再复制一遍。

试听成功不自动最终绑定。失败保留成功结果与库中候选；费用状态不明不盲目重试。候选被编辑或删除、原稿变化时重新核对，不能把旧试听冒充新参数的效果。

### 3. 最终绑定

用户明确说出最终声音后，整理**所有任务角色**的最终 project_voice_id 映射，包括此前已明确指定的项目声音；只对用户未确定的角色继续询问。`bind(core, selection_id, assignments, revision, confirmed=True)` 记录真实聊天选择并提交原 Question，不宣称用户点过网页。未确认不能传 confirmed=True；试听授权不能替代选声确认。

```text
python -X utf8 -c "import sys,json; from pathlib import Path; from makesound.core_v16 import ProjectCore; from makesound.voice_selection import bind; data=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8-sig')); result=bind(ProjectCore(sys.argv[1]),sys.argv[2],data,int(sys.argv[4]),confirmed=True); result['answer']['resolved']={r:{k:v for k,v in voice.items() if k!='capability_validation'} for r,voice in result['answer']['resolved'].items()}; print(json.dumps(result,ensure_ascii=False))" "<project>" "<selection_id>" "<assignments.json>" "<reviewed_revision>"
```

revision 使用选定时最近读取的项目版本；试听自动保存也可能增加版本。冲突后读取并核对用户选择，不以最新版本悄悄覆盖改变的配置。

没有推荐过程的“使用我的声音”，可在配方 B 后调用 `Questions(core).submit(question_id, assignments, revision=reviewed_revision, replace_assignments=True)` 保存全部已明确的选择；此参数用本次确认替换网页曾暂选的旧草稿，保留普通网页提交的快照规则。默认使用已确认的 `{"default_slot":"general"}` 等契约。不要为使用此入口额外制造推荐记录。已有 answered Question 且没有更改意图时直接沿用，不重复提交；需要换声/改参则按修订契约创建新版本，不能继续对旧 selection 调用 bind；未确定的声音不能通过 None 静默回退。

`assignments` 必须覆盖本任务全部角色，明确声音的值是项目声音 ID **字符串**，不是厂商 Voice ID 或包装对象。例如用户明确确认三角色声音后，文件内容为 `{"r1":"pv_a","r2":"pv_b","r3":"pv_c"}`；使用默认时对应值才是 `{"default_slot":"general"}`（或 male/female）。这些 ID 均替换为真实查询结果，未明确选择不能靠示例猜测。

绑定返回的 Answer 已含当前确认快照时直接沿用，不为配方 C 再读一次。完成候选试听并选定后，不新增固定的“绑定后首轮试听”关卡；先确定最终演绎目标并核对下面的复用清单，再按 [通用接口配方 D](workflow-api.md) 为未完成或演绎已变的原句提出生成单。

### 4. 核对已选试听并生成剩余内容

```text
python -X utf8 -c "import sys,json; from pathlib import Path; from makesound.core_v16 import ProjectCore; from makesound.voice_selection import reuse_report; targets=json.loads(Path(sys.argv[4]).read_text(encoding='utf-8-sig')); print(json.dumps(reuse_report(ProjectCore(sys.argv[1]),sys.argv[2],question_id=sys.argv[3],targets=targets),ensure_ascii=False))" "<project>" "<selection_id>" "<current-answered-question_id>" "<final-performance-targets.json>"
```

`<final-performance-targets.json>` 覆盖完整原稿句 ID，每项包含目标 `provider_directives`、`inline_controls`，例如 `{"S1":{"provider_directives":{"emotion":"angry"},"inline_controls":[]},"S2":{"provider_directives":{},"inline_controls":[]}}`，只写实际目标，不照抄试听值来制造复用。语速、声调、音色、模型使用当前已提交绑定快照；需改这些值先按改绑流程确认。

`reuse_report` 不联网、不生成、不修改计划或绑定。它检查当前项目的候选试听记录，按当前已提交 Answer、原文映射、完整最终情绪/发声控制目标筛选，并校验冻结快照、音频哈希和时长，返回 `reusable`、`remaining_sentence_ids` 和 `performance_checked=true`。缺失、损坏或参数不匹配的音频不会列为可复用。未传 targets 的旧调用只返回已有音频清单，标记 `performance_checked=false`，不能据此直接断言无需重生成。改绑后传实际已提交的新 Question；未保存的网页草稿不能用于判断。清单不代表付费授权。

情绪或发声控制与最终目标不同，重新生成是合理的：包括从自动改为指定情绪、指定情绪之间变化、增加或删除发声动作。列明旧→新差异和新增调用，随最终演绎单审阅，不强迫沿用 auto，也不为这一步另加重复确认。新付费单只含核对后的 `remaining_sentence_ids`；参数一致的已认可音频才复用，不因换 Job/句子 ID 假定缓存一定命中。段后停顿通过本地拼接处理，不能为停顿变化调用厂商；已有追加静音按可信元数据处理，不裁掉原始语音。复用片段和新片段按完整原稿顺序交付。

示例：十句中已选试听覆盖 S1/S4/S6，三句最终参数均一致时复用三句、只生成其余七句；若其中一条情绪改变，则复用两句、生成八句；三条均改变则生成十句。未选候选试听仍留库。完整交付总览区分“复用”与“新生成”，调用预算按核对后的实际新生成范围计算。音频符合目标但字幕缺失时，仅修复字幕或报告缺失，不为字幕重新合成，不承诺未验证的修复成功。

未选中的候选及试听继续保留在项目库，用户可在以后启动 Studio 管理模式时反复播放。页面服务关闭后，磁盘音频仍保留；网页播放需要重新启动服务，不要求重新合成。
