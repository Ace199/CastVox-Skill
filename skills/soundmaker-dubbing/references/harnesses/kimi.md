# Kimi Work 原聊天恢复

仅选项 1/2 实际需要网页且当前宿主匹配时读取；选项 3 的内置音频生成不触发本适配。网页入口与保存后业务路由沿用已读的 [Studio](../studio.md)，不重复加载主 skill 或其他宿主说明。

启动命令使用当前任务 Question；已有角色不得省略 Question 打开空角色管理页。启动器可能因已绑定而返回新 question_id，后续完成事件、Answer 读取使用实际新 ID；保留原启动命令用于会话归属核对，不手工改写历史命令。仅管理声音库时省略 question，不创建假 Question，也不通知绑定完成。

核查版本：Windows Kimi App 3.2.8，2026-10-16。适配 Work 模式，不是普通 Chat 或独立 Kimi Code CLI。通过运行中实例的本地鉴权 WebSocket JSON-RPC `conversations.send` 通知原会话，不启动另一会话冒充恢复。

## 自动登记

以下会话登记与完成通知用于带 Question 的绑定页；仅管理库按 Studio 省略 question，不要求匹配绑定命令或登记通知目标。

由发起任务的 Kimi 自己通过 Bash 执行 `python -m makesound.studio_session --project <当前项目绝对路径> --question <本次Question>`。已有任务沿用当前 Question；仅确实没有任务且需要角色绑定时才创建 Question。将当前 ID、项目路径直接写入独立的启动命令。不要把准备与启动包在另一个脚本里；否则工具记录中没有可核对的启动参数。

该命令在前台短暂运行，内部隐藏启动服务、验证就绪后返回 URL；不等待用户绑定，不需要另开终端、手工后台化或读源码判断生命周期。Windows 虚拟环境的后台服务优先使用同目录 pythonw.exe，日志仍写入本任务 Studio 目录。打开网页前按当前宿主浏览器工具实际 schema/必需说明执行，不猜测 action 名。

要求继承 `KIMI_AGENT_CLIENT_ID=kimiwork` 和 `KIMI_SHARE_DIR`。启动器只读该实例的 conversation 索引及末尾最多 2 MiB wire，要求项目相同，并且唯一未完成 Bash/Shell 工具调用中的启动参数匹配原启动 Question；自动创建 revision 后也不能把原工具调用中的旧 ID 改写为新 ID。不按最近、活动聊天或仅项目相同猜测目标。无匹配、多匹配、参数无法识别、同时存在其他 Harness 身份时拒绝登记。

目标按 Question 固定，保存准确 conversationKey、实例 generation、控制地址、令牌指纹和运行时路径。令牌只即时读取本地 lock，经过 stdin 传输，不写入网页、任务或回执。Kimi 重启后实例身份改变则拒发，不改投新会话。登记失败时修正原会话启动方式，或保留人工“完成了”恢复。

## 完成通知

网页先保存 Answer，再调用统一 notify。只在收到 `accepted=true`、相同 agentId/conversationKey 和 turnId 后报告 queued；它不证明模型已回复。重复通知读取回执，不再次发送；断开、超时或未知结果不盲目重试。关闭会话、接口拒绝或实例变化时保留 Answer。恢复事件不代表演绎单确认或付费授权。收到事件后按 Studio 的配方 C 读取实际 Answer，检查已有试听，revision 比较变更，仅处理未完成或受影响内容，不强制重新试听。

## 兼容范围

已在 Windows Kimi Work 3.2.8 验证绑定保存后原会话继续执行；测试使用假音色，不代表真实配音听感验收。其他版本、macOS、独立 CLI、第二个真实窗口隔离和重启后的完整交互未验收。接口和状态目录属于版本相关实现，不承诺是官方稳定公共 API，升级后需复验。
