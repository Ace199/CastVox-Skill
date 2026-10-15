# MakeSoundSkill V1.2 — 给 Codex 的探测任务与测试命令

> **先运行 M0，提交报告后再开始 M1–M4。** 下方分为“现成环境命令”和“实现后验收命令”。后者是目标 CLI，并不表示 MakeSoundSkill 已经安装。所有测试默认禁止产生 MiniMax 费用。

## 1. 可直接发给 Codex 的指令（复制整段）

```text
请先阅读 MakeSoundSkill_PRD_V1.2_2026-10-14.md 和 MakeSoundSkill_PRD_V1.1_2026-10-14.md，严格以 V1.2 为准。第一阶段只做 M0 环境探测和接口调查，不创建语音、不上传录音、不试听、不调用收费 TTS/Voice Design API，不修改已有 MiniMax config.json。禁止输出 API Key 或带凭据的 URL。

请完成：
1) 只读检查 Windows / Python 3.11+ / ffmpeg / ffprobe / Git / Codex / Claude Code 可用性；不要因工具未安装就擅自全局安装。
2) 只读检查 Path.home()/.config/minimax/config.json 是否存在；只在本地显示字段名、值类型和脱敏的区域/Base URL 信息，任何密钥值、token、Authorization、嵌套敏感信息均不得输出或复制。
3) 根据用户密钥区域核对 MiniMax 官方文档：TTS、get_voice、clone、upload 和 Voice Design 的真实 API/返回结构、开通条件、收费风险、Voice ID 生命周期、subtitle 返回字段。若无法证明不要猜测 endpoint。
4) 分析 Harness 的“CLI 进程等待 Studio 网页回答后继续”能否在 Codex/Claude Code 内运作，设计 fallback 的 pending-answer 机制；不得声称任意本地网页可唤醒已经结束的 Agent。
5) 输出 docs/M0_Discovery_Report.md：Observed（实际观测） / Docs-Verified（官方文档） / Assumption（假设）分开，标注可执行命令、脱敏结果、阻碍和下一步，不做收费调用。
6) 提交 M1~M4 测试计划、schema 草图，特别检查 Global Voice Asset 与 Project Voice Alias/Project Default 的隔离、没有 Session Preference、多声音、默认不命名、项目别名重绑定确认、Voice Design 进入 MUST。
M0 完成后先停止；不擅自开始收费或更改旧配置。
```

## 2. PowerShell：立即可运行的只读环境探测

在你的 MakeSoundSkill 仓库根目录使用 PowerShell。若仓库还未创建，可从任意普通工作目录运行这一小节；不要在 `C:\Windows\System32` 创建项目文件。

```powershell
$ErrorActionPreference = 'Continue'
Get-Location
Get-Command py, python, ffmpeg, ffprobe, git, codex, claude -ErrorAction SilentlyContinue |
  Select-Object Name, Source
py -0p
python --version
ffmpeg -version | Select-Object -First 2
ffprobe -version | Select-Object -First 2
git --version
```

以下命令**只输出 MiniMax JSON 文件的键名与值类型，不输出实际值**。不读取任意其他账户文件，不修改已有文件；不要将完整配置发给 Agent。

```powershell
@'
import json
from pathlib import Path
p = Path.home() / '.config' / 'minimax' / 'config.json'
print('minimax_config_exists:', p.is_file())
if p.is_file():
    try:
        obj = json.loads(p.read_text(encoding='utf-8-sig'))
        if isinstance(obj, dict):
            print('top_level_field_names_and_types:',
                  sorted((str(k), type(v).__name__) for k, v in obj.items()))
        else:
            print('root_json_type:', type(obj).__name__)
    except Exception as exc:
        print('parse_status:', type(exc).__name__)
'@ | python -
```

**注意**：字段名称本身原则上不是密钥，但如果用户自定义的键名含敏感内容，也应进一步脱敏。具体 API 地区、Base URL 不要求在终端打印明文；让 Codex 只报告规范化地区判定或“待用户确认”。

## 3. PowerShell：离线 Smoke Test（项目代码存在后再运行）

```powershell
# 进入实际仓库目录（由用户/Codex 确定；不要猜路径）
python -m makesound doctor --json
python -m makesound config resolve --project (Get-Location).Path --json
python -m pytest -q tests/unit
```

这些是**目标命令**。如果提示 `No module named makesound`，说明 M1 未实现，记录为“尚未实现”，而非默认要求立即联网安装依赖。不要用 `generate` 探测安装是否成功。

## 4. 必须先用 Fake Provider 实现的测试用例

Codex 应使用临时路径 `tmp_path` 和生成的假 Voice ID，**绝不需要真实 API Key**。

