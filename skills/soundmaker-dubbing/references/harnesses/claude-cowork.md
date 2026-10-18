# Claude Cowork：主机网页绑定与原请求继续

仅选项 1/2 实际需要打开网页，且当前明确为 Cowork 时读取；选项 3 不走本适配。不读取 Code 或其他宿主说明，不重复加载主 skill。聊天选声无需网页时不读本文件。

## 使用主机桥接

网页和项目由主机上的应用适配器持有；通用 host_bridge MCP 只路由任务和返回结果。不用 VM Bash 启动服务器、定位 Python 或读取主机项目文件。以当前实际可调用 schema 为准，工具名可能带宿主前缀。

| 工具 | 用途 |
|---|---|
| host_bridge_status | 核对 execution_environment=host，applications 包含 soundmaker |
| host_bridge_start | application=soundmaker，传 operation、稳定 request_id 和 payload |
| host_bridge_wait | 原样调用返回的 wait_tool，在原请求等待结果 |
| host_bridge_read | application=soundmaker，resource 传已知项目和 Question 标识，读已保存结果 |

SoundMaker 的 operation 与 payload：prepare_binding 传 project_key、script、可选 root_index/ui_language；open_binding 传 project_key、question_id、可选 root_index/ui_language；smoke_binding 仅传可选 ui_language。request_id 放在 start 顶层。普通任务不使用 smoke。read 的 resource 为 project_key、question_id 和可选 root_index。桥接本身不理解这些业务字段；由 SoundMaker 适配器验证、启动页面和保存绑定。

兼容旧安装：仅当当前 schema 仍只暴露 soundmaker_host_status、soundmaker_prepare_binding、soundmaker_open_binding、soundmaker_read_binding、soundmaker_wait_binding、soundmaker_smoke_binding 时，按实际旧 schema 直接调用；不同时调用两套、不为升级自动重配。新版优先使用通用工具。

桥接只提供绑定工具，没有合成、任意 shell 或读取凭据入口。project_key 是配置范围内的逻辑项目名，如 macbeth；不是 Windows/VM 路径。project_key、request_id 只能包含字母、数字、下划线、连字符。request_id 对同一次原稿保持不变；相同请求重试复用 Question，原稿不同却复用该 ID 会拒绝，不能换 ID 掩盖未确认的内容变化。

用户只要求管理声音库而没有任务时，当前桥接没有独立管理工具就报告该入口缺口，不伪造角色或 Question。已授权的绑定验收直接执行 smoke 工具，不重复询问是否继续；该授权不延伸到生成音频。

若工具尚不可用，只报告“主机 MCP 尚未连接”，说明需要重连本地 MCP、重新加载 App 或新建 Cowork。不能自行回退到 VM 冒烟、pip/uv 安装、原生身份检查、目录扫描或源码排查。安装配置成功与当前会话实际加载是两个状态；不伪造工具名或 URL。

## 打开当前任务

新主机任务调用 host_bridge_start（application=soundmaker、operation=prepare_binding），顶层传稳定 request_id，payload 传 project_key、原始 script（roles、segments 与可选 role_metadata），ui_language 按当前回答语言选 zh-CN/en。保留已有角色和原句 ID，不虚构配音任务。修改已知主机 Question 时使用 operation=open_binding，不重复 prepare。记录返回的 project_key、host_project_id、实际 question_id、handle 和 URL；修订以实际新 question_id 为准。

VM 旧任务不能靠更换路径由主机加载：project_id 与规范化绝对路径绑定。用户已授权网页绑定时，可沿用原稿和角色 ID 建立主机侧绑定副本，说明旧 VM 数据保留；不静默迁移旧音色/缓存，不手改项目 ID。其他有权限的主机项目也不能超出安装时配置的根目录。

先向用户展示返回的真实主机 URL；有实际浏览器导航能力才打开，否则给可点击链接。web_fetch 拒绝本地/私有地址不表示服务器失败，不再枚举 IP、端口、进程，也不改成 0.0.0.0。页面由主机 MCP 持有，在工具调用之间持续存在；本地 MCP 关闭会关闭它持有的页面服务，磁盘数据保留。

