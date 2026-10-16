# Kimi Work 原聊天恢复

核查版本：Windows Kimi App 3.2.8，2026-10-16。适配 Work 模式，不是普通 Chat 或独立 Kimi Code CLI。通过运行中实例的本地鉴权 WebSocket JSON-RPC `conversations.send` 通知原会话，不启动另一会话冒充恢复。

## 自动登记

由发起任务的 Kimi 自己通过 Bash 执行 `python -m makesound.studio_session --project <当前项目绝对路径> --question <本次Question>`。先创建 Question，再将返回的实际 ID、项目路径直接写入独立的启动命令。不要把准备与启动包在另一个脚本里；否则工具记录中没有可核对的启动参数。

要求继承 `KIMI_AGENT_CLIENT_ID=kimiwork` 和 `KIMI_SHARE_DIR`。启动器只读该实例的 conversation 索引及末尾最多 2 MiB wire，要求项目相同，并且唯一未完成 Bash/Shell 工具调用中的启动参数匹配本次 Question。不按最近、活动聊天或仅项目相同猜测目标。无匹配、多匹配、参数无法识别、同时存在其他 Harness 身份时拒绝登记。

目标按 Question 固定，保存准确 conversationKey、实例 generation、控制地址、令牌指纹和运行时路径。令牌只即时读取本地 lock，经过 stdin 传输，不写入网页、任务或回执。Kimi 重启后实例身份改变则拒发，不改投新会话。登记失败时修正原会话启动方式，或保留人工“完成了”恢复。

## 完成通知

网页先保存 Answer，再调用统一 notify。只在收到 `accepted=true`、相同 agentId/conversationKey 和 turnId 后报告 queued；它不证明模型已回复。重复通知读取回执，不再次发送；断开、超时或未知结果不盲目重试。关闭会话、接口拒绝或实例变化时保留 Answer。恢复事件不代表演绎单确认或付费授权。

## 兼容范围

已在 Windows Kimi Work 3.2.8 验证绑定保存后原会话继续执行；测试使用假音色，不代表真实配音听感验收。其他版本、macOS、独立 CLI、第二个真实窗口隔离和重启后的完整交互未验收。接口和状态目录属于版本相关实现，不承诺是官方稳定公共 API，升级后需复验。
