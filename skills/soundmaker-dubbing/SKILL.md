---
name: soundmaker-dubbing
description: Plan and produce dubbing for a supplied script with SoundMaker. Use when the user asks to generate voice audio, narration, dialogue dubbing, or a spoken soundtrack, or revise/regenerate part of an existing dubbing task.
---

# SoundMaker Dubbing

Use this Skill when the user asks to generate dubbing or revise an existing dubbing task. For a targeted revision, go directly to references/revision-and-recovery.md instead of restarting role analysis. Do not use it for ordinary writing, discussing characters, or managing a voice library without a dubbing request.

## Runtime and target project

This skill is linked into supported local agent hosts from the SoundMaker repository. Resolve the skill directory link before locating the runtime: the repository root is two directories above this skill folder (`skills/soundmaker-dubbing`). Use that resolved repository as the runtime working directory; do not assume a personal checkout path. If the host imported a copy instead of a link, locate the actual runtime repository before executing commands.

Run `python -m makesound...` with the SoundMaker repository as the command working directory, while passing `--project` as the user's CURRENT project absolute path. For Python API calls, instantiate ProjectCore with that same target project. Never substitute the runtime repository for a newly opened user project. Outputs, defaults, voices and task records belong to the target project; do not copy this repository's test voices, defaults or previous jobs into it. A new project may need voice binding/configuration. Reuse the user's provider configuration without exposing credentials. The user should not need to configure launch commands manually.

## 0. 先确定试听阶段与本地音频能力（所有应用共用）

新配音任务必须先做角色音色试听：**角色分析与绑定 → 每个角色选一句 → 展示并确认首轮试听单与付费范围 → 交付各角色独立 WAV → 用户确认音色 → 审阅、授权剩余对白 → 分批生成与最终合并**。绑定完成只表示选好了声音，不表示用户已试听或认可实际听感。不得从绑定直接跳到整稿生成。

例如三个人六句对白：首轮只选三句，每个角色一句，分别交付三个可播放音频；用户确认这三个声音后，才处理其余三句。完整剧本可以先展示供审阅，但不能因此把全部六句作为首轮试听单或首个生成 Job。角色选句以本节规则为准，不机械取前 N 句。

中文对白以至少 **20 个有效文字**作为建议选句下限（不计标点、空格和控制标签；这是试听经验规则，不是厂商限制，也不保证固定时长）。按该角色的原文顺序检查：第一句达到下限就选第一句；不足则检查第二句，依次选择最早达到下限的一句。如果该角色所有句子都不足 20 字，选择有效文字最多的一句；并列时取最早出现的。只有一句就使用该句，不凑字、不擅自改写或拼接。其他语言按足够判断音色的完整自然对白选择，不机械套用中文字符数。向用户注明选取的原句编号以及短句回退情况。

按角色首次出场顺序，每批最多五个不同角色，每个角色仅一句；角色很少时不凑满五段。超过五个角色时继续下一组，直到所有角色均试听。保留原句 ID。完整 Question 不能提交局部演绎单：先完成声音绑定，再基于保存的绑定快照为选中原句建立对应小批 manifest/Question，或使用已验证的直接请求路径；不得伪造网页 Answer，也不得为满足整单校验而把未试听角色的剩余句子全部生成。

**音频依赖应在展示生成授权范围之前检查**：从运行时仓库执行 `python -m makesound.media`，不读取密钥、不调用厂商、不下载。优先复用 PATH 或当前用户 WinGet 目录中已有的 FFmpeg/FFprobe；路径未找到不等于系统没有安装，也不代表应用不能处理音频。返回 `wav_only` 时使用已校验的单声道 16-bit PCM WAV；相同采样率的 WAV 保存、时长检查、追加静音、拼接和 SRT 导出可在本地完成。不得因缺失工具自动下载安装、长时间寻找下载源或修改全局 PATH。MP3 编码和重采样仍需要外部工具；缺失时说明限制，在冻结 Job 前明确改用 WAV。已冻结任务不静默改变输出格式。

用户明确要求执行一份完整外部演绎单，或已试听并明确要求直接生成全部时，按其明确范围执行，不重复增加试听关卡；“完成绑定”“确认剧本”或普通“生成配音”不能当作跳过首轮音色试听的指令。

## 1. Identify roles and report the required format

Read the manuscript without silently rewriting it. Return a role analysis before binding voices, using this format for every speaking role:

```markdown
## 角色分析

### 主角 1：<角色名>
- 性格/演绎特征：<基于原文的简短描述>
- 推荐声音：<声线特征或可用项目声音>
- 当前绑定：<项目声音名称和 Voice ID，或“待用户绑定”>
- 绑定方式：<明确指定 / 默认解析 / 待 Studio 补齐>
```

Distinguish facts from recommendations. Do not infer gender from a name; use only user or task-provided requirements.

## 2. Resolve voices before opening Studio

If the user explicitly requests a project default or a named project voice, check that it exists, is not deleted, resolves for this project, and has an available provider/model configuration. If it is usable, bind it directly and do not open Studio.

