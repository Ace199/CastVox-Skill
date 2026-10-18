# 通用运行接口：按需执行

仅用于主 Skill 选项 1/2 的项目音色路径；选项 3 内置生成不读取或执行本文件。不要在用户选择生成路径前运行项目查询、prepare 或媒体检查。

仅在查询声音、创建任务、读取绑定、提出/确认演绎单时读取对应配方。它们是本地操作，不授予付费权限。厂商配置、目录访问与真实生成只见选定厂商 reference；网页操作见 [Studio](studio.md)。

## 运行时和目标项目

下列配方中的 `python` 表示已确认的 Python 3.11+ 解释器，不强制要求 PATH 中存在名为 python 的命令。macOS 首次可用 python3，已有仓库虚拟环境则优先其 `bin/python`；定位后复用返回的 python_executable，不混用解释器。`python_unsupported` 只表示版本过低，不重新安装运行时、不扫描目录。基础 macOS 配置不代表各宿主自动通知已经通过 Mac 实测；只有实际打开网页才读当前宿主文档。

已有本会话的运行时绝对路径和解释器时直接复用，不再定位。否则从本次 Skill/Read 返回的加载路径取得 skill 目录，仅运行一次（可从任意 cwd 执行，无需先导入 makesound）：

```text
python -X utf8 "<当前已加载 skill 目录>/scripts/runtime_location.py"
```

该入口先解析 skill 链接的真实目标，以其上两级为运行时仓库；若宿主将 skill 导入为普通副本，读取 `~/.config/soundmaker/runtime.json` 的 `runtime_root` 安装记录。两条路径均仅检查固定文件是否存在，不读源码、不联网、不扫描目录。使用返回的 `runtime_root`、`python_executable`，不把宿主的 daimon 目录或当前用户项目当运行时。链接和记录均失效时停止项目操作，报告 `runtime_not_configured` 并让安装流程修复；不要扩大搜索 Documents、AppData、项目目录，也不要用 find、递归 glob、逐层 ls 或搜索 core_v16.py 猜位置。此入口不决定生成路径，选项 3 不执行。

记住运行时目录、当前解释器、用户项目绝对路径，每条命令显式使用运行时工作目录，`--project` 和 ProjectCore 指向用户项目。不要把运行时测试声音、默认或旧任务复制到新项目。cwd 重置不代表重新定位。

## 生成前检查与冻结/导出入口

生成授权前若本任务没有有效检查结果，执行一次 `python -m makesound.media`；环境和格式要求不变时沿用结果，不因换批次或打开另一个 reference 重跑：优先复用 PATH 中的 FFmpeg；Windows 额外核对已有 WinGet，macOS 额外核对 /opt/homebrew/bin 和 /usr/local/bin 中的可执行配对，不调用包管理器。媒体检查同时返回解释器、Python 版本与平台；python_unsupported 时先选择 Python 3.11+。`wav_only` 可保存、检查和拼接匹配的单声道 16-bit PCM WAV、追加静音、导出 SRT；MP3/重采样需要外部工具，冻结前说明限制并选格式。禁止自动下载、安装或修改全局 PATH，冻结后不静默改格式。

```text
python -m makesound.production plan --project "<project>" --performance-plan "<confirmed-plan-id>"
python -m makesound.production plan --project "<project>" --request "<reviewed-request.json>" --confirmed
python -m makesound.production export --project "<project>" --job "<job-id>"
python -m makesound.production repair-audio --project "<project>" --job "<job-id>"
```

只执行当前步骤需要的一条。`plan` 只冻结，不授权生成；`--confirmed` 必须有实际对应确认。export / repair 只适用于已有产物，不是通用失败重试。

## 固定调用配方（无需查源码或枚举方法）

以下命令都在**运行时仓库目录**执行。路径/ID 使用工具参数或正确的 Shell 引号传入；中文原稿、角色描述和计划内容由文件工具写入 UTF-8 JSON，不把用户正文插入 Shell/Python 代码，不用含中文正文的 heredoc/管道。`python -X utf8` 固定 Python 文件与标准输出编码；不要另在用户项目创建导入 makesound 的临时 `.py` 脚本，避免脚本目录改变模块搜索路径。占位路径必须替换为实际绝对路径。

