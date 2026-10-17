# 豆包工作：Windows 本机原聊天通知

仅选项 1/2 实际需要网页且当前宿主匹配时读取；选项 3 的内置音频生成不触发本适配。网页入口与保存后业务路由沿用已读的 [Studio](../studio.md)，不重复加载主 skill 或其他宿主说明。

启动命令使用当前任务 Question；已有角色不得省略 Question 打开空角色管理页。启动器可能因已绑定而返回新 question_id，后续完成事件、Answer 读取使用实际新 ID；保留原启动命令用于会话归属核对，不手工改写历史命令。仅管理声音库时省略 question，不创建假 Question，也不通知绑定完成。

适用于本机豆包 2.32.5（Windows Chromium 主体、app_id 582478）。这是经实机验证的本机兼容桥接，依赖临时 loopback CDP，不是官方稳定消息 API。其他版本、独立 DoubaoWork App、网页版和云电脑不在已验证范围。

## 启动与会话归属

以下会话登记与完成通知用于带 Question 的绑定页；仅管理库按 Studio 省略 question，不要求匹配绑定命令或登记通知目标。

从发起任务的豆包 Shell 调用现有 `python -m makesound.studio_session --project <当前项目绝对路径> --question <qid>`。自动登记读取该子进程自身的 `DOUBAO_OFFICE_APP_ID`、`MCP_VM_CONVERSATION_ID`，经客户端接口核对原聊天 ID、项目、工作目录、本机 runtime 和授权模式。用户不提供或抄写会话 ID/令牌。

首次需要本机桥接时，由 Agent 检查当前实例。若需重启，先让用户保存工作并正常退出；禁止强制结束进程或任务。原应用已经退出后，Agent 从运行时仓库运行 `python scripts/doubao_start_bridge.py`。启动器仅清理新进程继承的其他宿主身份，不修改系统环境变量，验证只监听 127.0.0.1，并保存实例配置。不得从别的平台复制认证变量，不得为通过检查而在豆包执行脚本内抹掉冲突身份。

桥接配置在运行时仓库 `.makesound/doubao-bridge.json`，只含 endpoint、browser instance 路径与 Profile 路径，不含凭据。端口和 browser generation 每次启动都可变化，不硬编码。豆包正常退出后实例失效，需重新验证和启动，不能宣称永久安装后永远可唤醒。

## 完成通知

先持久化 Answer，再由后台自动投递原聊天；保留客户端原生本机任务参数、同一项目和原授权模式。只向聊天 ID 发文字而省略本机参数会使后续工具落入 Linux 云环境，不能采用这种简化方式。不得扩大权限或自动切换云电脑。

`queued` 仅表示服务端确认接受该原聊天的消息，不证明模型已回复。模型收到事件后核对项目、实际 Question 和 Answer，按 Studio 的配方 C 读取结果，检查已有试听，revision 比较变更，仅处理未完成或受影响内容，不强制重新试听；事件不授权付费生成。原聊天忙碌、关闭、实例/权限改变或结果未知时保留 Answer，提示用户回原聊天发送“完成了”，不自动重发。

按 Answer 回执去重，重复点击不重复通知。声音、演绎单与付费确认仍遵循主 Skill，不因桥接测试跳过。

## 验收与限制

已实测固定标记进入指定原聊天并回复、Windows 本机 Shell 与真实项目目录、会话环境 ID 对应、豆包自身自动登记、假音色网页绑定保存与通知接受，以及原聊天自动读取正确 Answer 并生成 pending_confirmation 演绎单。真实回执重复调用不重发。全部测试未生成音频。两个独立真实聊天同时打开的隔离仍未验收；不能拿 mock 用例代替实机结果。

可用 `scripts/doubao_binding_smoke.py` 从豆包自己的 Shell 创建当前项目下隔离的 `.soundmaker-smoke` 假音色测试，禁止拿它生成付费音频。客户端已观察到的本机技能扫描入口包括 `~/Doubao/skills` 和 `~/.agents/skills`；实际安装时确认当前版本扫描目录，不自动创建多份独立 skill。
