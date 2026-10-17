# 网页绑定恢复索引（到网页步骤才读取）

仅选项 1/2 准备打开绑定/管理网页，或正在处理该网页恢复问题且需要共用说明时，才使用本索引。Studio 已提供宿主入口，不要求额外读取本索引；已读当前宿主说明不重复读取。选项 3 内置生成不触发此索引。按已知当前宿主只选下面的一份，不逐一打开；未知宿主只补问身份，不扫描源码或凭据来识别。

| 当前宿主 | 对应说明 |
|---|---|
| Claude Code | [Claude](harnesses/claude.md) |
| Codex | [Codex](harnesses/codex.md) |
| WorkBuddy | [WorkBuddy](harnesses/workbuddy.md) |
| Kimi Work | [Kimi](harnesses/kimi.md) |
| 豆包 | [豆包](harnesses/doubao.md) |

各宿主的启动、等待、通知状态和兼容性证据仅在对应文档维护，不从品牌、目录链接或 MCP 连接推断恢复能力。

共用规则：先持久化 Answer，再尝试通知发起网页的原会话。通知只表示绑定保存，不代表演绎单确认或付费授权。当前任务有角色时携带 Question；启动器返回 revision 新 ID 时，事件与后续 Answer 读取以实际 ID 为准，原启动命令保留供会话归属核对。收到事件后按已读 Studio 的配方 C 核对并读取真实结果，检查已有试听，revision 比较变更，仅处理未完成或受影响内容，不强制重做试听。未知发送结果不盲目重试；失败时保留 Answer，提示回原聊天说“完成了”。管理模式没有待回答 Question 时只保存管理结果，不伪造恢复事件。
