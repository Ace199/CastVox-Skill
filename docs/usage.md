# 使用说明

## 安装为目录链接

先克隆仓库，在仓库根目录运行。Windows PowerShell 示例（目标不存在时执行）：

```powershell
$skillSource = (Resolve-Path './skills/soundmaker-dubbing').Path
$skillParent = Join-Path $env:USERPROFILE '.codex/skills'
New-Item -ItemType Directory -Path $skillParent -Force | Out-Null
New-Item -ItemType Junction -Path (Join-Path $skillParent 'soundmaker-dubbing') -Target $skillSource
```

Claude Code 使用 `~/.claude/skills`，WorkBuddy 使用 `~/.workbuddy/skills`。Kimi Work 和豆包应先确认当前版本实际扫描的 skill 目录，再创建链接；Kimi Work 已验证版本的目录为 `%APPDATA%/kimi-desktop/daimon-share/daimon/skills`，豆包本机扫描入口包括 `~/Doubao/skills`。这些路径不代表其他版本或平台的稳定约定。

已有同名目录时先检查内容并备份，不覆盖或删除。创建链接后新建对话，确认宿主实际读到 SKILL.md。宿主导入或升级可能将链接改成副本；可用 `Get-Item <skill-path> | Select-Object LinkType,Target` 复核。macOS/Linux 使用对应宿主目录及符号链接，宿主恢复的实机覆盖范围仍以参考文档为准。

修改仓库后，核对宿主路径仍为链接、目标正确，且该路径与仓库 SKILL.md 的文件哈希一致；仅通过仓库测试不能证明宿主已经加载新版。需备份的旧副本放在宿主 skill 扫描目录外，避免被重复发现。替换链接不会更新对话中已经加载的旧指令，使用宿主支持的重新加载或新建对话后再验收三个入口。

Agent 应从 skill 的真实链接目标定位仓库，所有 `python -m makesound...` 命令以仓库为工作目录，`--project` 始终传用户当前项目的绝对路径。不要把仓库测试项目、测试声音或默认值复制进用户项目。

为支持宿主将链接重新导入为普通副本，在首次安装或迁移运行时后，从仓库根目录执行一次，保存本机安装记录（不是厂商配置，不含密钥，也不提交到仓库）：

```powershell
python -X utf8 -c "import json; from pathlib import Path; root=Path.cwd().resolve(); assert (root/'makesound/__init__.py').is_file() and (root/'skills/soundmaker-dubbing/SKILL.md').is_file(); record=Path.home()/'.config/soundmaker/runtime.json'; record.parent.mkdir(parents=True,exist_ok=True); record.write_text(json.dumps({'runtime_root':str(root)},ensure_ascii=False),encoding='utf-8')"
```

Agent 需要项目运行时且尚未记住位置时，只运行已加载 skill 目录下的 `scripts/runtime_location.py`；目录链接优先，安装记录为副本回退。两者失效则修复安装，不扫描用户目录。安装后应从宿主实际 skill 路径运行该入口，核对返回的仓库位置；内置音频入口不需要这个步骤。

## Claude App：先区分 Code 与 Cowork

Code 本地会话使用 `~/.claude/skills`。Cowork 的 skill 入口和运行环境不同；目录链接只负责加载规则，不能证明主机 MCP 已连接。当前网页绑定使用主机侧 `soundmaker_host` MCP：页面、项目和 Python 都在主机，Cowork 通过原工具请求取得保存的 Answer，不在 VM Bash 启动服务。

### 一次安装 skill 与主机桥接

在主机仓库中，用 Python 3.11+ 执行一次（macOS 用对应 python3）：

```text
python -X utf8 -m makesound.claude_install
```

无需手填 MCP JSON、解释器路径或 skill 连接命令。安装器检查 Windows 的 Claude-3p/Claude 固定配置位置或 macOS 的 Claude 配置位置，只在已知 skills-plugin 下检查两级账号/会话目录，不递归搜索用户文件。唯一兼容目录时自动连接 skill、备份并写入通用 MCP host_bridge、登记 soundmaker 应用；默认项目目录 ~/Documents/SoundMaker/projects。可识别的本仓库旧桥接升级会保留原项目根目录，备份后只移除完全匹配的旧 soundmaker_host 条目，其他配置和 MCP 保留。重复安装不重复登记。

多个 App/账号匹配时停止并列出需要显式选择的参数；不同内容的同名 skill 或 MCP 不覆盖。首次使用前需先打开 Cowork，让 App 建立本地 skill 存储。当前自动连接针对已验证的本地目录结构，不保证所有官方发行版本采用相同结构，也不代替账号侧 skill 上传。