### A. 查询当前项目（每次任务需要时一次）

```text
python -X utf8 -c "import sys,json; from makesound.core_v16 import ProjectCore; print(json.dumps(ProjectCore(sys.argv[1]).read(),ensure_ascii=False))" "<project>"
```

返回 `voices`、`defaults`、`default_snapshots` 和 `revision`。空库就是需要选声，不是继续探索代码的理由。默认按已保存快照判断，不能因原卡片隐藏而声称默认丢失。需要精确解析某个已知声音时直接调用 `core.resolve(explicit=voice_id)`；默认按明确的声音性别要求调用 `core.resolve(gender='male'或'female')`，无性别要求用 `core.resolve()`，不猜测性别。不读取或打印原始厂商凭据；模型配置交由运行时和 Studio 加载。

本配方不返回厂商配置摘要。需要推荐厂商/模型时直接读选声 reference 的 `choices()` 固定入口，不调用旧 M1 总帮助、config --help、doctor 或 schema 猜接口；这些兼容命令不能代替 V1.6 项目操作。

### B. 创建可恢复的绑定任务

首次写项目任务 JSON 前准备工作目录一次（本地操作，不创建 Question 或生成音频）：

```text
python -X utf8 -m makesound.project_files workspace --project "<project>" --task "<stable-task-key>" --title "<任务名称>"
```

`stable-task-key` 使用本任务唯一的字母/数字/下划线/连字符标识；同任务跨批次、改绑和恢复沿用，另一任务另建标识及不同标题。任务名清理 Windows 非法字符和路径分隔符后使用，不以用户文字拼任意路径。保存返回的 `inputs_dir`、`delivery_dir`。以下 manifest、recommendations、assignments、items、试听 performance、最终 targets、需保存的工具 JSON 均在 `inputs_dir` 下，以含批次/版本的文件名区分，已有已审阅输入不覆盖；外部原稿保持原位。运行时创建的 request/plan/handoff 不额外复制一套。

用文件工具写 `<manifest.json>`，内容结构如下；实际包含本次完整绑定稿，ID 采用字母、数字、下划线或连字符，中文放 display_name/text，不使用中文 ID：

```json
{"roles":["r1"],"role_metadata":{"r1":{"display_name":"角色名","appearance_summary":"来自原稿的描述","recommended_voice_description":"推荐声线"}},"segments":[{"paragraph_id":"p1","sentence_id":"s1","role_id":"r1","text":"本次原对白"}]}
```

```text
python -X utf8 -m makesound.offline_harness prepare --project "<project>" --manifest "<manifest.json>"
```

这里只复用 `prepare` 的本地任务准备能力：它生成唯一 Question/Job ID，并同时保存原稿 handoff，不执行音频生成。返回中的 `offline_only` / `needs_studio` 是旧入口标记，不决定选声方式，也不是生产模型可用性结论。**真实配音不得使用此模块的 `continue`，生成仍只走所选厂商 reference 记录的 production。** 不单独调用 `Questions.create` 代替这个配方，不手填 `job_pending`，不手写内部 handoff，不因想确认 ID 再造一次任务。保存 question_id；聊天选声继续 [选声契约](voice-selection.md)，只有用户选择网页配置时才启动对应 Studio，满足宿主归属核对。

`prepare` 本身不改项目 preset 的 revision；仅此步骤后无需为取版本重复查询。入库、参数修改、试听保存或其他页面操作可能改变 revision；需要写入时使用已知当前版本，冲突再读取并核对，不自动覆盖。

### C. 绑定完成后读取原结果

当前 Question 使用最近一次启动/保存实际返回的 ID；改绑后用新版本，旧 source_question_id 仅用于追溯。已读该 Answer 且未变化时沿用返回值，不为满足本配方再次读取。

Cowork 主机桥接的 wait/read 工具已返回完整真实 Answer 时，即完成本配方；不在 VM 再执行下方命令读取主机项目，也不改写主机路径。桥接缺少的后续执行入口应报告缺口，不在 VM 重建任务冒充同一项目。具体工具只在网页阶段的当前宿主说明维护。

