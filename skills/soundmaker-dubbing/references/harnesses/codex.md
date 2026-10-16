# Codex 原聊天唤醒

2026-10-16：本机 codex-cli 0.149.1 已实测 codex queue 成功入队，并在原 Codex 桌面聊天触发下一轮回答。网页集成已实现；新会话完整实操待验收。

## Agent 启动绑定
使用 SoundMaker 仓库的 `python -m makesound.studio_session --project <绝对项目路径> --question <qid>`。
启动器自动读取 CODEX_THREAD_ID，保存本次 Question 对应的唤醒目标。环境变量缺失时，只有已可靠获得当前聊天 UUID 才传 `--codex-thread <原聊天UUID>`；不能用项目 ID、Question 的 harness_session_id 或其他会话 ID 代替，不能猜测。不得把测试聊天 ID 硬编码进 Skill。Windows 启动及队列发送须处于允许本机进程通信的宿主环境。

## 完成按钮
只有启动器创建的带 Question 的一次性绑定页会发送通知。保存 Answer 成功后调用 makesound.harness_resume.notify，运行 codex queue --thread <原聊天UUID> --message <绑定完成事件>，然后返回网页回执并停止一次性服务。管理模式的完成按钮不发送。
消息包含项目路径、Question ID、Answer ID，并明确只继续制作待审阅演绎单。不发送密钥、整份配置或音频。通过参数数组调用，不使用拼接 shell 命令；npm Windows shim 通过 Node 执行对应官方入口。

## 配置兼容及失败恢复
若配置 features.context_management 为对象，本机旧 CLI 解析不兼容，适配器只在本次命令传 -c features.context_management=false，不改写配置文件。
目标保存在 .makesound/studio/<qid>/wake-target.json，发送回执为 wake-receipt.json。同一 Question 不允许改投其他聊天；重复通知读取回执，不再次发送。queued 仅代表命令成功；dispatching/unknown 表示可能已投递，禁止盲目重试。CLI 缺失、命令失败时显示手动恢复提示，不丢失绑定。

参考：[codex-wake-run](https://github.com/ZardLi1115/codex-wake-run)。本项目使用已验证的 queue 命令，不依赖安装该第三方项目。
