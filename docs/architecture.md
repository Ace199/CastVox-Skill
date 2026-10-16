# 代码与 skill 结构

## 运行时分层

代码仍保留现有模块路径，避免改变已验证的命令和数据引用。

| 层 | 主要模块 | 边界 |
|---|---|---|
| 配置与声音 | `config_loader`、`config_resolver`、`provider_config`、`preset_store`、`project_voice_library`、`voice_registry` | 读取本机配置、项目声音、默认与快照 |
| 项目与存储 | `core_v16`、`storage`、`validation`、`errors` | revision、校验、原子写入、锁和受管理路径 |
| 绑定 | `questions`、`studio_backend`、`studio_session` | Question / Answer、Studio 生命周期；不发起付费合成 |
| 表演计划 | `performance_plan`、`inline_controls` | 审阅、确认、声音快照与受支持控制项 |
| 执行与交付 | `production`、`generation`、`providers`、`minimax_provider`、`media` | 冻结 Job、调用预算、收据、缓存、WAV/MP3/SRT 与本地修复 |
| 原会话恢复 | `harness_resume` 及宿主模块 | 自动登记原会话、保存 Answer 后通知、去重与失败回退 |
| CLI | `cli`、`__main__`、`service`、`jobs`、`offline_harness` | 配置命令与已有契约兼容 |

`production` 是明确授权的生成入口。裸 `Generation(core)` 默认没有 MiniMax 适配器；不能将其当作真实合成入口。`media` 只处理本地文件，不下载或安装软件。

## Skill 分层

```text
skills/soundmaker-dubbing/
  SKILL.md                         # 共用流程与确认阶段
  references/
    minimax.md                     # 模型能力、参数、执行与错误处理
    performance-plan.md            # 演绎单与直接请求契约
    delivery-layout.md             # 任务与版本交付目录
    revision-and-recovery.md       # 局部修订、计费未知与本地修复
    harness-resume.md              # 恢复的共用规则
    harnesses/
      codex.md
      claude.md
      workbuddy.md
      doubao.md
      kimi.md
```

主文件只决定配音流程；厂商参考规定实际可执行参数；宿主参考只规定启动、身份和恢复机制。所有宿主读取同一份主 skill，不能为修复某个应用而复制另一套配音规则。

## 宿主恢复

| 宿主 | 当前路径 | 主要限制 |
|---|---|---|
| Codex | 原聊天 queue | 入队不证明模型已执行 |
| Claude Code | 当前进程继承的原生消息地址和令牌 | 管道写入记为 sent_unconfirmed；不得复制其他会话凭据 |
| WorkBuddy | 宿主受管理后台任务与 TaskOutput | 必须在同一轮等待任务；桌面完整续跑仍需验收 |
| 豆包工作 | Windows 本机实例桥接 | 依赖版本与临时本机调试端口；不得强杀应用或切换云端权限 |
| Kimi Work | 当前实例鉴权 WebSocket 控制通道 | 要求唯一原会话匹配；实例变化拒发，不按最近聊天猜测 |

共用规则为保存 Answer 后通知，按 Question/Answer 去重，未知投递结果不盲目重发。通知没有付费权限；恢复后仍须执行角色试听与演绎单确认。版本适配细节保留在各自的 skill 参考中。

## 界面状态与语言

`ui_locale` 在启动器与持久化服务间传递规范化 `zh-CN` / `en`，通过 session 模块交给前端。Agent 按主 Skill 将当前回答主语言显式传入 `--ui-language`；后端不解析聊天、不读取宿主 UI 设置。前端 `i18n`、语言字典和 `locale-control` 负责翻译及手动切换；用户文本保留原文，插值不作为代码或翻译键求值。

默认草稿保存在 store，完成操作存在变更时先确认、保存，再用新 revision 提交 Answer。保存失败不通知，提交失败保留已经保存的默认。语言切换重建视图并保留 store 中草稿，忙碌或确认处理中禁止切换；同源手动偏好优先于启动语言，未提供语言时中文。

## 发布内容

运行时、skill、网页、必要静态资源、测试源代码、示例和公开文档可发布。`doc/` 中的 PRD、`docs/` 中的内部过程材料、`archive/`、`wireframes/`、`.makesound/`、`outputs/`、生成交付与配置凭据留在本地。`.gitignore` 对公开文档使用明确白名单，避免未来报告被误加入。
