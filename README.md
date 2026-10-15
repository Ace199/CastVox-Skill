# CastVox-Skill

Agent-Native Voice Production — for Codex + MiniMax.

当前包含 Python 配置核心和 V1.6 Voice Studio 前端原型。网页使用 HTML / CSS / Vanilla JavaScript；项目声音、默认设置和任务分配目前使用内存 Mock，不调用付费 TTS，刷新后重置。

## 打开 Voice Studio

```powershell
python studio_server.py --port 8766 --config-dir web/tests/fixtures/providers
```

打开 http://127.0.0.1:8766/ 。此命令使用仓库内不含凭据的模拟模型配置。详细运行与测试说明见 [web/README.md](web/README.md)，当前需求基线见 [PRD V1.6](doc/MakeSoundSkill_PRD_V1.6_2026-10-15.md)。

## M1 历史实现说明

以下保留 M1 阶段说明；其中的“没有网页”描述仅针对当时的 M1 交付范围。

当前实现配置、全局音色资产登记、项目音色别名/默认、离线解析及不可变配置快照。运行时只依赖 Python 3.11+ 标准库，本机以 3.13 验证；没有真实 MiniMax 客户端、网页、音频生成或自动恢复。本版只验收 Codex / Claude Code 调用同一 CLI 的契约，不依赖两者 SDK。其他平台不开发 Adapter。

## 运行与测试

在此项目根目录运行：

```powershell
python -m makesound --help
python -m makesound doctor --json
python -m unittest discover -s tests -t . -v
```

无需安装依赖即可 `python -m makesound`。`pyproject.toml` 声明可安装包与 `makesound` entry point；构建/安装包需要 setuptools，本机尚未进行 wheel 构建或全局安装。没有为测试安装 pytest，使用标准库 unittest。所有测试目录都在工作区 `.test-tmp` 中，使用假凭据/假素材并清理；CLI 测试有 Python socket 网络阻断。

所有业务命令 stdout 是一个 UTF-8 JSON 对象，stderr 为静态诊断；成功退出 0，配置待补/修复或错误退出 2。`--help/--version` 是人类可读输出。`ready` 表示本地结构与约束可解析，`readiness=local_configuration_only`；绝不证明远端音色/模型/余额可用。`snapshot_only` 不表示生成完成。

## 隔离的离线示例

以下只登记假 ID、解析配置，不联网、不生成音频。路径必须明确指向你选择的**新测试目录**。从工作区根目录执行；不要把下列目录改成现有用户数据/项目而不查看已有 revision。

```powershell
$demoRoot = Join-Path (Get-Location) 'local-demo'
$demoProject = Join-Path $demoRoot '项目 A'
$demoData = Join-Path $demoRoot 'user-data'
$demoGlobal = Join-Path $demoRoot 'global-presets.json'
New-Item -ItemType Directory -Force -Path $demoProject | Out-Null

python -m makesound voices aliases add 女声音1 --project $demoProject --voice examples/voice-female.json --set-default --settings examples/settings.json --expected-revision 0 --data-dir $demoData --global-config $demoGlobal --json
python -m makesound voices aliases add 男声音1 --project $demoProject --voice examples/voice-male.json --expected-revision 1 --data-dir $demoData --global-config $demoGlobal --json
python -m makesound config resolve --project $demoProject --request examples/request-second-paragraph.json --data-dir $demoData --global-config $demoGlobal --json
```

首次新目录预期 `p001 → FAKE_VOICE_A`、`p002 → FAKE_VOICE_B`。这些是**假 ID/属性/模型**，不能用于真实 Provider。再次运行添加操作会拒绝重名或 revision 不符；先用 `voices aliases list` / `config show` 读取当前状态，不能默认覆盖。

直接设默认、不增加别名：

```powershell
# 新测试项目的 revision 为 0；既有项目必须先读取实际 revision。
python -m makesound config set-default --project $demoProject --voice examples/voice-female.json --settings examples/settings.json --expected-revision 2 --data-dir $demoData --global-config $demoGlobal --json
```

该命令只更新默认与显式 settings，不添加/删除 named_voices。上例接在前两次 alias add 后使用 revision 2。设全局默认用 `--global` 代替 `--project`，并读取全局自身的 revision。项目字段覆盖全局字段；本次参数不回写默认。

## 常用 CLI