```text
python -X utf8 -m makesound.claude_install --check
python -X utf8 -m makesound.claude_install --app-data "<选定的 Claude 数据目录>" --plugin-root "<选定账号的 skill 插件目录>" --allowed-root "<专用主机项目目录>"
```

--check 仅解析目标，不创建目录或写配置，也不证明 App 连接成功。备份保存在 ~/.config/soundmaker/backups/；若第二步失败，报告 partial_install 及已完成的 skill 步骤，修正冲突后可重跑。安装不调用语音服务、不上传密钥、不强制关闭 App。配置完成后重新连接本地 MCP，必要时重开 App；调用 host_bridge_status 确认 ready、execution_environment=host、applications 包含 soundmaker。这一次宿主加载动作可能仍需用户完成，复制 SKILL.md 本身不会执行安装器。

通用桥接核心位于 host_bridge/，只有状态、启动任务、等待、读取结果四个工具；不依赖 SoundMaker。makesound/host_application.py 负责 SoundMaker 业务，scripts/host_bridge.py 是明确登记应用的启动入口。其他应用可实现相同适配接口接入；工具调用者不能指定任意命令或模块。当前只交付了 SoundMaker 的实际应用适配器，尚未发布独立 MCPB 安装包。

桥接只允许配置目录下的项目，按逻辑 project_key 创建子目录；不接受 VM 或任意绝对项目路径。它只提供状态、创建/打开绑定、等待、读取结果与 Fake 验收工具，没有合成或任意 shell 执行入口。所有原稿、角色和项目操作都在同一主机项目内，保留现有项目身份校验；不自动迁移旧 VM 项目或缓存。

### 无付费验证

在 Cowork 中直接说：

```text
调用 host_bridge_start，application=soundmaker、operation=smoke_binding、payload={}，
request_id 使用本次测试的稳定标识。
展示返回的 URL，然后调用返回的 wait_tool，保持当前请求等待。
waiting 时继续同一个 handle；我在网页完成 Fake 角色绑定后，
报告真实 question_id、answer_id 和已保存选择，随后停止，不生成音频。
不要转用 VM Bash，不再询问是否继续。
```

正常任务用 `host_bridge_start`，application=soundmaker、operation=prepare_binding，顶层传 request_id，payload 传 project_key 和原始 script；同一原稿重试复用相同 ID，避免重复创建。已知 Question 要修改时才用 operation=open_binding；仅获取已保存结果或重连恢复时用 `host_bridge_read`（application=soundmaker，resource 传 project_key/question_id），不会创建新修订。网页由主机 MCP 持有，跨工具调用持续可用；MCP 关闭会关闭页面服务，磁盘结果保留。结果通过发起等待的 MCP 请求 ID 返回，不广播；handle 只在当前桥接进程有效，同一 Question 只允许一个活动等待。

2026-10-18 的原专用桥接在 Windows Claude App 实测已完成：主机连接 ready → 打开绑定页 → 用户提交 Fake 角色 → 原 Cowork 的 wait 工具取得真实 Answer → 原请求继续报告已保存选择。没有调用合成。agent_resumed=false 仍保留，因为单次工具回执不能独立证明模型回复；本次续跑证据来自原会话的后续报告与落盘 Answer 核对。新增通用工具入口有真实子进程 MCP/HTTP 自动化回归，尚未重做 App 实机验收。

这条通路延续正在等待的请求，不能唤醒已结束的聊天。客户端取消/断连后可在原聊天说“完成了”，用已保存项目标识读取结果。其他平台、App 版本、真实 TTS、独立声音库管理和旧 VM 项目迁移不在此次验收范围。完整按需路由见 [Cowork 说明](../skills/soundmaker-dubbing/references/harnesses/claude-cowork.md)。

### Skill 目录链接

对已核实提供本地 skill 存储的 Cowork 开发版本，可执行 `python -m makesound.claude_cowork --plugin-root "<当前 App 实际 skill 插件根目录>"`。安装器只检查显式目录，备份清单、保留其他 skills，登记本地 user/syncManaged=false 项并拒绝覆盖副本。它不会上传账号；App 升级/同步可能改变缓存，需核对链接和当前会话加载结果，不绕过宿主校验。官方通用 skill 入口见 [Claude 使用说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)。

