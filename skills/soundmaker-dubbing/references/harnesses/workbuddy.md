# WorkBuddy：通过受管理任务续跑

核查版本：腾讯 WorkBuddy 5.8.3，日期 2026-10-16。当前使用宿主 TaskOutput 续跑，不使用直接调用模型引擎来冒充桌面新一轮聊天。真实界面仍待按下述新流程验收。

## 发起与等待

1. 发起聊天的命令环境自动提供 `WORKBUDDY_CONFIG_DIR` 和 `CODEBUDDY_SESSION_ID`。`makesound.workbuddy_task` 将 Question 绑定到该会话，不需要网关密码；多 Harness 身份拒绝猜测。
2. 在 SoundMaker 仓库，以 WorkBuddy 自身命令工具的 `run_in_background: true` 运行 `python -m makesound.studio_session --project <目标项目绝对路径> --question <qid>`。CLI 在受管理任务进程中运行实际绑定服务，不创建脱离子进程。
3. 读取任务实时输出，得到 URL 后立即打开。**打开网页后，在同一轮聊天继续调用该任务的 TaskOutput，使用 block=true 等待。返回 running 时继续等待同一任务，不结束当前回复，不要求用户发“完成了”来触发正常续跑。** 等待调用按宿主允许的有限超时执行，不用一个无限超时命令。
4. 用户网页提交后先保存 Answer，再记录 `awaiting_task`，处理 HTTP 回执并结束后台服务。TaskOutput 返回 `binding_saved`、项目、Question 和 Answer ID。Agent 从这些明确标识读取 Answer，在原聊天正常生成待确认演绎单；先查是否已处理，不重复生成。输出不是付费合成授权。

网页等待期间不要等待进程退出才开 URL。不要用 nohup、尾随 &、计划任务或 Windows Job breakaway。Python API 的脱离式 `start()` 对 WorkBuddy 返回 `managed_launch_required`。

`awaiting_task` 只表示 Answer 已交给受管理任务返回，不证明宿主已取回或模型已回复。若宿主取消/丢失等待任务，保留 Answer，并允许用户在原聊天说“完成了”进行人工恢复。正常流程应一直等待 TaskOutput。

## 兼容与诊断

个人 skill 目录为 `~/.workbuddy/skills`。需要无付费诊断时，可从 WorkBuddy 自己的后台任务运行 `scripts/workbuddy_binding_smoke.py`，打开网页后仍按上文等待同一 TaskOutput；不得在别的宿主伪造其环境。

直接调用引擎 reply 即使返回 delivered，也不能证明桌面可见，因此旧 `workbuddy_native` 路径不用于生产通知。隐藏会话、云端 Session 或其他渠道回帖都不能替代原桌面回复。当前受管理任务流程仍需真实桌面完整验收，包括第二聊天隔离、重复完成与断连保留 Answer。