## 等待与继续

展示网页后，在当前 Cowork 请求调用返回的 wait_tool（host_bridge_wait；旧安装以实际返回名为准），原样传 handle 与 timeout。默认每次等 50 秒、上限 55 秒；宿主工具超时应大于等待时长。waiting 时继续同一 handle，不新开服务、不重做任务；用户暂停/结束或宿主取消时停止等待，结果保留。不能将 wait_tool 改成 VM Bash 命令，不能把返回的主机路径改写成 VM 路径。

binding_saved 包含实际 question_id、answer_id 和完整 answer。直接使用该真实 Answer 准备下一步演绎审阅，复用已认可且实际参数未变的试听，仅处理未完成或受影响部分；不再在 VM 运行配方 C 读取主机项目。结果重复读取保持同一 Answer，业务层避免重复处理。绑定保存不代表演绎确认或付费授权，本桥接不会生成音频。

结果只沿发起 wait 的 MCP 请求 ID 返回，不广播、不向另一窗口发外部消息。同一 Question 只允许一个活动等待；这不是聊天身份鉴权，持有相同项目权限和 handle 的其他请求仍可主动读取。handle 只在本地 MCP 进程存活期间有效；重连后用已记录 project_key/question_id 直接读取结果，不能搜索“最近会话”。agent_resumed=false 表示桥接不能证明模型已回复，不能改口宣称完成实机验收。

此机制延续仍在等待的原请求，不能唤醒已经结束的对话。若等待已结束，用户回原聊天说“完成了”后，调用 host_bridge_read，application=soundmaker，resource 传保留的 project_key/question_id（多根目录时同时保留 root_index），直接读真实 Answer；不能为读取结果调用 open_binding 创建修订，不能重复创建任务或重新绑定。

## 无付费验收

1. 调用 host_bridge_status，确认 execution_environment=host 且 soundmaker 已登记。
2. 调用 host_bridge_start，application=soundmaker、operation=smoke_binding、payload={}、稳定 request_id；展示返回 URL。
3. 调用返回的 wait_tool，用户在网页给 Fake 角色选声音并完成；waiting 则继续等待。
4. binding_saved 后报告实际 Question/Answer ID 和已保存选择，停止，不生成音频。

第二窗口不应收到主动通知，并发等待同一任务应被拒绝；客户端取消等待不删除 Answer。当前请求无需检查 VM Python、安装 uv、运行 scripts/claude_binding_smoke.py 或读取源码。自动化测试通过与真实 Cowork 看见工具、点击网页后继续回复分别报告。

## 安装与范围

安装命令见[使用说明](../../../../docs/usage.md)。主机仓库执行 python -X utf8 -m makesound.claude_install，一次连接 skill、配置通用 host_bridge 并登记 SoundMaker 适配器。仅安装时检查固定 App 配置位置；多账号要求显式选择。普通配音 Agent 不执行安装、不读取配置或凭据定位宿主；缺连接就报告缺口。

skill 的目录链接只负责加载规则。Cowork 的 skill 目录与 Code 的 ~/.claude/skills 不同；已有链接/启用登记不证明 MCP 已连接。宿主升级后若拒绝链接或本地 MCP，遵守其权限与策略，不修改校验或开放公网端口。

原专用桥接的 Windows Claude App 主机连接、网页 Fake 绑定和原请求后续报告已于 2026-10-18 实测通过；通用工具入口另有自动化回归，尚需 App 重连后实测，这不扩展到付费生成、其他平台或已结束聊天的唤醒。取消/重连等其余边界按实际测试证据分别说明。

## 接入协议兼容

本说明现有调用省略 protocol_version 时保留旧业务输出，旧绑定网页继续工作。新建其他 Skill 的适配器时按[通用桥接接入协议](../../../../docs/host-bridge-integration.md)使用显式 1.0、统一 data/error 和网页提交；仅开发接入时读取，不在普通配音中额外加载。