参考：[Anthropic skills](https://github.com/anthropics/skills)、[Cowork 插件示例](https://github.com/anthropics/knowledge-work-plugins)。消息中继或原生身份检查成功不能代替主机网页与原请求续跑验收。

## 其他 Skill 接入通用桥接

按[接入协议 1.0](host-bridge-integration.md)实现自己的应用适配器；它统一 MCP 业务结果、网页提交、错误、版本校验和幂等回执，提供独立表单示例与可复用存储/HTTP 服务。普通 SoundMaker 配音不需要额外读取这份开发文档。新版协议显式声明 protocol_version=1.0；省略版本的现有调用保持兼容。

## macOS 基础安装与配置

当前新增 macOS 的配置编辑器、解释器检查及已有 FFmpeg 发现分支；核心配音和文件交付复用同一套代码。Mac 原生文件锁、符号链接和后台 Studio 冒烟测试放入跨平台 CI，尚未执行的 CI/真实桌面操作不能视作已验收。Codex、Claude Code、Kimi、豆包等自动通知与续跑仍分别按宿主文档的已验证范围处理，本节不承诺全部宿主完整 Mac 适配。

### 1. 确认 Python，准备运行时

在终端执行；需要 Python 3.11+，若 python3 版本过低，使用已经安装的较新解释器替换命令中的 python3。不自动安装 Python/Homebrew，也不修改全局 PATH。

```sh
git clone https://github.com/Ace199/CastVox-Skill.git
cd CastVox-Skill
python3 -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'; print(sys.executable)"
python3 -m venv .venv
.venv/bin/python -m makesound.media
```

已有仓库直接进入原目录；已有 `.venv` 时跳过环境创建，先核对 `.venv/bin/python` 版本。核心不需要额外 pip 安装依赖。`makesound.media` 返回 python_executable、python_version、python_supported、platform 和媒体状态。版本过低时返回 python_unsupported 和退出码 2；不要误判成运行时缺失。后续优先使用这里确认的解释器完整路径，桌面宿主不一定继承终端中的环境。

### 2. 安装 skill 为符号链接

下面以 Codex 的个人 skill 目录为例，在仓库根目录执行。目标已存在（包括旧链接）时 Python 会拒绝创建，不覆盖、不向旧目录里再嵌套一个链接。先检查并备份旧安装，备份放在宿主扫描目录之外。

```sh
.venv/bin/python -c "from pathlib import Path; root=Path.cwd().resolve(); target=Path.home()/'.codex/skills/soundmaker-dubbing'; target.parent.mkdir(parents=True,exist_ok=True); target.symlink_to(root/'skills/soundmaker-dubbing',target_is_directory=True)"
```

Claude Code 将目标父目录改为 `~/.claude/skills`。Kimi、豆包和 WorkBuddy 先核对该 Mac 应用实际支持的 skill 目录，不把 Windows 的 AppData 路径替换成猜测的 Mac 路径。

从仓库根目录写入本机运行时记录，以支持宿主重新导入普通副本时定位原运行时：

```sh
.venv/bin/python -X utf8 -c "import json; from pathlib import Path; root=Path.cwd().resolve(); assert (root/'makesound/__init__.py').is_file() and (root/'skills/soundmaker-dubbing/SKILL.md').is_file(); record=Path.home()/'.config/soundmaker/runtime.json'; record.parent.mkdir(parents=True,exist_ok=True); record.write_text(json.dumps({'runtime_root':str(root)},ensure_ascii=False),encoding='utf-8')"
.venv/bin/python -X utf8 "$HOME/.codex/skills/soundmaker-dubbing/scripts/runtime_location.py"
```

核对返回的 runtime_root 和 python_executable，然后新建对话或重新加载 skill。以上 skill 目录可链接；用户项目数据的受管理路径仍保持原来的链接/越界保护，不为 Mac 关闭校验。

### 3. 创建并打开 MiniMax 配置

只在实际选择项目音色/MiniMax 后执行：

```sh
.venv/bin/python -X utf8 -c "import json; from makesound.voice_selection_entry import configure; print(json.dumps(configure('minimax'),ensure_ascii=False))"
```

路径仍为 `~/.config/minimax/config.json`，不搬迁旧文件。缺失时创建模板，已有文件只打开；macOS 通过 `/usr/bin/open -t` 请求默认文本编辑器，避免执行 JSON 的任意文件关联。请求成功不代表已经编辑/保存；填写 Key 并保存后再检查配置摘要，密钥不发聊天。无桌面会话、编辑器不可用或系统拒绝时返回安全错误，保留原文件/模板，可按返回路径手动编辑。

### 4. 复用已有 FFmpeg，或先使用 WAV

先检查 PATH；不足时只核对 `/opt/homebrew/bin`、`/usr/local/bin` 中完整且可执行的 ffmpeg/ffprobe 配对，不扫描磁盘、不执行 brew、不下载安装。查找规则与 Homebrew 常用前缀有关，不能据此推断用户已安装或所有 Mac 版本均受支持；参考 [Homebrew 安装说明](https://docs.brew.sh/Installation)。

未找到时返回 wav_only：匹配的单声道 16-bit PCM WAV 可保存/拼接，字幕仍依赖真实时标；MP3 和重采样需用户准备媒体工具。自定义安装位置可在启动宿主时提供正确 PATH，或由开发调用显式指定工具路径；已有显式路径不会被自动发现覆盖。

### 5. 先核对基础页面

要先管理声音，可创建一个独立项目，从仓库启动：

```sh
mkdir -p "$HOME/CastVoxProjects/first-project"
.venv/bin/python -m makesound.studio_session --project "$HOME/CastVoxProjects/first-project" --ui-language zh-CN
```

打开实际返回的本机 URL，检查配置按钮、添加声音和默认设置。该管理入口不创建绑定 Question、不调用 TTS，也不发原聊天完成通知。网页绑定后自动续跑的宿主适配不在本次新增范围；需要手动继续时，回原聊天发送“完成了”，由 Agent 读取真实已保存 Answer，不能伪造通知成功。

## 配置和音频工具

MiniMax 配置通过本机配置入口管理，默认位于 `~/.config/minimax/config.json`。不要将真实 API Key 提交到 GitHub、贴到聊天或写入测试示例。Studio 的配置编辑按钮可辅助打开/创建配置；火山引擎配置支持不代表其合成适配器已实现。

在展示本次生成授权范围前执行：

```powershell
python -m makesound.media
```

`ready` 表示媒体工具文件已找到；`wav_only` 表示使用纯 Python 的匹配 PCM WAV 路径。WAV 回退支持单声道 16-bit PCM、帧完整性检查、同采样率拼接与字幕导出；它不是通用解码或重采样器。MP3 和重采样需要已有的 FFmpeg/FFprobe。找不到时不自动下载安装，在冻结 Job 前明确使用 WAV。

## 声音管理和绑定

未绑定角色可选择“帮我选声音”：默认每角色推荐 2～3 个已核实音色（最多 3 个；用户明确单选或确实仅有一个合适候选时可只给一个并说明），所有候选入项目库，按用户选择生成单个、部分或全部候选的同句试听。确认最终声音后在聊天保存绑定，无需网页。推荐和入库不生成音频；试听生成仍须确认具体内容及费用范围。生成成功的完整试听保留在声音库。

已有固定音色或工作流时选择“使用我的声音”，直接复用明确配置；只在需要管理或自行配置时打开网页。调用契约见 [聊天选声](../skills/soundmaker-dubbing/references/voice-selection.md)。MiniMax 查询接口提供目录，角色匹配推荐由 Agent 判断。

只管理当前项目声音时，可启动持久化 Studio：

```powershell
python -m makesound.studio_session --project '<existing-absolute-project-path>' --ui-language zh-CN
```

读取实际启动输出的本机 URL，不假设端口。此入口不创建假任务，不发绑定完成通知。离线开发需要 Fake 时使用底层 `studio_v16_server.py --fake --config-dir web/tests/fixtures/providers`，该目录只有测试配置。

配音任务的绑定页由 Agent 创建 Question 后执行：

```text
python -m makesound.studio_session --project <absolute-project-path> --question <question-id>
```

对话已有角色和任务时，重新打开网页默认使用带 Question 的入口，展示角色和已有绑定。已提交的任务会自动准备预填的新绑定版本，返回实际新 Question ID；从旧 ID 重开也会沿用最新已保存选择。打开草稿不改变生效绑定，不生成音频，也不授权付费；旧 Answer、Job 和音频保留。保存后用 `python -m makesound.binding_revision status --project <project> --question <new-question-id>` 查询受影响角色与句子，只审阅和生成需要变化的部分。

用户只需在页面选择声音、速度和声调，再点击完成。Agent 从保存的 Answer 恢复，检查已有试听，不重复生成相同内容。宿主恢复失败时可在原聊天说“完成了”；完整 Answer 不会因通知失败丢失。仅到网页步骤读取当前宿主说明；WorkBuddy 按受管理后台任务要求启动和等待。

默认声音、默认男声、默认女声均可留空。选择或清空默认只改草稿，页面不设独立保存/取消按钮；点击“完成设置”时，有变化才弹出确认。取消或 Esc 保留草稿；确认后先保存默认，再提交当前绑定。保存失败时不提交，提交失败时保留已经保存的默认，修复后可重试。

已保存默认包含独立声音快照。库中原卡片的编辑或软删除不会自动重写默认或既有任务；需要更新默认时显式重新选择并保存。直接声音管理没有待处理 Question 时，只保存管理结果，不通知聊天或生成音频。

## 界面语言

Studio 支持简体中文和英文。顶部“中 / 英”按钮可随时切换；选中项呈按下状态，悬浮与点击提供分级按压反馈。切换保留未保存的默认草稿、声音参数及角色分配，不触发保存或通知。用户输入的名称、剧本和 Voice ID 不自动翻译。

默认语言由 Agent 当前回答语言决定：英文回答用英文，中文回答用简体中文；混合回答取主要解释语言，无法确定或不支持时默认中文。剧本、引用、代码和配音语言不参与判断。用户明确指定 Studio 语言时优先采用；页面手动选择优先于启动语言，浏览器允许时仅在同源地址记住选择，端口改变后不保证沿用。复用同一绑定服务时，若启动语言不同会返回 `ui_language_mismatch` 并保留原服务；可在原页面切换，或关闭后再启动。

主 Skill 在每次启动时通过 `--ui-language` 传入，不读取各 Harness 设置，也不跟随浏览器或操作系统语言。后端不自动分析聊天，已打开页面不实时跟随回答语言变化。英文回答的启动示例：

```text
python -m makesound.studio_session --project <absolute-project-path> --question <question-id> --ui-language en
```

直接管理入口 `studio_v16_server.py` 也支持 `--ui-language en` / `zh-CN`。调用者也可设置项目自定义环境变量 `CASTVOX_UI_LANGUAGE`，显式参数优先；该变量不是任何 Harness 官方语言变量。页面语言只影响显示，不改变音频语言、项目配置或付费授权。

## 确认和生成

Agent 负责整理原文、角色、已绑定声音、支持的情绪与停顿，展示可审阅演绎单。用户不需要提供内部 hash。确认后冻结 Job，展示厂商/模型、字符数及调用上限，已有的明确授权不重复索取。

以下是运行接口，占位值必须来自已确认并授权的实际任务；不能原样执行或当作付费许可：

```text
python -m makesound.production run --project <absolute-project-path> --job <frozen-job-id> --authorize-paid --max-calls <authorized-calls> --max-characters <authorized-characters>
```

缺失配置、接口错误和未知计费不自动重试。收到音频后字幕/转换失败，只修复已有产物，不再次合成。纯本地导出使用 `python -m makesound.production export --project <absolute-project-path> --job <job-id>`；收到的音频需重处理时使用 `repair-audio`。详见主 skill 的修订与恢复参考。

## 数据目录

- `配音/<任务名称>/<版本>/`：用户可读交付，保留完整分句、字幕与合并试听。
- `.makesound/exports/audio/<job_id>/`：运行时源导出。旧 `outputs/audio` 保留兼容，不再新建。
- `.makesound/workspace/<task-key>/inputs/`：任务输入与分批 JSON，不能散落项目根目录。
- `.makesound/`：绑定问答、计划、冻结快照、缓存、预算与通知回执。

这些是项目本机数据，不上传公共仓库。目录链接只同步 skill 源文件，不同步不同项目的声音绑定或任务状态。


## 正式交付与默认声音

项目音色路径使用一份完整 final-items 统一复用检查、实际演绎参数和正式交付：`python -m makesound.final_delivery review` 提出待生成批次，确认和授权后仍走原 production 入口；`publish` 仅从已验证音频本地建立完整版本、分句、真实字幕、演绎单与索引。段后静音按可信语音边界去除，再在合并中追加一次，不使用临时拼接脚本。字幕缺失或默认设置未完成时分别报告，不能笼统称全部完成。

用户明确要求将当前角色作为项目默认时使用 `python -m makesound.project_defaults --project <project> --question <answered-question> --revision <reviewed-revision> --slot general`；多角色增加 `--role`，男/女默认仅按用户明确要求选对应 slot。该入口操作 V1.6 快照，不走旧版 config set-default，不生成音频。准确命令及授权边界见 skill 的通用接口和交付规范。
