# 绑定完成后的原聊天恢复

启动网页前识别 Harness。Codex 当前实现见 [Codex](harnesses/codex.md)。Claude 接入与验收见 [Claude](harnesses/claude.md)，腾讯 WorkBuddy 见 [WorkBuddy](harnesses/workbuddy.md)，豆包 Windows 2.32.5 的临时本机桥接见 [豆包](harnesses/doubao.md)。Claude 原生适配器已通过本地管道、HTTP 及 Windows 原会话自动绑定→网页完成→回复实测；WorkBuddy 桌面端仍待验收。不能因同品牌或支持 MCP 就推断它们能唤醒原聊天。

Kimi Work 3.2.8 已通过自动登记、网页绑定完成和原会话继续执行测试，详见 [Kimi](harnesses/kimi.md)。其他模式与版本仍须验证。

统一规则：先持久化 Answer，再通知发起绑定的原会话。通知仅表示绑定完成，不表示演绎单已确认或允许付费合成。Agent 收到事件后核对项目、Question、Answer，读取已保存结果，按厂商文档生成待审阅演绎单；已处理的 Answer 不重复执行。

Codex 确认入队才显示已发送；入队不等于 Agent 已运行。Claude 原生管道写入使用 sent_unconfirmed，页面明确尚未确认接收或回复。WorkBuddy 改用受管理任务续跑：打开网页后须在同一轮等待 TaskOutput；awaiting_task 表示保存后交给任务返回，不能写成已向桌面聊天发消息。旧 delivered 仅证明引擎执行，真实测试中桌面丢弃了这些输出。通知失败或结果不明时保留 Answer，提示用户回原聊天发送“完成了”。网页随后可以关闭。未知发送结果不得自动重发。无 Harness 支持时仍可完成绑定，不阻断保存。
