# MakeSoundSkill V1.2 测试计划与 Schema 草图

日期：2026-10-14（Asia/Shanghai）。**M1 已实现并完成 49 项离线测试（40 unit + 9 integration，全部 PASS）；实际记录见 [M1_Implementation_Report.md](M1_Implementation_Report.md) 与 [M1_Test_Results.json](M1_Test_Results.json)。M2–M4 及真实平台 Agent 闭环仍 NOT RUN。M1 完成后停止。**

**最新产品确认**：V1.2 只验收 Codex 与 Claude Code；核心 Harness-Agnostic。Kimi Work、DSH、WorkBuddy、豆包均只保留调研，不开发 Adapter，不作为本版交付门槛。kimi_work 与 kimi_code 的历史区分仍保留以免未来混用。Adapter 设计见 [Harness_Adapter_Design.md](Harness_Adapter_Design.md)，阶段安排见 [Platform_Integration_Plan.md](Platform_Integration_Plan.md)。

## 1. 基线与阶段门槛

- V1.2 为主；后补 V1.1 已阅读，其 §11.3 旧 Preset 和 §12.1 源文范围作为兼容基线。Session Preference、Voice Design 暂缓、旧分期/CLI 冲突项按 V1.2 取代；文档基线已齐，迁移实现与验证仍 NOT RUN。
- 用户确认区域作为配置项、接受设计与试听一次调用、属性不明人工选声、等待超时后持久领取。用户补设后本轮复查 region=cn、Base URL 归类国内且一致；仍需实现校验，不把声明配置当成账号认证；本轮不修改凭据。
- 当前 Python 3.13.10、FFmpeg/ffprobe 8.1.2 可执行；3.11 环境未安装验证，安装和依赖变更不在本阶段。
- M1–M3 使用临时目录、Fake Provider 与本地 fixture，不读取真实 MiniMax Key；测试进程禁止外部网络，所有潜在付费入口用“未被调用”断言守住。
- 真 Key 仅供未来显式授权的 M4 使用。配置只读，错误输出脱敏；未知端点禁止猜测。新音色设计仍为 MUST，不能静默降级为 LATER。
- 单元测试与集成测试分别报告；通过 Fake 测试不证明真实声学质量、账单或账号权限。

## 2. M1：数据作用域、CLI 与持久化（离线 PASS）

本节测试目标已由真实单元/CLI 子进程测试覆盖，范围细分见 M1 报告；涉及 Studio 真网页、完整生成 resume 和宿主模型对话的部分仍留后续阶段。执行命令为 `python -m unittest discover -s tests -t . -q`；本机无 pytest，未安装第三方测试依赖。

| 用例 | 操作与验收 | 对应 |
|---|---|---|
| CFG-01/02 | 无默认必须 needs_setup；直接存项目默认但不命名，named_voices 保持空；内置建议不能自动成默认 | AT-01/02/11 |
| CFG-03/04 | A/B 项目同名允许；同项目重名需显式确认，确认绑定原 revision 与旧/新引用，过期确认不能覆盖 | AT-03/16 |
| CFG-05 | A→B 重绑定后新任务解析 B，历史快照仍为 A | AT-05 |
| CFG-06/07 | 稳定 asset ID、全局显示名唯一；删除原样本不删 Provider ID/项目引用/历史；资产删除先查引用 | AT-04/06 |
| CFG-08/09/10 | female 硬约束不回退 male；unknown 不冒充 female；缺别名打开修复；网页明确取消筛选并提交后以此为准 | AT-08/09/10 |
| CFG-11 | 声音字段与导出/SRT 独立合并；只有明确勾选保存才持久化；不存在 Session Preference | AT-02/11 |
| CFG-17 | 非 Git、中文路径、可信显式项目根、无根、只读根；禁止落到 HOME/System32 或其他项目 | AT-16 |
| CFG-18 | 按 V1.1 §11.3 旧格式只读解析；声音迁入 default_voice，导出/脚本/停顿迁入 project_settings；模型与未知字段不丢失；显式迁移有备份及回滚；区域不足需补配置，不默认为 cn | 兼容基线 |
| REGION-01 | region 显式配置及覆盖、旧文件无 region、地区/URL 冲突、无声切区禁止；快照冻结具体区域，doctor 不调用收费 API | 区域可配置 |
| IO-01 | 原子写失败、磁盘满、锁竞争、进程中断、schema 不兼容、两项目/两进程并发，无半文件/丢更新 | AT-16/17 |
| CLI-01 | stdout 单一可解析 JSON，stderr 诊断；非零错误码；凭据/敏感 URL/原录音不泄露 | AT-17 |

