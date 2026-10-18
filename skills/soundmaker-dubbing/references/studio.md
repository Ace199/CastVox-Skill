# Studio：仅打开网页时读取

本文件只用于选项 1/2 的项目网页。选项 3 不因角色描述或内置工具失败而读取本文件；用户另行明确要求查看既有项目或切换路径时才进入网页流程。

聊天推荐、绑定或生成不读本文件，也不读任何宿主网页恢复说明。只在实际需要网页时，根据当前会话已知上下文选择下表一份；未知时只问宿主身份，不扫描配置/历史或逐项打开。已读当前宿主且未变化时直接沿用，不再次打开索引或其他宿主说明。

| 当前宿主 | 只读这一份 |
|---|---|
| Claude Code / Claude App 的 Code 本地会话 | [Claude Code](harnesses/claude.md) |
| Claude App 的 Cowork 会话 | [Claude Cowork](harnesses/claude-cowork.md) |
| Codex | [Codex](harnesses/codex.md) |
| WorkBuddy | [WorkBuddy](harnesses/workbuddy.md) |
| Kimi Work | [Kimi](harnesses/kimi.md) |
| 豆包 | [豆包](harnesses/doubao.md) |

进程、后台任务、等待与原会话通知按该宿主说明；共用恢复确有需要才查 [恢复索引](harness-resume.md)，不因此读取其他宿主。用户不负责启动终端、选端口或查任务 ID。

Claude App 普通聊天不因应用名相同而读取 Code/Cowork 两份说明；先核对是否实际具备本地命令和文件访问能力，缺少时说明项目流程尚不可执行，不在云端创建指向本机的假绑定页。

## 按当前任务决定网页入口

用户说“先等一下/先看网页”立即暂停生成推进，不继续 propose/ask/执行原授权。已有明确任务和角色时，“重新打开网页/文件”默认打开当前绑定任务，显示角色及已有值，允许继续修改；不要误路由到空角色的项目声音库。只有明确要管理项目声音库或确实无当前任务时，才省略 question。

Cowork 按已选宿主说明调用主机 MCP，不执行下面的 VM/本地 CLI；主机工具已返回的真实 Answer 直接沿用，不跨环境执行配方 C。以下命令用于其他说明确认能在同一运行时启动的宿主（占位值换真实值）：

```text
python -m makesound.studio_session --project "<absolute-project-path>" --question "<current-question-id>" --ui-language zh-CN
```

- 当前 Question pending：打开原任务，保留草稿，不重复 prepare。
- 当前 Question answered：启动器自动创建预填旧 Answer 的 binding revision 并打开，返回实际新 question_id；从旧 ID 重开会追到最新已提交版本再准备草稿，后续读取/保存使用返回的新 ID。准备 pending 新版本仅供查看/修改，不修改已生效绑定、不表示确认变更、生成许可或付费。
- 仅管理库：使用 `python -m makesound.studio_session --project "<absolute-project-path>" --ui-language zh-CN`，无需假任务或通知目标。

始终打开返回的实际 URL，不假定端口；启动器核验 HTTP 与目标任务，可复用已验证会话。不能把 `answer_immutable` 解释为声音不能再改；旧 Answer、冻结任务和音频不可覆盖，用户通过新版本修改。保存库卡片本身不改旧绑定快照。

用户仅要求打开网页时，浏览器导航返回成功即可交付链接和当前角色摘要，不为复述已知绑定而抓取整页卡片/完整可访问性树；角色摘要复用真实 Question/Answer。只有页面异常或用户要求检查界面时才做必要的局部检查，不分页读取数万字符的整页快照。

## 语言、等待与恢复

每次启动传 ui-language：按当前对用户的主要解释语言，中文（含繁体）用 zh-CN，英文用 en，不依原稿或系统区域推断；用户显式要求优先，网页手动/保存语言最高优先，切换保留草稿。

保持服务可用供用户绑定/试听；磁盘音频保留，关闭后网页播放需重新启动，不需重合成。绑定模式保存 Answer，管理模式只保存库设置；两者都不生成演绎单或调用厂商。按宿主机制等待，不忙轮询；保存后通知是尝试而非保证，通知不等于生成授权。无接收证据时说“完成后将尝试通知”；未确认通知则保留结果，提示回原聊天说“完成了”，不盲目重发。

收到完成事件按 [配方 C](workflow-api.md#c-绑定完成后读取原结果) 读取真实 Answer；是 revision 时按 [修订与恢复](revision-and-recovery.md) 比较变更，仅审阅受影响句子。用户只是查看或没有保存时，不自动重绑、不恢复旧授权执行；需用户明确继续。回环/进程受限遵守宿主权限要求，不用计划任务绕过。
