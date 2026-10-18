# CastVox · AI 多角色配音

**把剧本交给 Agent，先选声试听，再生成可剪辑的对白、旁白和有声故事。**

A local-first agent skill for multi-character text-to-speech (TTS), AI voiceovers, and dialogue dubbing with MiniMax.

[English](README.en.md) · [快速开始](#快速开始) · [看看怎么用](#看看怎么用) · [支持的应用](#支持的应用) · [通用网页桥接](#通用网页桥接) · [安装与配置](docs/usage.md) · [反馈问题](https://github.com/Ace199/CastVox-Skill/issues)

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Voice provider: MiniMax](https://img.shields.io/badge/Voice-MiniMax-4055C8)
![Local-first](https://img.shields.io/badge/Workflow-Local--first-2D7A65)

完整配音流程适用于 **Codex、Claude Code、Kimi Work、豆包工作**等可执行本地命令的 Agent。**Claude App Cowork** 已接入主机网页绑定与原请求继续，当前桥接不提供语音合成。真实语音生成已接入 **MiniMax CN**；主要实机验证环境为 Windows；已增加 [macOS 基础配置](docs/usage.md#macos-基础安装与配置)，完整宿主自动续跑仍待 Mac 验收。

## 为什么用 CastVox？

多角色配音的工作不止是“把文字读出来”：你还要给人物选声、比较试听、调整演绎，把结果整理给剪辑。改一句后，又得判断哪些音频能继续用。

CastVox 把这套流程放进同一段 Agent 对话：

| 你要完成的事 | CastVox 帮你做什么 |
|---|---|
| 为人物挑选合适声线 | 根据角色推荐 2～3 个候选，按你选择的范围试听 |
| 保持人物声音一致 | 保存项目声音、角色绑定和默认配置，之后继续使用 |
| 先判断效果再做整稿 | 同角色用同一句原文比较，选定后再生成剩余对白 |
| 修改台词、换声或调整情绪 | 核对实际变化，复用没变的音频，保留旧版 |
| 把素材交给剪辑 | 整理独立 WAV、可用 SRT、合并试听、演绎单与文件索引 |
| 明确本次生成范围 | 生成前展示台词、参数、模型和调用范围，按授权执行 |

**适合：** 短剧对白、有声故事、视频旁白、角色讨论，以及需要保留分句素材的内容制作。配置、缓存与产物保存在本机，合成文本会发送给所选语音服务。

## 看看怎么用

把这段话复制给已安装 skill 的 Agent，再附上剧本：

```text
使用 soundmaker-dubbing 为这份剧本做多角色配音。
先分析角色，每个角色推荐 2～3 个合适音色，让我选哪些试听。
同一角色用同一句原文、相同演绎比较；我选定后再准备正式配音。
生成前展示台词、实际情绪和调用范围。
最后给我合并试听、独立分句，以及实际可用的字幕。
```

没有剧本也可以从主题开始：

> 写一段三个人讨论《麦克白》的短对白，需要配音。先给我文案，再让我选择选声方式。

下面是**流程示意**，不是音频效果演示：

```text
你：用这份三人剧本配音。
Agent：你可以使用自己的声音配置，或让我推荐音色。
你：推荐，每个角色给两个候选。
Agent：列出候选名称、ID 和差异，询问要试听哪些。
你：全部试听。
Agent：展示同句试听单及费用范围，确认后分别生成。
你：选好声音了，继续做正式配音。
Agent：核对最终演绎，复用符合目标的试听，只生成剩余内容。
你：第二句停顿长一点。
Agent：本地调整段间停顿，另存新版本，保留原版。
```

### 选声有三种入口

1. **使用我的声音**：沿用项目绑定、默认声音或指定 Voice ID，适合已有工作流。
2. **推荐音色**：Agent 从核实目录匹配角色，候选全部入项目库；可试听一个、部分或全部，再最终选定。
3. **当前应用内置生成**：仅 Kimi/豆包会话确有可调用音频工具时提供。直接交付音频，不进入项目音色库，不承诺跨次保持相同声线。

选项 1/2 需要时才打开 **Voice Studio** 管理声音和绑定；支持中英文，保存后还可以重新打开修改。推荐匹配由 Agent 完成，MiniMax 提供音色目录。

## 快速开始

项目音色路径需要：**可执行本地命令的 Agent、Python 3.11+、可用的 MiniMax CN API 配置**。真实语音生成由服务商计费，配置和入库本身不生成音频。

macOS 使用 Python 3.11+ 的 python3 或虚拟环境解释器；安装、符号链接和配置编辑见 [Mac 基础安装](docs/usage.md#macos-基础安装与配置)。不要直接在 Mac 执行下方 PowerShell 命令。

### 1. 克隆仓库

```powershell
git clone https://github.com/Ace199/CastVox-Skill.git
cd CastVox-Skill
python -m makesound.media
```

核心 Python 运行时仅依赖标准库。媒体检查不调用语音服务，也不下载安装软件；没有 FFmpeg 时仍支持符合要求、采样率匹配的单声道 PCM WAV，MP3 和重采样需要额外媒体工具。

### 2. 把 skill 安装到你的 Agent

将 `skills/soundmaker-dubbing/` 链接到应用实际使用的 skill 目录，并重新加载或新建对话。Windows PowerShell 的 **Codex 示例**如下，仅在目标目录不存在时执行：

```powershell
$skillSource = (Resolve-Path './skills/soundmaker-dubbing').Path
$skillParent = Join-Path $env:USERPROFILE '.codex/skills'
New-Item -ItemType Directory -Path $skillParent -Force | Out-Null
New-Item -ItemType Junction -Path (Join-Path $skillParent 'soundmaker-dubbing') -Target $skillSource
```

Claude Code、Kimi Work、豆包工作和 WorkBuddy 的路径与运行时定位设置见 [完整安装说明](docs/usage.md#安装为目录链接)。已有同名目录先核对并备份，不覆盖。

**Claude App Cowork：一次安装 skill 与桥接。** 在主机上的仓库目录执行：

```text
python -X utf8 -m makesound.claude_install
```

自动连接 skill、备份配置并登记通用主机 MCP，无需手填 JSON；已有配置会检查冲突，其他 MCP 保留。需 Python 3.11+，macOS 使用对应 python3；配置后可能仍需重连或重开 App。自动安装针对已验证的本地存储布局，多账号与其他版本见[安装说明](docs/usage.md#一次安装-skill-与主机桥接)。此入口当前用于绑定，不提供完整配音生成。

### 3. 配置服务，开始第一段配音

告诉 Agent：

> 使用 soundmaker-dubbing 帮我推荐声音。如果 MiniMax 尚未配置，打开本机配置文件让我填写 API Key。先给我试听单，确认后再生成。

Agent 会按需创建或打开 `~/.config/minimax/config.json`。**API Key 留在本机文件里，不贴到聊天中。** 保存后检查配置，再附上剧本或使用上面的示例。

## 你会拿到什么？

项目音色流程把用户交付集中放在一个任务目录：

```text
你的项目/
├─ 配音/任务名称/
│  ├─ 文件索引.md
│  ├─ 试听/                     # 候选音色逐个试听
│  └─ v01_初版/
│     ├─ 合并试听_全文.wav
│     ├─ 配音演绎单.md
│     ├─ 交付说明.md
│     ├─ 剧本.md
│     └─ 分句/                  # 独立 WAV + 已取得的真实 SRT
└─ .makesound/                  # 内部状态、输入、缓存及收据
```

情绪、音色或发声控制改变时，相关句子需要重新生成；只有段间停顿改变时，本地调整即可。字幕下载失败会单独报告并保留音频，不用空字幕冒充成功，也不为补字幕自动重做 TTS。内置生成入口仅交付实际工具返回的文件或链接，不强制这套目录。

## 支持的应用

| 应用 | 当前支持情况 |
|---|---|
| [Codex](skills/soundmaker-dubbing/references/harnesses/codex.md) | 已有原聊天唤醒记录；队列接收不等于模型已完成处理 |
| [Claude Code](skills/soundmaker-dubbing/references/harnesses/claude.md) | Windows 2.1.295 已有绑定恢复记录 |
| [Claude App · Cowork](skills/soundmaker-dubbing/references/harnesses/claude-cowork.md) | 主机常驻 MCP 的网页 Fake 绑定与原请求继续已在 Windows App 实测；桥接不提供合成 |
| [Kimi Work](skills/soundmaker-dubbing/references/harnesses/kimi.md) | Windows 3.2.8 已有绑定与原会话续跑记录；不等同普通 Chat/独立 CLI |
| [豆包工作](skills/soundmaker-dubbing/references/harnesses/doubao.md) | Windows 2.32.5 已有绑定恢复记录，依赖当前实例和桥接配置 |
| [WorkBuddy](skills/soundmaker-dubbing/references/harnesses/workbuddy.md) | 等待与返回机制已实现，真实桌面完整流程待验收 |

同一份 skill 共用配音流程。宿主升级和权限变化可能影响恢复；通知失败时绑定仍会保存，可回原对话说“完成了”继续。macOS/Linux 及不同版本的完整宿主恢复尚未统一实测。

## 通用网页桥接

网页选好声音后，Cowork 可以通过仍在等待的工具请求取得保存结果，继续原任务。网页与项目由主机服务持有，无需在 Cowork 的隔离 VM 中启动服务器。

这套桥接也可以供其他 Skill 接入：**Skill 决定业务流程，应用适配器负责网页与数据，MCP 负责启动任务、等待和返回结果。** 通用核心不依赖 SoundMaker，不读取角色或音色字段。当前交付了 SoundMaker 绑定适配器和独立的普通表单参考应用；新应用需要实现并登记自己的适配器。

协议 **1.0** 统一任务结果、网页提交和错误格式，支持提交去重、版本冲突检查、持久化恢复；业务字段放在 data 中。新调用显式声明 protocol_version，旧 MCP 输出、原绑定网页与已保存数据保持兼容。

- [接入文档：协议、适配器与 Skill 调用示例](docs/host-bridge-integration.md)
- [JSON Schema：结果与网页提交校验](schemas/host-bridge-v1.schema.json)
- [独立表单示例：不加载 SoundMaker 或语音服务](host_bridge/example.py)

桥接返回当前等待请求，不负责唤醒已结束的对话。网页完成也不代表授权付费生成。Windows Cowork 的绑定与原请求继续已有实机验证；新增协议 1.0 有自动化覆盖，App 新协议实测与完整 Mac 宿主续跑仍需分别验收。

## 常见问题

**安装 Skill 都需要配置 MCP 吗？**

本地命令方式运行的宿主继续使用原安装流程。Cowork 的主机网页绑定需要本地 MCP，可通过上面的一次安装命令一起配置；只复制 SKILL.md 不会自动安装服务。

**是否必须打开厂商网站选声？**

推荐路径可以在聊天里选声、试听和确认。用户自行管理时才开本地 Voice Studio；首次获得服务商账号和 API Key 仍需用户自行完成。

**是否支持火山引擎？**

目前只有配置管理，真实合成适配尚未接入，不提供可执行的火山推荐入口。

**可以先不付费看看流程吗？**

开发测试可使用 FakeProvider 验证绑定、恢复和交付链路，输出是测试静音。真实声音试听与正式生成使用服务商 API，按确认范围执行。

**已有明确声音或完整演绎单，还要重新选一遍吗？**

不需要。可沿用明确配置和有效授权，只补缺项；当前参数与已认可试听一致时复用已有音频。

## 文档与反馈

[安装和配置](docs/usage.md) · [架构与开发](docs/architecture.md) · [桥接接入协议](docs/host-bridge-integration.md) · [Voice Studio](web/README.md) · [English](README.en.md)

欢迎带着你的场景来 [提问或报告问题](https://github.com/Ace199/CastVox-Skill/issues)：使用的 Agent 与版本、所处步骤、期望与实际结果，以及脱敏错误信息，能帮助复现。请勿附上 API Key、私有收据或签名下载链接。

如果 CastVox 对你有用，可以 Star 留作之后的配音工具，也欢迎把仓库分享给做短剧、有声故事或视频旁白的朋友。
