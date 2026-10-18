# 代码与 skill 结构

## 运行时分层

代码仍保留现有模块路径，避免改变已验证的命令和数据引用。

| 层 | 主要模块 | 边界 |
|---|---|---|
| 配置与声音 | `config_loader`、`config_resolver`、`provider_config`、`preset_store`、`project_voice_library`、`voice_registry` | 读取本机配置、项目声音、默认与快照 |
| 项目与存储 | `core_v16`、`storage`、`validation`、`errors` | revision、校验、原子写入、锁和受管理路径 |
| 选声与绑定 | `voice_selection`、`binding_revision`、`questions`、`studio_backend`、`studio_session`、`project_defaults` | 候选、绑定修订、当前 Answer 保存为 V1.6 项目默认；不发起付费合成 |
| 表演计划 | `performance_plan`、`inline_controls` | 审阅、确认、声音快照与受支持控制项 |
| 执行与交付 | `production`、`generation`、`providers`、`minimax_provider`、`media`、`project_files`、`final_delivery` | 冻结 Job、调用预算、收据、缓存、WAV/MP3/SRT 与本地修复 |
| 原会话恢复 | `harness_resume` 及宿主模块 | 自动登记原会话、保存 Answer 后通知、去重与失败回退 |
| CLI | `cli`、`__main__`、`service`、`jobs`、`offline_harness` | 配置命令与已有契约兼容 |

`production` 是明确授权的生成入口。裸 `Generation(core)` 默认没有 MiniMax 适配器；不能将其当作真实合成入口。`media` 只处理本地文件，不下载或安装软件。

## Skill 分层

```text
skills/soundmaker-dubbing/
  SKILL.md                         # 共用流程与确认阶段
  references/
    workflow-api.md                # 固定调用、V1.6 默认设置与统一正式 review
    voice-selection.md             # 候选、试听、绑定及同一份完整 items 复用
    studio.md                      # 实际开网页时才读取
    native-audio/                  # 内置路径只读当前应用
    minimax.md                     # 模型能力、参数、执行与错误处理
    performance-plan.md            # 演绎单与直接请求契约
    delivery-layout.md             # 任务与版本交付目录
    revision-and-recovery.md       # 局部修订、计费未知与本地修复
    harness-resume.md              # 恢复的共用规则
    harnesses/
      codex.md
      claude.md
      workbuddy.md
      doubao.md
      kimi.md
```

主文件只决定配音流程；厂商参考规定实际可执行参数；宿主参考只规定启动、身份和恢复机制。所有宿主读取同一份主 skill，不能为修复某个应用而复制另一套配音规则。

## 宿主恢复

| 宿主 | 当前路径 | 主要限制 |
|---|---|---|
| Codex | 原聊天 queue | 入队不证明模型已执行 |
| Claude Code | 当前进程继承的原生消息地址和令牌 | 管道写入记为 sent_unconfirmed；不得复制其他会话凭据 |
| Claude App Cowork | 独立 skill 入口；主机常驻本地 MCP 持有网页，通过原 MCP 请求返回 Answer | Windows App 的 Fake 网页绑定与原请求继续已实测；不能唤醒已结束的对话，不提供合成 |
| WorkBuddy | 宿主受管理后台任务与 TaskOutput | 必须在同一轮等待任务；桌面完整续跑仍需验收 |
| 豆包工作 | Windows 本机实例桥接 | 依赖版本与临时本机调试端口；不得强杀应用或切换云端权限 |
| Kimi Work | 当前实例鉴权 WebSocket 控制通道 | 要求唯一原会话匹配；实例变化拒发，不按最近聊天猜测 |

共用规则为保存 Answer 后通知，按 Question/Answer 去重，未知投递结果不盲目重发。通知没有付费权限；恢复后仍须执行角色试听与演绎单确认。版本适配细节保留在各自的 skill 参考中。

`claude_cowork` 只针对显式核实的本地插件目录安装开发链接与 user/syncManaged=false 清单项，保留精确备份、拒绝覆盖副本；不会扫描目录、上传账号或修改应用校验。`claude_native --surface` 只诊断本命令继承的身份，Code/Cowork 可核对，普通聊天不假定支持。诊断不连接传输或输出消息凭据，available 与 receiver_verified=false 同时返回，避免把存在环境变量写成自动续跑成功。

`--completion-mode tool-result` 显式登记 Question 为工具结果返回任务，不依赖 workspace 服务继承 App 环境变量，不借用/伪造聊天身份。网页持久化 Answer 后记 awaiting_tool；`cowork_task` 核对 Question、目标、Answer 和回执，并以独占锁限制一个活动等待者，结果经请求它的工具调用返回，不广播。这不是聊天鉴权，有项目读取权限的其他请求仍可主动读取任务；原有继承式指纹路径仅保留兼容。每次等待不超过 55 秒，超时返回 waiting，原请求仍有效才继续同一等待。重复领取不发外部消息、不重复提交 Answer；模型实际继续仍需实机证据。此路径的 HTTP/命令结果不是关闭会话后的外部唤醒能力。

`host_bridge/` 是独立于业务的通用任务桥接核心，不导入 makesound。它提供 host_bridge_status/start/wait/read；由启动方显式传入应用对象，接口为 start(operation, payload, request_id)、wait(handle, timeout, cancel_event)、read(resource)、close()。核心维护进程内句柄、请求幂等、单活动等待、取消和 JSON-RPC 路由；不理解角色、音色、Question 或合成，不根据工具参数动态导入模块/执行 shell。其他应用只需实现同一接口，无需改桥接核心；当前交付的真实适配器为 SoundMaker，普通表单适配器有隔离测试。

