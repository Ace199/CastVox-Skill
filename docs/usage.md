# 使用说明

## 安装为目录链接

先克隆仓库，在仓库根目录运行。Windows PowerShell 示例（目标不存在时执行）：

```powershell
$skillSource = (Resolve-Path './skills/soundmaker-dubbing').Path
$skillParent = Join-Path $env:USERPROFILE '.codex/skills'
New-Item -ItemType Directory -Path $skillParent -Force | Out-Null
New-Item -ItemType Junction -Path (Join-Path $skillParent 'soundmaker-dubbing') -Target $skillSource
```

Claude Code 使用 `~/.claude/skills`，WorkBuddy 使用 `~/.workbuddy/skills`。Kimi Work 和豆包应先确认当前版本实际扫描的 skill 目录，再创建链接；Kimi Work 已验证版本的目录为 `%APPDATA%/kimi-desktop/daimon-share/daimon/skills`，豆包本机扫描入口包括 `~/Doubao/skills`。这些路径不代表其他版本或平台的稳定约定。

已有同名目录时先检查内容并备份，不覆盖或删除。创建链接后新建对话，确认宿主实际读到 SKILL.md。宿主导入或升级可能将链接改成副本；可用 `Get-Item <skill-path> | Select-Object LinkType,Target` 复核。macOS/Linux 使用对应宿主目录及符号链接，宿主恢复的实机覆盖范围仍以参考文档为准。

Agent 应从 skill 的真实链接目标定位仓库，所有 `python -m makesound...` 命令以仓库为工作目录，`--project` 始终传用户当前项目的绝对路径。不要把仓库测试项目、测试声音或默认值复制进用户项目。

## 配置和音频工具

MiniMax 配置通过本机配置入口管理，默认位于 `~/.config/minimax/config.json`。不要将真实 API Key 提交到 GitHub、贴到聊天或写入测试示例。Studio 的配置编辑按钮可辅助打开/创建配置；火山引擎配置支持不代表其合成适配器已实现。

在展示本次生成授权范围前执行：

```powershell
python -m makesound.media
```

`ready` 表示媒体工具文件已找到；`wav_only` 表示使用纯 Python 的匹配 PCM WAV 路径。WAV 回退支持单声道 16-bit PCM、帧完整性检查、同采样率拼接与字幕导出；它不是通用解码或重采样器。MP3 和重采样需要已有的 FFmpeg/FFprobe。找不到时不自动下载安装，在冻结 Job 前明确使用 WAV。

## 声音管理和绑定

只管理当前项目声音时，可启动持久化 Studio：

```powershell
python studio_v16_server.py --project '<existing-absolute-project-path>'
```

读取实际启动输出的本机 URL，不假设端口。离线开发时显式加 `--fake --config-dir web/tests/fixtures/providers`，该目录只有测试配置。

配音任务的绑定页由 Agent 创建 Question 后执行：

```text
python -m makesound.studio_session --project <absolute-project-path> --question <question-id>
```

用户只需在页面选择声音、速度和声调，再点击完成。Agent 从保存的 Answer 恢复，按主 skill 准备每角色一句的试听单。宿主恢复失败时可在原聊天说“完成了”；完整 Answer 不会因通知失败丢失。WorkBuddy 的后台任务与等待要求必须另读对应宿主参考。

## 确认和生成

Agent 负责整理原文、角色、已绑定声音、支持的情绪与停顿，展示可审阅演绎单。用户不需要提供内部 hash。确认后冻结 Job，展示厂商/模型、字符数及调用上限，已有的明确授权不重复索取。

以下是运行接口，占位值必须来自已确认并授权的实际任务；不能原样执行或当作付费许可：

```text
python -m makesound.production run --project <absolute-project-path> --job <frozen-job-id> --authorize-paid --max-calls <authorized-calls> --max-characters <authorized-characters>
```

缺失配置、接口错误和未知计费不自动重试。收到音频后字幕/转换失败，只修复已有产物，不再次合成。纯本地导出使用 `python -m makesound.production export --project <absolute-project-path> --job <job-id>`；收到的音频需重处理时使用 `repair-audio`。详见主 skill 的修订与恢复参考。

## 数据目录

- `配音/<任务名称>/<版本>/`：用户可读交付，保留完整分句、字幕与合并试听。
- `outputs/audio/<job_id>/`：运行时源导出，不直接替代用户交付入口。
- `.makesound/`：绑定问答、计划、冻结快照、缓存、预算与通知回执。

这些是项目本机数据，不上传公共仓库。目录链接只同步 skill 源文件，不同步不同项目的声音绑定或任务状态。