If every required role is resolved, continue without Studio. Otherwise, the agent must create a Question, start the project’s persistent Voice Studio service for that exact Question, and open its returned local URL for the user. Do not ask the user to run a terminal command, choose a port, or supply a Question ID.

The user’s only Studio action is to bind each role, speed, and pitch, then save the Answer. Keep the service available while the user works and resume from that immutable saved Answer. Studio is for binding only; it does not create a performance plan or call a provider. If the agent runtime cannot retain a local service, treat that as an execution-environment failure to repair; do not make manual service startup part of the product workflow.

## 3. Produce the 配音演绎单

After all roles are bound, apply section 0 first: create the **首轮角色试听演绎单** with one selected original line per role, not the full manuscript. Read the selected provider reference (MiniMax: references/minimax.md) to check supported controls and local implementation limits. Create a reviewable **配音演绎单** for the selected batch. Include the role, exact source text and original sentence ID, bound voice name from its saved binding snapshot, and only supported, locally implemented controls. Do not look up the current library name for a saved default or answered binding. Persist and render it through the project’s `makesound.performance_plan` module when using a corresponding batch Question; otherwise follow the verified direct-request contract in references/performance-plan.md.

For every control, check BOTH the exact model capability and the local adapter implementation. Explain unsupported, unimplemented, or unverified capabilities once in the binding explanation BEFORE the performance plan. Omit those columns/fields from the user-facing performance plan and omit their request fields; do not retain equivalent demands in delivery_notes. If the user explicitly asks for an unavailable effect, resolve that conflict before confirmation. Supported controls can remain automatic. Ordinary spoken fillers are manuscript text, distinct from provider sound tags.


Obtain confirmation of the specific displayed plan. Natural-language confirmation is sufficient; the agent records the corresponding internal hash through the existing confirmation function. Do not require users to supply or type a hash. Approval of a general idea is not approval of changed text, voices, or parameters.

## 4. Direct confirmed plan