| 命令 | 行为 |
|---|---|
| doctor | 只读检查 Python、工具是否在 PATH、MiniMax 文件结构/region/URL；不发鉴权请求 |
| config resolve [--project ROOT] [--request JSON] [--region cn] | 只读解析；没有可信项目根时可用本次/全局，但不落盘到 cwd |
| config show --project ROOT / --global | 非敏感预设视图，包含 revision；不输出兼容备份内容 |
| config set-default --voice JSON --settings JSON --expected-revision N | 直接引用 ID/资产或项目别名；--project 或 --global 必选其一 |
| config settings --settings JSON --expected-revision N | 仅更新项目/全局导出、模型、字幕等字段 |
| config migrate --project ROOT --region cn --confirm | 将旧 1.1 导出为兄弟 preset.v1.2.json，另建内容备份；原 active preset.json 不改，重复导出拒绝 |
| voices assets register --file JSON [--sample ABSOLUTE_FILE] | 仅登记已有 clone/design ID；可复制授权本地样本供保留，不上传、不创建远端音色 |
| voices assets list [--show-local-paths] | 默认摘要隐藏设计 prompt/授权资料/样本路径；显式选项查看本地样本路径 |
| voices assets rename ASSET --name NAME --expected-revision N | 全局唯一名称；稳定 asset_id 不变 |
| voices assets references ASSET | 检测本数据目录已登记项目、全局默认、快照中的引用 |
| voices assets sample-delete ASSET --confirm | 只删托管副本，不删原输入文件、Voice ID、资产/别名/快照 |
| voices assets delete ASSET --expected-revision N --confirm --known-projects-only | 仅删除无引用本地记录；须确认引用清单局限，不删除远端音色；保留样本须先显式删除 |
| voices aliases list/add/rebind/rename/remove | 项目内别名管理；不同项目允许同名 |
| jobs snapshot [--request JSON] [--source-hash SHA256] | 冻结声音、模型/参数和段落目标，生成 snapshot_only；不保存原稿、不创建合成 Chunk |
| jobs status JOB_ID | 只读加载与校验已冻结快照，不重新解析别名或执行任务 |
| schema validate --kind preset/asset-registry/request/snapshot --file JSON | 使用严格的 Python 协议验证器离线校验 |

共享选项位于最终子命令后：`--data-dir`、`--global-config`、`--minimax-config`、`--project`、`--region`、`--json`。默认资产/Job 在 Windows LOCALAPPDATA/makesound，默认预设为 `~/.config/makesound/presets.json`，凭据只读位置为 `~/.config/minimax/config.json`。

重绑定必须提供 `--confirm --expected-revision N --expected-old-ref old-ref.json`；old-ref.json 只含旧 ref 对象。例如 `{"kind":"provider_voice","provider":"minimax","region":"cn","voice_id":"FAKE_VOICE_A"}`。确认与 CAS 一起验证，不能用 `--confirm` 强行覆盖过期配置。删除被默认引用的别名会拒绝；改名同步更新该默认。

## 配置、约束和保留边界

- MiniMax 只读字段 api_key/region/base_url；环境变量 `MINIMAX_API_KEY/MINIMAX_REGION/MINIMAX_BASE_URL` 显式覆盖。region 只接受 cn/international；HTTPS 官方区域 origin 白名单，拒绝 URL 中的用户信息、path、query、fragment，区域不符拒绝。旧国内域名只做同区兼容，不静默切换。未核实北部新域名等其他地址不会自动放行。
- config resolve 不需要 Key，也不自动读取它。具体引用带区域；`region=configured` 或旧 1.1 引用需显式 `--region`，不靠密钥猜区。
- 解析优先：本任务 applied Studio 对象 > 明确别名/直接引用 > 项目默认 > 全局默认。draft/pending/cancelled/expired 不冒充 applied。M1 的 applied 对象是**调用方提供的离线协议输入**；问题令牌、提交/领取真实性、TTL 与端到端事务在 M3 实现，不是本阶段的收费授权入口。
- female 等硬约束只按有来源的 metadata 验证，unknown 不自动匹配。缺别名返回 needs_studio、缺默认返回 needs_setup；只返回修复数据，M1 不真的打开 Studio。已提交选择显式 clear_constraints 时记录覆盖提醒。
- 字段按类型/范围校验，未知业务字段拒绝；参数分层，非声音设置不会随换声丢失。显示名/别名用 Unicode NFC、去除首尾空白的输入被拒绝，比较区分大小写；相同规范名全局/项目范围内唯一。
- V1.1 兼容只读，原未知字段保留在兼容副本中，不透传请求。迁移需显式地域、确认和备份；输出不自动激活，需审查后自行安排替换。
- 跨进程 OS 锁 + revision 比较 + 同目录临时文件/fsync/原子替换。托管路径拒绝 symlink/junction。项目 index 在配置提交前登记，失败最多产生保守的多余索引。同步盘/断电持久性/外部直接编辑未做全面验证。
- 引用检测只覆盖当前数据目录知晓的项目、全局默认与历史快照（含审计引用）。不能扫描全部磁盘或其他数据目录；删除必须确认此边界，不自动清理历史引用。样本删除是不可逆本地删除，需 --confirm；若删除后元数据提交失败，下次 list 按文件存在性显示，可再次执行完成登记。
- M1 样本仅本地保留、大小设 20 MiB 上限，不验证真实音频格式/时长，也不代替 M4 的上传规则校验。

所有示例均不含真实凭据、录音或私密脚本。开发阶段不自动初始化 Git、不提交文件、不修改用户的 MiniMax 配置。正式结果与限制见 [M1 实现报告](docs/M1_Implementation_Report.md)。