| Case | 操作 | 期望 |
|---|---|---|
| CFG-01 | 无默认 | `needs_setup`，不能收费 |
| CFG-02 | 直接保存项目默认 Voice ID，不添加 alias | 成功且不产生 `named_voices` 条目 |
| CFG-03 | 项目 A/B 都叫“女声音1” | 各自引用独立，允许重名 |
| CFG-04 | 同项目再次写同名 alias | 提示明确确认，默认拒绝覆盖 |
| CFG-05 | 重绑定 alias A→B 后 resume 历史 Job | 原任务仍指向 Voice A |
| CFG-06 | 创建全局克隆资产，保留原样本，再删除本地样本 | 仅删除本地文件，不删除 Voice ID 或项目引用 |
| CFG-07 | 全局创建资产显示名冲突 | 拒绝或要求重命名，稳定 Asset ID 唯一 |
| CFG-08 | 用户约束 female、项目默认 male | 不能错误地选择默认男声 |
| CFG-09 | “男声音1”不存在 | `needs_studio`，带缺失别名与 male 预筛选 |
| CFG-10 | 用户关闭筛选并选择男声后提交 | 以提交的具体声音为准，留下覆盖记录 |
| CFG-11 | 声音设置和导出参数分别覆盖 | 换声音不影响 sentence / SRT 配置 |
| CFG-12 | 两段不同 Voice ID | 请求拆分且顺序正确；不混用单请求 |
| CFG-13 | 同一句内换声 | 保留原句 ID 并生成多个声音 Chunk |
| CFG-14 | 默认 SRT 为 true、字幕失败 | 标记 `subtitle_failed`，不假报 completed |
| CFG-15 | Studio answer 重复提交 | 幂等，不重复生成/保存 |
| CFG-16 | Studio CLI wait 超时、答复迟到、任务恢复 | 不丢已提交回答，不自动收费 |
| CFG-17 | 无可信项目根/只读项目 | 不落到任意 cwd、HOME 或其他项目 |
| CFG-18 | V1.1 schema 迁移 | 备份、明确兼容策略，不破坏现有配置 |

测试要覆盖中文路径、多实例并发、Windows 原子写失败、同一项目两浏览器竞争提交。声学测试可以用合成的静音/WAV fixture 验证时长和 SRT offset，但不得用“文字长度/字数推断”冒充字幕精准对齐。

## 5. Studio 本机问答集成测试（M3 完成后）

```powershell
# 仅当 python -m makesound 已实现这些 CLI 时运行
python -m makesound studio start --project (Get-Location).Path --purpose setup --json
# 记录返回 JSON 中真实的 question_id / studio_session_id；不要手写端口
# 在另一个终端，使用上一步实际返回的 ID：
python -m makesound studio wait --question '<实际question_id>' --timeout 60 --json
python -m makesound studio answer get --question '<实际question_id>' --json
```

测试页面 `applied / cancelled / expired` 三种结局；测试同一回答重复提交、隔离两个项目和两个并行提问；测试浏览器关掉后 CLI 不误报成功；测试已经保存的回答可在 CLI 进程重启后领取。URL 不能编造，启动成功前不输出已就绪。

## 6. MiniMax 实际 API 测试：必须先得到授权

**阶段 M0 只读文档调查，不发创建/试听/合成请求。** 真正测试时，请 Codex 先列出：API 动作、可能收费的调用、预计请求数、输入文本/录音是否将发送给第三方、错误时是否允许重试。得到用户明确同意后，再进行最小样本：

1. 一次短句 TTS + 默认句级 SRT，核验音频长度与字幕时间；
2. 声音复刻（需用户授权录音）+ Voice ID 复用、原样本保留/删除；
3. 文本 Voice Design 创建一次，确认 Voice ID 是否真正可持久使用、区域和收费；
4. 多 Voice ID 的两个短 Chunk 拼接，以及各字幕 offset；
5. Provider 超时/异常时幂等及重复收费风险。

未经同意严禁执行第 1–5 项。不要为了所谓“API 连通性”运行带文本的 TTS，可能收费。未知 API 不猜测，不把完整 `config.json`、Key、录音或实际语音原文粘贴进报告。

## 7. 测试报告验收格式

Codex 最后提交：`M0_Discovery_Report.md`、`Capability_Matrix.md`、`Testing_Plan.md`，分别说明 Python/FFmpeg 版本与环境可用性、配置键结构（仅脱敏）、MiniMax Voice Design 官方真实接口是否已核验、Studio 问答恢复可行性，以及 V1.2 Schema/任务状态的风险。区分确认事实、官方文档陈述和待实测假设。没有执行的测试必须写 **NOT RUN**，不能声称 PASS。