```text
python -X utf8 -c "import sys,json; from makesound.core_v16 import ProjectCore; from makesound.questions import Questions; print(json.dumps(Questions(ProjectCore(sys.argv[1])).read(sys.argv[2]),ensure_ascii=False))" "<project>" "<question_id>"
```

网页绑定 `pending` 时按当前 Harness 等待规则等待，不忙轮询、不创建新 Question；`answered` 时使用 `answer.resolved` 中的声音快照。聊天中用户明确选定后，按选声契约提交真实选择；不能为了继续而猜测选择、伪造网页操作或提前 `claim`，冻结入口处理所需领取。没有接收证据时只说“完成后将尝试通知”，不能保证“我一定自动收到”。

**绑定完成后先取得真实 Answer，再检查已有试听。** bind 已返回该 Answer 时直接沿用，不重复执行 C。推荐路径按 D.1 使用一份完整 final-items 同时推导复用目标与实际批次，仅复用与最终目标一致且获认可的片段；无最终目标的已有音频清单不能代替参数比较。不强迫沿用试听自动情绪；正常的情绪调整在最终演绎单中列明差异和新增范围。尚未试听的角色才按主 Skill 的试听选句规则选句并执行 D。继续复用原 project、question_id、运行时目录和解释器。读取到 `answered` 后，不再运行 prepare/production 的 `--help`，不重新查询声音库或读取 questions.py；根据本次未完成范围，直接提交对应批次配方。缺少原稿上下文时只读本次原稿文件或 `.makesound/handoffs/<question_id>.json` 的 manifest，这是任务数据，不是程序源码。

### C.1 将已选角色声音保存为项目默认

仅用户明确要求时执行，绑定完成本身不设置默认。“把当前声音设为默认”使用 general；明确默认男声/女声时才指定对应 slot，不能因声音性别擅自修改其他槽位。单角色自动取该角色；多角色须明确 `--role`，不猜。先用已知当前 revision；未知时按 A 只读一次。固定入口沿用保存的 Answer，核对当前活动声音来源/参数未变化，写 V1.6 的默认快照，幂等保存不修改绑定或触发生成：

```text
python -X utf8 -m makesound.project_defaults --project "<project>" --question "<current-answered-question_id>" --revision <reviewed-revision> --slot general
```

使用返回的 status、revision、defaults 说明成功；冲突/声音变化先核对，不循环改版本号试命令。不要调用旧 M1 `makesound config set-default/show/schema`，它操作另一份兼容数据；不要传正文 JSON 到要求文件路径的 CLI，不因此打开网页代替已有入口。默认修改和音频生成分别报告结果。

### D. 提出与确认演绎单

推荐路径最终绑定后优先使用下述“统一正式入口”；自行绑定首轮试听或已有明确批次可沿用本配方。准备 UTF-8 `<items.json>` 数组，每项至少包含 `sentence_id`、`emotion`、`delivery_notes`、`pause_after_ms`；字段含义及可选控制仅按 performance-plan / 当前厂商 reference，不查源文件。首轮按主 Skill 的试听选句规则每角色选一句，每批最多五句；items 只写本批选中原句。下方配方从同一个已回答 Question 创建独立批次，显式传入所选 sentence_ids，自动沿用 Answer 快照及原稿顺序。无需新建 Question、重复网页绑定或把快照转换成当前库声音。

```text
python -X utf8 -c "import sys,json; from pathlib import Path; from makesound.core_v16 import ProjectCore; from makesound.performance_plan import propose,render; items=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8-sig')); result=propose(ProjectCore(sys.argv[1]),sys.argv[2],items,sentence_ids=[item['sentence_id'] for item in items]); print(json.dumps({**{k:result[k] for k in ('plan_id','plan_hash','job_id','question_id','sentence_ids','status')},'review':render(result)},ensure_ascii=False))" "<project>" "<question_id>" "<items.json>"
```