建议验证 Unicode NFC 规范化、显示名去空白和项目内唯一性策略；这些规范目前是 Proposed，需要形成明确 Schema 后才能编写验收。

## 3. M2：文稿、Chunk、音频与字幕（NOT RUN）

| 用例 | 操作与验收 | 对应 |
|---|---|---|
| SCRIPT-01 | narration_only/verbatim/明确授权 rewrite；保留术语、日期、数字；歧义 needs_review；removed_items、源文哈希及映射可审计 | AT-14 |
| CFG-12/13 | 段间/句内多声音，按实际 provider+region+voice_id+兼容参数切分；稳定段句/span ID 和顺序，单请求不跨声 | AT-12 |
| EXPORT-01 | whole/paragraph/sentence，默认 paragraph；句内多个 Chunk 正确组成一个句级产物 | AT-13 |
| SUB-01 | Fake 返回真实结构的人工时间戳 fixture；独立导出时间轴以零为原点；不按字数估算；超界/倒序/空文本/控制符拒绝 | AT-13 |
| AUDIO-01 | 用本地可确定采样数 WAV fixture 验证拼接、静音策略、采样率转换及取整；模拟 MP3 编码延迟并检查真实解码采样数 | AT-13 |
| CFG-14 | 字幕缺失、过期下载、损坏、时间单位不明→subtitle_failed，保留音频、不可 completed；只能用户明确关闭字幕 | AT-13/18 |
| CACHE-01 | 模型、Provider、区域、ID、文本、全部有效参数或字幕契约变动导致缓存失配；别名仅审计，快照不再解析别名 | AT-05/18 |
| RESUME-01 | Chunk 成功后进程退出再恢复，成功缓存不重合成；仅重做失败后处理；局部重生重建受影响 Chunk 和产物 | AT-18 |
| AMBIG-01 | 发送后超时标 billing_unknown；不自动重试未知扣费请求；Fake 断言不会重复调用 | AT-18 |

字幕 fixture 的时间只证明拼接计算正确，不能证明 MiniMax 对齐准确。API 句界可能不等于源文句界：映射不可靠则失败或 needs_review；不得擅自引入 ASR。首 cue 不必强行归零，应保留实际首字延迟。以上处理建议仍待用户确认。

## 4. M3：Studio 与 Harness 问答（NOT RUN）

| 用例 | 操作与验收 | 对应 |
|---|---|---|
| START-01 | Windows 真后台服务，127.0.0.1 随机端口；返回 URL 经本机浏览器可达后才 ready；端口占用/进程退出正确报错 | AT-01/15 |
| ANSWER-01 / CFG-15 | applied/cancelled/expired；提交含 question/job/project/revision；重复 answer 幂等；两浏览器竞争不能最后写入覆盖 | AT-15/16 |
| WAIT-01 / CFG-16 | CLI 等待时提交返回；等待器超时但问题 TTL 未过，迟到回答仍可保存和领取；TTL 过期拒绝提交 | AT-15 |
| RESTART-01 | 关闭浏览器不撤销已提交答案；杀 wait、重启服务、重启 Harness 后 answer get/jobs resume 可领取；断在 claim 后可恢复 | AT-15/18 |
| INTENT-01 | 应用本次、设项目默认、添加命名库三项独立；无需命名即可默认；保存默认不自动合成；多处写入失败不谎报成功 | AT-02/03 |
| ISOLATE-01 | 两项目/两 Job/两问题交叉提交失败；Origin/CSRF/随机令牌/TTL/路径限制；令牌不进查询参数和公共日志 | AT-16/17 |
| HARNESS-01 | Codex 实际调用 wait 后继续；具体 session ID 恢复；终止后网页只说已保存待领取；不能以 --last 混投其他任务 | AT-15 |
| HARNESS-02 | Claude Code 读取同一项目别名/默认、同一 CLI 契约；明确 session 与 job 关联，不继承声音会话偏好 | AT-20 |
| RESUME-BUTTON-01 | 等待超时后按钮提交同一 Job 恢复意图；双击/刷新/网络重发只领取一次、只调度一次；running 返回现有状态，completed 返回已有结果，billing_unknown 不重发 | 用户补充 |
| RESUME-BUTTON-02 | 有桥接时准确投递目标 Harness 会话且展示真实接管状态；无桥接时复制继续指令并由用户在原聊天发送；问题过期需重新确认，保存默认不会升级为生成授权 | AT-15/17/18 |
| NO-COST-01 | 网页未提交、needs_review、取消、超时、别名缺失、仅编辑设置均为零收费调用；重放回答不重复调度 | AT-01/17/18 |

