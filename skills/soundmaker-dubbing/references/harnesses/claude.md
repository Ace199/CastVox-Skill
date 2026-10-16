# Claude Code 原聊天恢复

本适配针对 Claude Code 的原生会话消息机制。已在 Windows Claude Code 2.1.295 验证；其他 Claude App 模式、版本和平台不可据此推断。个人 skill 目录为 `~/.claude/skills`，目录可读与消息恢复是两个独立条件。

## 登记与启动

从发起绑定的 Claude Bash 工具运行仓库的 `python -m makesound.studio_session --project <absolute-project-path> --question <qid>`，继承自己的 `CLAUDE_CODE_MESSAGING_SOCKET` 和 `CLAUDE_CODE_MESSAGING_TOKEN`。不得复制另一会话的地址或令牌，不打印凭据。多个 Harness 身份冲突时拒绝猜测；复用旧服务前必须核对它属于当前身份。

启动器通过 `makesound.claude_native` 自动登记。Windows 使用 named pipe；其他平台的传输仍需对应环境验证。令牌只通过进程环境继承，任务记录保存地址和指纹，不保存令牌本身。

## 完成与失败恢复

网页先保存 Answer，再写入原会话消息。原生管道写入状态为 `sent_unconfirmed`，不是接收或模型回复的确认。原会话收到后核对项目、Question、Answer，读取绑定快照并按主 skill 准备角色试听单；消息不代表付费授权。

重复提交不重复通知，目标不匹配、已关闭或未知发送结果时保留 Answer，不盲目重发。用户可回原聊天说“完成了”恢复。不能用 `claude --resume` 启动另一进程冒充原会话恢复，不能改接收权限绕过拒绝。

## Channels 备用路径

仓库保留 `claude_channel.py` 与 `scripts/claude_soundmaker_channel.py` 的 Channels 原型。它要求目标会话实际加载并启用相应 channel；普通 MCP 连接不代表可接收推送。默认优先原生消息路径，不自动安装或启用备用配置。

原生消息机制参考 [Claude Code cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging)。实际兼容性需在目标安装版本核验，不能从目录链接推断消息能力。
