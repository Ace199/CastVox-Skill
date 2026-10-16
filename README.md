# CastVox-Skill

### 在你熟悉的 AI 工具里，把剧本做成多角色配音。

贴入一份剧本，让 Agent 帮你分析角色、打开选声页面、准备逐句演绎单，再生成可试听、可修改、可剪辑的音频和字幕。

**先听角色，再生成整稿。改一句，就只重新生成那一句。**

适合短剧对白、有声故事、视频旁白，以及需要保留分句素材的配音项目。

[开始使用](#开始使用) · [配音流程](#从剧本到音频) · [应用兼容](#在这些应用中使用) · [详细安装](docs/usage.md)

---

## 你负责决定声音，Agent 负责推进流程

多角色配音需要处理选声、参数、文件和返工。CastVox 把这些步骤放进你与 Agent 的同一段对话中。

| 你想做的事 | CastVox 如何处理 |
|---|---|
| 给不同角色挑声音 | 分析角色，在本地 Voice Studio 页面绑定音色、语速和声调 |
| 先判断声音合不合适 | 每个角色选一句原对白，分别生成试听，确认后再继续 |
| 调整一句的演绎 | 逐句展示声音、情绪、语速、声调及实际支持的停顿或发声动作 |
| 把音频拿去剪辑 | 保留独立分句和字幕，同时整理合并试听版 |
| 中途改一句台词或换声 | 为变化部分建立新版本，复用其余已校验音频，保留原版本 |
| 控制生成范围和开销 | 生成前展示本次模型、字符数和调用上限，按明确授权执行 |

已成功生成且文本、声音、参数不变的试听句可以复用，不必为完成整稿再生成一次。音频已收到但字幕或导出失败时，优先修复本地产物，避免盲目重复提交。

## 从剧本到音频

假设你有一段 **3 个角色、6 句对白** 的剧本：

```text
你：用这份剧本做多角色配音，先让我听听每个角色的声音。

Agent：分析三个角色，打开 Voice Studio。
你：在页面里为角色选声，点击完成。

Agent：展示三句试听单，每个角色一句，说明参数和本次调用范围。
你：确认试听单并授权这次生成。

Agent：分别交付三个角色的试听音频。
你：声音合适，继续生成剩余对白。

Agent：展示剩余三句供审阅，按授权生成，再整理完整交付。
```

这是一段使用流程示意，不是预生成的演示结果。

你可以每批审阅，也可以先审阅并授权全部剩余内容，再让 Agent 自动逐批执行。实际执行每批最多五段。已有完整外部演绎单，或已经试听并明确要求直接生成时，也可以按指定范围继续。

**点击网页“完成”只是保存声音绑定。** 音色试听、演绎单确认和付费授权各有明确阶段，Agent 不会把选声完成当成整稿生成许可。

## 交付后，还能继续修改

对 Agent 说“第二句换成另一个声音”或“这句停顿再长一点”，它会先给出修改前后的差异，确认后只处理变化部分，并用已有片段重建合并版。

交付按目标项目的 `配音/<任务名称>/<版本>/` 整理，包含当前版本的分句音频、对应字幕和合并试听。局部修改保留旧版，并提供新版合并音频、替换句与原句的对照入口。

首轮角色试听优先展示各角色的独立音频；完整交付优先提供合并试听，并保留剪辑所需的分句素材。

## 在这些应用中使用

同一个 `soundmaker-dubbing` skill、同一套配音运行时。应用适配层负责识别原会话，以及选声完成后的恢复方式。

| 应用 | 绑定完成后的继续方式 | 兼容说明 |
|---|---|---|
| [Codex](skills/soundmaker-dubbing/references/harnesses/codex.md) | 原会话消息队列 | 已验证原聊天唤醒；入队不等于模型已完成处理 |
| [Claude Code](skills/soundmaker-dubbing/references/harnesses/claude.md) | 原生会话消息 | Windows 2.1.295 已验证；写入状态本身不代表接收确认 |
| [Kimi Work](skills/soundmaker-dubbing/references/harnesses/kimi.md) | 当前实例的本地控制通道 | Windows 3.2.8 已验证；不覆盖普通 Chat 或独立 CLI |
| [豆包工作](skills/soundmaker-dubbing/references/harnesses/doubao.md) | Windows 本机桥接 | 2.32.5 已验证；依赖版本与本机实例配置 |
| [WorkBuddy](skills/soundmaker-dubbing/references/harnesses/workbuddy.md) | 受管理后台任务与 TaskOutput | 已实现等待与返回机制，真实桌面完整流程仍待验收 |

当前实机验证主要在 Windows。应用升级、权限或运行环境变化可能影响恢复；安装 skill 不代表所有版本都能自动唤醒。通知失败时声音绑定仍会保存，可以回原对话说“完成了”继续。

## 开始使用

需要一个能执行本地命令的 Agent、Python 3.11+，以及可用的 MiniMax 国内账号与 API 配置。真实语音生成由 MiniMax 计费。

### 1. 获取项目

```powershell
git clone https://github.com/Ace199/CastVox-Skill.git
cd CastVox-Skill
python -m makesound.media
```

核心 Python 运行时只依赖标准库。上面的媒体检查不调用语音服务、不产生合成费用，也不下载工具。

### 2. 安装 skill，配置声音服务

按 [安装说明](docs/usage.md#安装为目录链接)，把 `skills/soundmaker-dubbing/` 链接到所用应用的 skill 目录，然后新建对话。

按 [配置说明](docs/usage.md#配置和音频工具) 设置本机 MiniMax 配置。Voice Studio 提供配置编辑入口；真实 API Key 留在本机配置中，不需要贴到对话里。

### 3. 把剧本交给 Agent

可以从这句话开始，随后附上你的剧本：

> 使用 soundmaker-dubbing 为下面的剧本配音。先分析角色，让我选择声音；每个角色先生成一句独立试听，等我确认音色后再继续。

如果你还没有剧本，也可以先请 Agent 帮你写好，再进入配音流程。

## 没有 FFmpeg，也能先用 WAV

运行时优先复用已有 FFmpeg / FFprobe，包括 Windows 当前用户的 WinGet Gyan 安装。找不到时，符合要求的单声道 16-bit PCM WAV 仍可校验、保存、按相同采样率拼接并导出字幕。

**不会为了完成配音自动下载安装 FFmpeg。** MP3 编码和重采样仍需要外部媒体工具；缺失时先说明限制，在冻结任务前明确使用 WAV。已确认的输出格式不会被静默替换。

## 当前支持范围

- **语音服务**：已接入 MiniMax CN 同步语音接口；具体模型、情绪、句中停顿和发声动作以 [MiniMax 能力说明](skills/soundmaker-dubbing/references/minimax.md) 为准。官方支持与本地已接入能力会分别说明。
- **火山引擎**：目前支持配置管理，合成适配器尚未接入。
- **离线体验**：FakeProvider 可测试选声绑定、恢复和交付链路，输出是测试静音，不是真实配音。
- **声音效果**：模型参数不等于精确表演承诺，最终以试听结果为准。

## 想了解实现或参与开发？

[代码与 skill 结构](docs/architecture.md) · [完整使用说明](docs/usage.md) · [Voice Studio 开发说明](web/README.md) · [反馈问题](https://github.com/Ace199/CastVox-Skill/issues)

```powershell
python -m unittest discover -s tests -t . -q
node --test web/tests/v16.test.js tests/doubao-control.test.cjs
python web/tests/test_config_editor.py
python web/tests/test_provider_config.py
```

Python 集成测试需要本机回环网络与子进程权限；语音请求使用替身。浏览器测试另需预先准备 Playwright 和 Chromium。

本机凭据、任务缓存、生成音频和项目交付不随仓库发布。PRD、设计草稿与实施记录也不包含在当前发布文件中。
