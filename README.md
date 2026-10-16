# CastVox-Skill

面向本地 Agent 的多角色配音 skill：角色选声、独立试听、演绎单确认、受限授权生成，以及 WAV / SRT 交付。

主 skill 与 SoundMaker Python 运行时共用一份源文件。Codex、Claude Code、WorkBuddy、豆包与 Kimi 的差异集中在会话恢复适配层，配音规则不会按应用复制维护。

## 配音流程

1. 读取剧本，分析角色；已有明确绑定可直接复用，缺失声音通过 Voice Studio 绑定。
2. 首轮为每个角色选择一句原对白，展示并确认试听单及本批调用范围。
3. 分别交付角色试听，等待音色确认；三个角色六句对白的首轮是三个独立音频。
4. 展示剩余对白，用户选择逐批确认或一次确认全部范围；每批最多五段。
5. 复用已经成功生成且参数不变的试听句，按原文顺序交付分句音频、合并试听与字幕。

完整外部演绎单和已试听后明确要求直接生成的任务，按明确范围执行。网页完成绑定不等于确认音色、演绎单或付费生成。

## 快速开始

需要 Python 3.11+。核心运行时仅依赖标准库；开发验证使用 Python 3.13。使用源代码时，在本仓库目录运行：

```powershell
python -m makesound --help
python -m makesound.media
```

将 [soundmaker-dubbing](skills/soundmaker-dubbing/SKILL.md) 目录链接到宿主的 skill 加载目录，然后在新对话中使用。安装、配置和启动步骤见 [使用说明](docs/usage.md)。

MiniMax CN 同步接口已接入，必须使用当前项目的声音绑定，并具有本次 Job 的明确付费授权。火山引擎目前支持配置管理，尚未接入合成。FakeProvider 仅生成测试静音，不能用于评价音质。

FFmpeg / FFprobe 可选：优先使用 PATH 或 Windows 当前用户已有的 WinGet Gyan 安装；缺失时匹配的单声道 16-bit PCM WAV 仍可保存、校验、合并并导出字幕。MP3 编码和重采样需要外部媒体工具；不会自动下载安装或静默改变已冻结格式。

## 仓库结构

| 目录 / 文件 | 职责 |
|---|---|
| `skills/soundmaker-dubbing/` | 主流程规则、厂商能力和宿主适配参考 |
| `makesound/` | 项目声音、绑定问答、演绎单、生成、媒体与会话恢复 |
| `scripts/` | 宿主传输、桥接启动、诊断与无付费 smoke 工具 |
| `web/` | Voice Studio 界面、静态资源和前端测试 |
| `studio_v16_server.py` | 持久化 Voice Studio HTTP 服务 |
| `studio_server.py` | 保留的内存 Mock 服务与部分共享服务工具 |
| `studio_config_editor.py` | 本机厂商配置编辑支持 |
| `tests/` | Python 单元、集成与宿主契约测试 |
| `examples/`、`schemas/` | 无真实凭据的示例和格式约束 |
| `docs/` | 公开使用说明和结构说明 |

模块边界、skill 分层与适配限制见 [结构说明](docs/architecture.md)。

## 开发验证

在仓库根目录运行：

```powershell
python -m unittest discover -s tests -t . -q
node --test web/tests/v16.test.js tests/doubao-control.test.cjs
python web/tests/test_config_editor.py
```

Python 集成测试需要本机回环网络及子进程权限。语音请求使用替身，不发送真实付费请求；浏览器测试需要另备 Playwright 和 Chromium，不会由运行时自动安装。前端操作见 [web/README.md](web/README.md)。

## 数据与边界

凭据从本机厂商配置读取，不进入网页问答、演绎单或音频收据。用户交付入口为目标项目的 `配音/<任务名称>/`；运行时源导出在 `outputs/audio/<job_id>`，缓存、冻结快照和回执在 `.makesound/`。

Git 不发布本机任务状态、生成音频、凭据、PRD、设计草稿、实施过程记录、测试报告、截图和历史原型。测试源代码及脱敏测试配置保留，便于复现验证。宿主恢复依赖应用版本与本机权限，目录链接本身不代表该宿主全流程已验收。