本机浏览器测试和进程中断需实际执行，静态页面、仅 HTTP 200 或 CLI help 不能代替通过。跨 Harness 测试如需模型推理额度，应先明确测试范围；Fake Provider 只能保证没有 MiniMax 费用。

## 5. M4：真实 Provider 受控验收（NOT RUN，须另行明确授权）

在发出请求前提供动作、区域、模型、最大请求数、预算上限、输入/录音第三方传输范围和重试策略。原录音授权与一般生成授权分开；声音创建的授权不自动等于所有后续 TTS 授权。

| 测试 | 最小建议样本/成功条件 | 计费/风险门槛 |
|---|---|---|
| RO-01 | 确认当前区和 Base URL 后一次官方音色列表查询，记录脱敏字段与业务状态 | 需先确认该只读查询无收费；不以 TTS 替代连通性；不自动换域名或换区 |
| TTS-01 | 一条短句、非流式、显式 sentence 字幕；保存真实返回形状、字幕单位、解码时长、人工听检 | 预授权一次 TTS；测试 ID/文本必须事先确定，不预填假 ID |
| CLONE-01 | 一次授权样本上传+一次克隆；记录请求 ID、生命周期、保留样本；后续一次 ID 复用不再上传 | 上传是远端写入；试听/首次正式使用/音色费可能累加；不自动重建 |
| DESIGN-01 | 一次 prompt+preview_text 设计；本地登记 ID；另行预算一次复用验证 | 必填试听会收费；记录账户是否开放、区域、实际账单与返回；不虚构第二创建接口 |
| MIX-01 | 两个已授权可用 Voice ID，各一短 Chunk，验证顺序、真实时长及字幕 offset | 预授权最多两次 TTS；新增创建不在此项授权范围 |
| FAIL-01 | 优先离线故障注入；真实请求只观察自然失败 | 不为压测故意制造大量收费/429；超时不盲重试 |
| LIFE-01 | 已有音色的后续可见性与复用记录；官方澄清 design 有效期 | 长期行为不能一次调用就判 PASS；不为保活自动付费 |

