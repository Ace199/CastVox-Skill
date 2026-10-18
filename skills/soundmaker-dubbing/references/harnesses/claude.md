# Claude Code 原聊天恢复

仅选项 1/2 实际需要网页且当前宿主匹配时读取；选项 3 的内置音频生成不触发本适配。网页入口与保存后业务路由沿用已读的 [Studio](../studio.md)，不重复加载主 skill 或其他宿主说明。

启动命令使用当前任务 Question；已有角色不得省略 Question 打开空角色管理页。启动器可能因已绑定而返回新 question_id，后续完成事件、Answer 读取使用实际新 ID；保留原启动命令用于会话归属核对，不手工改写历史命令。仅管理声音库时省略 question，不创建假 Question，也不通知绑定完成。

本适配针对 Claude Code 的原生会话消息机制。已在 Windows Claude Code 2.1.295 验证；其他 Claude App 模式、版本和平台不可据此推断。个人 skill 目录为 `~/.claude/skills`，目录可读与消息恢复是两个独立条件。

Claude App 的 Code 本地会话按本文件核对；Cowork 使用 Studio 中的独立入口，不连带读取两份说明。首次诊断可在原 Code 命令工具执行 `python -X utf8 -m makesound.claude_native --surface code`：available 只证明继承了消息身份，尚未验证接收/回复；正常启动不强制重复检查。

## 登记与启动

从发起绑定的 Claude Bash 工具运行仓库的 `python -m makesound.studio_session --project <absolute-project-path> --question <qid>`，继承自己的 `CLAUDE_CODE_MESSAGING_SOCKET` 和 `CLAUDE_CODE_MESSAGING_TOKEN`。不得复制另一会话的地址或令牌，不打印凭据。多个 Harness 身份冲突时拒绝猜测；复用旧服务前必须核对它属于当前身份。

启动器通过 `makesound.claude_native` 自动登记。Windows 使用 named pipe；其他平台的传输仍需对应环境验证。令牌只通过进程环境继承，任务记录保存地址和指纹，不保存令牌本身。

## 完成与失败恢复

网页先保存 Answer，再写入原会话消息。原生管道写入状态为 `sent_unconfirmed`，不是接收或模型回复的确认。原会话收到后核对项目、实际 Question、Answer，按 Studio 的配方 C 读取结果，检查已有试听，revision 比较变更，仅处理未完成或受影响内容；不强制重新试听，消息不代表付费授权。

重复提交不重复通知，目标不匹配、已关闭或未知发送结果时保留 Answer，不盲目重发。用户可回原聊天说“完成了”恢复。不能用 `claude --resume` 启动另一进程冒充原会话恢复，不能改接收权限绕过拒绝。

## Channels 备用路径

仓库保留 `claude_channel.py` 与 `scripts/claude_soundmaker_channel.py` 的 Channels 原型。它要求目标会话实际加载并启用相应 channel；普通 MCP 连接不代表可接收推送。默认优先原生消息路径，不自动安装或启用备用配置。

原生消息机制参考 [Claude Code cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging)。实际兼容性需在目标安装版本核验，不能从目录链接推断消息能力。