保存返回的 `plan_id` 与 `plan_hash`，根据同一输出的 `review` 展示逐句演绎单；它带原句 ID 和实际参数，不输出重复的完整嵌套计划，也不再读工具日志提取一遍。完整计划仍保存在项目中。只有用户确认该版本之后才运行：

```text
python -X utf8 -c "import sys,json; from makesound.core_v16 import ProjectCore; from makesound.performance_plan import confirm; result=confirm(ProjectCore(sys.argv[1]),sys.argv[2],sys.argv[3]); print(json.dumps({k:result[k] for k in ('plan_id','plan_hash','confirmation_hash','status')},ensure_ascii=False))" "<project>" "<plan_id>" "<reviewed_plan_hash>"
```

必须使用**展示时保存的哈希**，不得读取最新哈希来绕过变更确认。随后用上表 production plan 冻结，再按实际付费授权执行 production run；不是一次连续自动执行整张命令表。

保存本次返回的独立 `job_id`，不要拿原绑定 Question 的 job_id 执行本批。用户认可音色后，剩余句子按每批最多五句重复 D，仍复用原 question_id，使用各批返回的 plan_id/job_id。批次选择、确认和冻结均不调用付费接口；原稿变化会拒绝冻结，需要重新审阅。旧的 `propose(core, question_id, items)` 不传 sentence_ids 时仍要求全稿覆盖，不用于部分选句。

### D.1 统一正式入口：同一份完整 items 计算复用与批次

准备 `<final-items.json>`，覆盖本任务全部原句，字段与 D 一致。实际情绪以 `provider_directives.emotion` 为准；只在描述字段写 calm 不会发给模型，现会报 emotion_not_mapped。指定 calm 时写 `"emotion":"calm","provider_directives":{"emotion":"calm"}`；自动写 `"emotion":"自动","provider_directives":{}`，控制写 inline_controls。不再另建 final-performance-targets.json，不把试听值当作必须沿用的最终目标。

```text
python -X utf8 -m makesound.final_delivery review --project "<project>" --question "<current-answered-question_id>" --items "<final-items.json>" --selection "<selection_id>"
```

无推荐选声记录时省略 `--selection`。返回同一份输入计算的 reusable_sentence_ids、remaining_sentence_ids、原稿顺序最多五句的实际 review、plan_id/hash 和独立 job_id；ready_to_publish 表示没有新增句。只展示实际返回的情绪/控制。后续批次显式用可重复的 `--sentence <原句ID>` 选择尚未完成范围；已有已确认/冻结批次直接沿用，不因恢复重新 review。不要再手写另一份 items 改变同一批实际参数。

向用户展示 review 与复用范围，确认后仍用 D 的 confirm、production plan 和所选厂商授权入口执行；review 不授权付费。用户要一次审阅全部时先展示完整 final-items 的可执行目标和总范围，按已有规则逐批冻结，不把第一批确认当全稿授权。最终调用交付规范的 publish，传同一 final-items、实际生成 Job 和 selection，交付时再次检查参数一致。

### E. 失败才诊断；成功立即推进

- `ModuleNotFoundError: makesound`：先确认该次命令的工作目录和解释器，改回上述 `-m` / `-c` 调用。不要因用户项目外置脚本导入失败就重装包、改全局 PYTHONPATH 或扫描仓库。
- 中文乱码：检查输入文件是 UTF-8，使用固定配方；不默认重复创建 Question。已有错误记录需针对处理，保留原任务归属，不手改冻结状态。
- 参数拒绝：只看当前入口的帮助一次；权限/回环受限按宿主工具处理。一次修正仍失败，报告具体错误和影响，再做最小范围诊断，不循环试探或打印凭据。
- 缺少原稿/用户选择/授权时处理该缺项；需要等待用户不是程序错误，不触发源码排查。成功返回后直接下一步，不再执行 inspect 或查看实现“验证一次”。
- 已知待提取字段时，在原调用中投影输出必要 ID/摘要；不要先打印完整嵌套结果，再反复 Read、Grep 同一工具日志。输出已被宿主截断时只提取缺项一次，不重新运行写入/生成命令来取输出。既有目录证据和配置摘要未变时复用，不重复抓取目录。