上述是候选请求数，尚非用户批准的预算，必须避免重叠测试重复计费。国内当前公开音色费及试听费见 [官方价格](https://platform.minimax.cn/docs/pricing/overview)；实际预算须在 M4 前重新核对区域、字符计量、最小扣费单位及账号规则。

## 6. Schema 草图（Proposed，未实现）

### 6.1 结构、作用域和不变量

| 对象 | 必需字段草图 | 不变量/验证 |
|---|---|---|
| GlobalVoiceRegistry | schema_version、revision、assets[] | 全局 asset_id 与规范化 display_name 唯一；只有 clone/design；官方音色不强行登记成创建资产 |
| VoiceAsset | asset_id、display_name、source_type、provider、region、voice_id、created_at、availability、metadata、sample、consent | sample 本地删除不改 voice_id；设计 prompt 也可能敏感，限制访问；元数据记录来源与核验时间 |
| VoiceReference | kind=global_asset 或 provider_voice | 使用 oneOf：前者 asset_id，后者 provider+region+voice_id；不能两套同时生效；配置内 `configured` 在快照中必须解析为具体区 |
| ProjectPreset | schema_version、project_id、revision、project_settings、default_voice、named_voices | default_voice 可直接引用，不要求 alias；named_voices 只在本项目唯一；写入需可信根和 revision 检测 |
| GlobalDefault | schema_version、revision、default_voice、project_settings | 与创建资产库分离；只按用户明确保存更新 |
| ScriptManifest | schema_version、document_id、source、source_hash、paragraphs、voice_assignments、removed_items | 段/句/span 稳定 ID、范围及覆盖率；V1.1 §12.1 Unicode 字符 [start,end)，无法定位则 null+哈希，须覆盖 UTF-16 转换 |
| ProviderConfig | provider、region、base_url 来源、credential_path 引用 | 草图；区域不能写死；Key 不复制；显式覆盖可追溯，地区/URL 冲突禁止调用，doctor 只读 |
| JobSnapshot | schema_version、job_id、project_id、created_at、source_hash、chunks、export_plan、effective_settings、authorization_ref | 冻结实际 Provider/region/ID/参数与文本；resume 不重解析别名；不得含 Key |
| StudioQuestion | schema_version、question_id、studio_session_id、job_id、project_id、purpose、requested_fields、filters、expected_revision、expires_at、status | 无声音 Session Preference；令牌另存、只保存校验材料；wait 超时不等于问题 expired |
| StudioAnswer | answer_id、question_id、project_id、job_id、submitted_at、selection、save_intents、expected_revision、status | 不可变回答、唯一幂等键、原子 claim；不同项目/Job 拒绝；迟到但未过 TTL 可以领取 |
| ChunkResult | chunk_id、request_fingerprint、provider_request_id、audio、subtitle、status、billing_status | 文件存在/哈希/解码与字幕校验才能成功；unknown 计费单列，不能安全地盲重试 |
| ResumeIntent | resume_intent_id、job_id、question_id、answer_id、snapshot_hash（若已有）、target_platform、可选 native_session_ref、status、lease | 草图；重发同一意图幂等；校验项目、Job、快照和授权；原 target_harness_id 含义拆清为平台与可选宿主会话；accepted 不等于 running，桥接不可用仍保留待领取 |

建议业务 Schema `additionalProperties:false`，明确可选/null/默认及枚举；Provider metadata 单独命名空间，不能无校验透传。ID 用字符串；内部时间用整数毫秒或采样点，换算留原始单位，读取外部时间单位不明则拒绝。

### 6.2 项目配置示例（仅草图、不是请求）

```json
{
  "schema_version": "1.2",
  "project_id": "example-project",
  "revision": 1,
  "project_settings": {
    "export_mode": "paragraph",
    "subtitle_enabled": true,
    "subtitle_type": "sentence",
    "script_processing": "narration_only",
    "audio_format": "mp3"
  },
  "default_voice": {
    "ref": {
      "kind": "provider_voice",
      "provider": "minimax",
      "region": "cn",
      "voice_id": "EXAMPLE_NOT_A_REAL_VOICE"
    },
    "voice_settings": {"speed": 1.0, "volume": 1.0, "pitch": 0, "emotion": "auto"}
  },
  "named_voices": {}
}
```

例子明确展示不命名也能设默认；占位 ID 不能作为有效声音或发送给 Provider。auto 仅是本地省略 emotion 的语义。优先级为已提交 Studio > 明确别名 > 项目默认 > 全局默认；描述硬条件、别名缺失和冲突先阻断；本次字段覆盖独立应用。没有 Session Preference 层。

### 6.3 任务与回答状态

- Job 主状态沿 V1.2：created → config_resolving → ready/needs_studio/invalid → script_preparing → needs_review/ready_to_generate → generating → postprocessing → completed/partial_failed/failed。
- 问题独立状态：pending_answer → applied/cancelled/expired；wait_timeout 为 CLI 返回原因，不是问题终态。
- 字幕作为独立子状态 pending/completed/subtitle_failed；字幕失败时顶层 partial_failed，音频保留。PRD 同时提到 subtitle_failed 与主状态枚举，需明确此层级，不能让两个状态字段互相覆盖。
- availability 建议 unknown/pending_activation/available/unavailable/expired；记录证据与 last_checked_at；未在列表中不自动标 unavailable。
- 收费发送前持久记录 attempt_id/request_fingerprint 和授权；成功结果落盘后更新完成。崩溃发生在“远端已接受、本地未记录”之间时标 billing_unknown，需用户处理或有可靠 Provider 幂等证明才重试。

## 7. 验证命令与交付标准

以下命令分阶段运行：M1 的 doctor/config resolve 和离线单元/集成测试已执行（使用 stdlib unittest）；Studio 尚未实现、对应命令 NOT RUN。现在可直接在仓库运行 python -m makesound，无需联网安装。

```powershell
python -m makesound doctor --json
python -m makesound config resolve --project (Get-Location).Path --json
python -m unittest discover -s tests -t . -q
python -m makesound studio start --project (Get-Location).Path --purpose setup --json
# wait/answer get/jobs resume 使用 start/status 实际返回的 ID，不手写 URL/端口。
```

每项测试记录：用例 ID、环境版本、Provider fake/real、输入 fixture 哈希、预期、实际、PASS/FAIL/BLOCKED/NOT RUN、调用数与费用是否未知、必要脱敏证据。真实音色 ID/样本路径按需保存在用户私有测试记录，公开报告不泄露敏感素材。

M1 离线门槛已通过，局限见实现报告。M2 门槛：多声音与三导出、真实采样时间轴、失败续跑。M3 门槛：真网页端到端，Codex/Claude Code 分别记录真实验收，不能以静态页面或本次 CLI 子进程测试替代。M4 门槛：授权范围内的实际 API/字幕/计费证据，长期项允许显式 NOT RUN，不能假报 AT-19 完成。

本轮完成 M1 核心实现与离线测试后停止，不自动进入 M2；真实 Studio 与自动投递桥接仍 NOT RUN。完整历史决策见 [M0_Discovery_Report.md](M0_Discovery_Report.md)，当前代码结果见 [M1_Implementation_Report.md](M1_Implementation_Report.md)。

## 8. 新增平台的调查与后续验收计划

以下是未来平台扩展的存档计划，**全部 NOT RUN，且不属于 V1.2 两平台验收范围**。保留 Kimi Work、DSH、WorkBuddy、豆包的调研与身份区分，不实现 Adapter、不安装插件/启动模型。若未来重新授权执行 KW，仍须真实 Windows 客户端和 Fake Provider，不从 Kimi Code CLI 推导超时、Shell 或 Session 规则。

| 用例 | 平台/测试 | 验收标准或阻碍 |
|---|---|---|
| PLATFORM-01 | 产品与版本识别 | 目标是普通 Kimi Desktop 的 Work 模式，区别于 Kimi Code Desktop/CLI、网页版 Chat；WorkBuddy/CodeBuddy、豆包/扣子/TRAE、DSH/第三方 CLI 分开；记录版本/运行位置/权限。当前仅早先元数据已查 |
| KW-01 | 识别实际 Windows 客户端版本、Work 模式及授权设置 | 记录应用版本与现有审批模式；不得以开始菜单名字证明 Work 可用，不自动改权限 |
| KW-02 | 在 Kimi Work 导入 MakeSoundSkill，验证触发 | 记录实际接受的本地包格式、安装与脚本资源路径，验证读取 SKILL.md 和显式/自然语言触发；不套用 Kimi Code 的目录规则 |
| KW-03 | 通过 Skill 执行本机 Python CLI | 使用 Fake Provider/假 ID/临时数据，不读真实 Key；确认系统解释器、中文/空格路径、JSON stdout 与退出码；MiniMax 业务调用为零 |
| KW-04 | 可信项目目录与音色库 | 明确授权的 A/B 项目配置解析正确，根目录来源可审计；无根/只读/越界阻止项目写入；不以任意 cwd/HOME 替代 |
| KW-05 | 启动真实 Voice Studio | 在本机实际启动并返回真实 127.0.0.1 URL；浏览器可打开且 Question/Job 正确关联；仅有浏览器工具文档不算通过 |
| KW-06 | 网页提交后等待中的 Agent 继续 | 先采用有界短轮询，记录桌面实际等待/超时/进程行为；回答使 CLI 返回并继续同 Job；不继承 Kimi Code 的 60s/5min/Session 规则，无重复等待器或重复 Fake 调用 |
| KW-07 | 等待结束后用户再发继续指令 | 等待器结束而问题仍有效时提交并持久化；用户发送含真实 job_id 的继续指令领取同一 Answer/Job；重复继续幂等，问题过期需处理；不自动给原聊天发消息 |
| KW-08 | 两项目、两任务并发隔离 | Job/Question/Answer/ResumeIntent 隔离；交叉提交被拒，双击只应用一次；别名变更不污染历史快照 |
| KW-09 | 权限审批模式 | 按真实客户端审批测试 CLI 与文件写入的允许/拒绝/取消；失败不写其他目录、不虚报成功、不切换全权限；敏感值不进宿主输出 |
| KW-10 | 正式恢复/消息桥接能力核查 | 仅核查可验证的官方协议与版本适用性，本阶段不发自动消息；无证据则保留“回答持久化 + 用户发继续指令”，不得把手动 Job 恢复说成原生 session 恢复 |
| WB-01 | WorkBuddy 本地 Skill 导入与授权范围 | 本地 CLI 执行 doctor/config resolve/Fake Job；明确受控目录权限与 Python 来源；禁止自动开完全访问或全局安装 |
| WB-02 | 等待与手动继续 | 无已证实等待上限时先测短 wait；超时/重启后原任务读取持久回答；浏览器关闭、双击、两个项目不串线 |
| WB-03 | 官方本地助理 Open API 可选桥接 | 另行配置开发者应用/OAuth，最小 user.localassistant.readable/invokable；确认 online 与正确任务关联；text 或 permission_response 的 requestId 必须来自真实请求，不能直接套 MakeSound question_id |
| WB-04 | 正式连接器包装评估 | 对照市场 CLI+Skill 的 runtime/跨平台/auth/status/unAuth 要求；长期 Token 模式按 MCP 规则评估；不能为了上架改写只读 MiniMax 凭据。Windows 本地试用通过不等于市场通过 |
| DOUBAO-01 | 豆包桌面实际能力辨识 | 记录办公任务/执行环境、能否读取用户授权的临时宿主目录、运行无联网 CLI、访问宿主 loopback；GUI 操作能力不代替稳定 Skill/CLI 证据 |
| DOUBAO-02 | 豆包网页版环境与边界 | 区分云沙箱/本机；未有正式本机连接就不能访问本机配置或伪造可达 URL；不自动开公网服务/隧道 |
| DOUBAO-03 | 扩展与恢复入口核验 | 需官方协议或实机证据证明自有 Skill 安装、原任务继续与消息投递；不足则标 BLOCKED/NOT RUN，提供人工移交，不宣称原生支持 |
| DSH-01 | 固定版本/profile/工具组合 | 记录发布版本/提交、profile、Skills provider、Bash 或 pwsh 执行后端；Node 可用不等于 DSH 已安装；先确认安全 sandbox 与工作目录 |
| DSH-02 | headless --session-id 与 JSONL | 用真实持久 session ID+Fake Job 恢复，未知 ID明确失败；校验 stdout JSONL、stderr，不能虚构通用 dsh resume；不执行配置 dump 当纯只读（可能初始化 profile） |
| DSH-03 | 进程等待、SDK/ACP 和网页 | 检查前台超时/后台通知/重启、SDK 精确 session 投递、Studio 问题关联；DSH Web UI 与 Studio 独立，SDK 可用不等于桥接已接通 |
| XH-01 | V1.2 两平台持久化一致 | Codex/Claude Code 复用相同 Core、项目库和快照；Question/Answer/ResumeIntent/成功 Chunk 恢复待 M2/M3；Kimi Work/DSH 如未来扩展也复用，不纳入当前实现 |
| XH-02 | “继续任务”跨平台统一语义 | 一次点击对应同一 Job 的幂等恢复意图；无桥接复制指令，有桥接需实测接管；已完成直接返回，billing_unknown 不盲重发 |

WB/DOUBAO 用例保留为调研后的候选验收，不计首批门槛；本轮均 NOT RUN。未来 CLI 的无推理版本检查仅在已发现明确可执行文件后运行 --version/--help；Kimi Work 版本按真实桌面界面核验，不要求安装 Kimi Code CLI。不要以 npx 自动拉取 DSH 或临时安装 Kimi。任何平台模型任务可能消耗宿主额度，即使 MiniMax 使用 Fake，也与本机离线测试分别记录。本轮仅修订文档，未授权执行 KW 桌面闭环或插件安装。

保留的 HarnessAdapter 能力草图允许 unknown，未来 kimi_work/kimi_code 分开；不在当前 M1 创建这些平台 Adapter。KW-01 至 KW-10 为延期存档，不是当前验收义务或完成证明。V1.2 仅 Codex/Claude Code，核心不绑定宿主 SDK。

官方依据及当前限制见 [Capability_Matrix.md](Capability_Matrix.md) §6、[M0_Discovery_Report.md](M0_Discovery_Report.md) §11。平台文档以 2026-10-14 调查为准；DSH master 和在线产品持续变化，实际验收必须记录安装版本与适用文档，不能用本次调查永久保证兼容。