应用协议 1.0 统一结果状态、业务 data、错误、任务版本和网页提交；详见[通用桥接接入文档](host-bridge-integration.md)。`protocol.py` 校验数据，`tasks.py` 提供 SQLite 事务与提交去重，`http.py` 提供同源本机参考服务，`example.py` 为独立普通表单。新调用显式传 protocol_version，旧调用保持原输出。SoundMaker 在适配层映射旧 Answer，附加标准提交端点，旧网页接口与存量数据不迁移。

`makesound.host_application.SoundMakerApplication` 是业务适配器，复用 `claude_host_bridge.Bridge` 的绑定页和数据规则；后者保留旧六工具入口供已安装用户兼容。新安装仅登记 `host_bridge` 通用服务，显式启用 soundmaker 适配器，不同时登记两套 MCP。应用负责允许目录、持久化和操作权限，桥接负责请求传输。每个绑定页的回环 HTTP server 与线程由应用持有，长等待不阻塞 ping；MCP 关闭时释放页面，保留磁盘结果。handle 只在当前进程有效，重连由 read(resource) 读取应用保存的结果，不自动创建业务修订。

`claude_install` 合并 skill 链接与 MCP 安装。仅安装时检查固定 App 配置位置及 skills-plugin 的两级账号目录；多候选不猜测，也不在普通配音中搜索安装目录。`claude_host_setup` 复用原字节备份与冲突保护；只有完全匹配本仓库、当前解释器、原项目根目录的旧配置才能自动迁移，异源条目保留并报告冲突。新用户默认 ~/Documents/SoundMaker/projects，已有可识别配置沿用原根目录。安装成功与 App 加载/模型继续分别验证，不重启或强制关闭 App。

Windows Claude App 于 2026-10-18 完成 Fake 端到端实测：真实本地 MCP 连接、主机网页打开、用户提交绑定、原请求取得 Answer 并继续报告；落盘结果与报告匹配，未生成音频。该证据对应原专用入口；新的通用工具入口需重新做 App 实机验收，不能由兼容测试通过推定。重连读取、取消、并发隔离和 RPC 请求 ID 返回另有自动化覆盖，不能将这些自动化项一并标为 App 实机通过。其他平台和旧 VM 项目迁移仍需单独验证。

## 界面状态与语言

`ui_locale` 在启动器与持久化服务间传递规范化 `zh-CN` / `en`，通过 session 模块交给前端。Agent 按主 Skill 将当前回答主语言显式传入 `--ui-language`；后端不解析聊天、不读取宿主 UI 设置。前端 `i18n`、语言字典和 `locale-control` 负责翻译及手动切换；用户文本保留原文，插值不作为代码或翻译键求值。

默认草稿保存在 store，完成操作存在变更时先确认、保存，再用新 revision 提交 Answer。保存失败不通知，提交失败保留已经保存的默认。语言切换重建视图并保留 store 中草稿，忙碌或确认处理中禁止切换；同源手动偏好优先于启动语言，未提供语言时中文。

## 发布内容

运行时、skill、网页、必要静态资源、测试源代码、示例和公开文档可发布。`doc/` 中的 PRD、`docs/` 中的内部过程材料、`archive/`、`wireframes/`、`.makesound/`、`outputs/`、生成交付与配置凭据留在本地。`.gitignore` 对公开文档使用明确白名单，避免未来报告被误加入。


## 正式演绎与交付一致性

推荐路径最终绑定后，一份完整 final-items 供 `final_delivery.review` 推导复用目标和正式批次，再经原有确认、冻结及厂商授权执行。`emotion` 说明不等于请求参数；写入已知情绪代码却未映射到 provider_directives 时拒绝，防止 calm 静默变为自动。旧 targets 只保留兼容入口。

`final_delivery.publish` 只读取已成功且内容、绑定、实际情绪/控制一致的 Job/已选试听，并校验音频哈希和可信 speech_seconds。分句去除记录中追加的段后静音，合并仅插入一次确认停顿，完整版本保留实际演绎、字幕缺失状态、来源映射和索引；不调用厂商、不改冻结记录、不隐式重采样或覆盖旧交付。


## macOS 基础配置边界

`studio_config_editor` 根据平台选择记事本或 macOS `/usr/bin/open -t` 文本编辑器；模板路径与现有 `~/.config/<provider>/config.json` 不变，打开失败不覆盖或删除文件。`media` 检查 Python 3.11+，先复用 PATH，再按平台查固定已有工具位置；Mac 只核对 `/opt/homebrew/bin`、`/usr/local/bin` 的可执行 ffmpeg/ffprobe 配对，不调用包管理器。定位脚本对版本过低返回 python_unsupported，避免误诊运行时丢失。

平台基础 CI 覆盖 Windows/macOS 与 Python 3.11/3.13，Mac 原生冒烟测试检查链接、文件锁及后台 Studio 的 POSIX 启停。编辑器 GUI、真实 MiniMax 听感和各宿主原聊天自动恢复仍需真实 Mac 验收，工作流文件存在不代表已经跑过。此次不改变全局数据位置、不迁移项目、不绕过受管理路径保护。