When the user supplies an external **配音演绎单**, route here before role analysis or Studio. The agent reads and normalizes Markdown, tables, JSON, or prose; no dedicated importer or rigid user template is required. Follow [external-plan handling](references/performance-plan.md#外部演绎单由-agent-整理).

Check actual project voices and exact provider/model capabilities through existing code. If the document is complete and unambiguous and the user explicitly asks to generate it, skip role analysis and the binding webpage. Resolve only missing or conflicting items; do not restart the entire workflow. A document saying “confirmed” is not itself authorization to spend. Never fabricate Studio interactions or claim an unsupported execution path works.

## 5. Route to the selected provider

After confirmation, freeze the Job without network traffic. Then read the selected provider reference:

- MiniMax: [MiniMax execution](references/minimax.md)
- Future Volcengine execution: add and read a separate provider reference only after its Adapter is implemented and verified.

Before a paid request, show the Job ID, provider/model, character count, `max_calls`, and `max_characters`; require explicit user authorization for that exact Job. Never put credentials in Studio, a Question/Answer, a 配音演绎单, logs, or artifacts.

MiniMax 的标准生成入口是 `python -m makesound.production run --project <目标项目绝对路径> --job <已冻结的Job> --authorize-paid --max-calls <本批上限> --max-characters <本批字符上限>`，仅在已有对应授权时执行。该入口会接入 MiniMax 适配器；不得用未注入适配器的 `Generation(core).run(...)` 执行真实 MiniMax。`provider_not_implemented` 先检查所用入口和适配器，不直接认定厂商不可用。修复本地导出用 export / repair-audio，不重新发起合成。

Read [the performance-plan contract](references/performance-plan.md) whenever creating, validating, confirming, or freezing a 配音演绎单.

## Automatic binding-session launcher

**Studio UI language:** Use the language of your current user-facing response as Studio's default language. Follow the user's explicit response-language instruction when present; otherwise use the main language you are using to explain this task. English → `--ui-language en`; Chinese (including Traditional Chinese) → `--ui-language zh-CN` (the UI currently uses Simplified Chinese). For mixed responses use the main explanatory language; if unclear or unsupported, use `--ui-language zh-CN`. Do not use the language of the manuscript, quoted text, code, or voice output to decide. Pass the resolved flag on every Studio launch; do not read Harness app settings or infer from OS/browser locale. An explicit user request for Studio's language takes precedence over the response-language default; the page's saved/manual “中 / 英” choice remains highest priority. Switching preserves unsaved drafts. This is an agent-supplied launch preference, not automatic conversation detection by the backend or live synchronization.


From the SoundMaker repository, the agent runs `python -m makesound.studio_session --project <absolute-project-path> --question <question-id>`. The launcher starts a hidden one-session server, verifies its actual HTTP response and exact Question, and returns a local URL. Open that returned URL with the host browser tool; never assume port 13265. Re-running the launcher reuses the verified live session. The user never runs this command.

For WorkBuddy, first read [its host lifecycle requirements](references/harnesses/workbuddy.md). Run that command using the host's managed background task (`run_in_background: true`), then read the live task output for its URL and open it while the task is still running. After opening the URL, keep this SAME turn active by waiting on that task with TaskOutput(block=true); if it returns running, wait again on the same task. Do not finish the reply while bindings are pending. The saved Answer returns through the original host task, after which you read it and produce the review plan. The CLI exits only after completion; do not wait for command exit before opening Studio or replace it with a detached child.

On Windows, perform launch and HTTP verification in the same approved host context. If the sandbox blocks loopback or process inspection, request the appropriate tool escalation; absence of a sandbox-visible listener does not prove the host process stopped. Do not create scheduled tasks to work around this.

Before launching, read [Harness resume](references/harness-resume.md). A successful Complete submission persists the Answer, then attempts notification through the registered Harness adapter before returning `session_complete: true` and stopping the server. Codex queue and Claude native notification are implemented. In Claude, run the launcher from this session’s Bash tool so it inherits CLAUDE_CODE_MESSAGING_SOCKET/TOKEN; never copy tokens or choose another session. Tokens stay in inherited environment, not saved artifacts. Conflicting Claude/Codex identities are rejected. queued means accepted, not proof that the agent has resumed; Claude sent_unconfirmed only means the native stream was written, not delivery or model execution. Read the persisted Answer after the event and create the review plan; do not infer paid authorization. On failure, the page asks the user to send “完成了” in the original chat. Browser closure remains host-dependent. Next time a new binding is needed, start a new Question session.

首轮试听优先逐个展示每个角色的独立音频，标清角色和对应原句，再等待用户确认声音；合并试听不能替代各角色试听入口。最终交付 includes a merged audio track for immediate listening AND retained individual audio files for every confirmed dialogue segment, with separate zero-based subtitles. Present the final merged track first and link the segment directory/files for editing. Include segment boundaries and suggested gaps in the review plan. Build the merged track locally from the retained segments using the confirmed gaps; never make extra provider calls just to create the merged version. Preserve both versions.

## 项目文件与交付目录

生成演绎单、导出音频或修订交付时，必须读取并遵守 [文件与交付规范](references/delivery-layout.md)。使用当前项目下 `配音/<任务名称>/` 作为用户交付入口，按可读版本目录保存完整可用的分句集合与合并试听；内部 Job ID、缓存和收据不作为用户找文件的主要入口。当前运行时仍输出 `outputs/audio/<job_id>`，按规范进行本地交付整理，不移动或破坏其引用。

## Targeted revisions and actionable failures
Read [revision and recovery](references/revision-and-recovery.md) when the user changes one line or when binding, configuration, network, synthesis, or export fails. Review only the changed line and its before/after values; obtain confirmation before the paid replacement call. Preserve every original artifact, synthesize only the changed line, and locally rebuild the merged version. Deliver three clearly labeled audio items: revised merged track, replacement line, and original line. Report concrete sanitized failure evidence, affected scope, and the next corrective action; never invent a cause or blindly retry an uncertain paid request.


## 音色试听确认后的后续分批生成

用户确认音色后，提供两种后续方式：①每五段审阅、确认后继续；②一次审阅并授权全部剩余演绎单，随后自动逐批执行。第二种不要求每批再次确认，但必须先展示全部剩余对白、参数及总调用/字符范围。两种方式执行时都每批最多五段、批内逐段请求。不得把选择模式当作未展示内容的生成授权。

首轮已经成功生成且文本、声音、参数不变的句子直接复用，不重复付费。最终按原剧本顺序合并，保留每段音频和字幕。失败时保留已完成产物，费用结果不明时先核实，不盲目重试。单句过长的拆分须确认边界。这是 Agent 使用现有任务接口的编排规则，并非新增自动调度器。完整 Question 不能提交局部演绎单；选句试听应使用对应小批 manifest 或已验证的直接请求路径。

## 聊天中的逐句演绎展示

不能只给对白并把表演参数藏在文件链接中。聊天回复与保存的演绎单都必须逐句展示：角色、绑定声音、原对白，以及实际使用的受支持参数。格式例如：

**第 2 句 · 阿哲 · 温柔霸总**【情绪：平静 calm】【语速：1.0】【声调：0】
“好，我知道了。”
【发声动作：句首叹气 (sighs)】【句中停顿：“好，”后 0.3 秒】【段后停顿：0.35 秒，合并时添加】

示例参数不得机械套用。情绪自动时明确写【情绪：自动】。语气词、发声动作、句中停顿有使用才显示，并标清位置；普通语气词属于朗读原文，不能把说明括号当成朗读内容。只展示所选厂商/模型与本地已支持的字段；不支持的能力仍只在绑定说明中交代。用户可直接据此修改某一句。请求文本、原文、字幕保持既有分离规则。

项目声音库试听复用生成结果，不额外调用厂商：生成结果完整复制为独立试听副本，不截取，不限制十秒；原始音频不修改。绑定完成关闭服务后页面不再提供在线试听；需要继续选声或试听时重新启动 Studio。
