# MakeSoundSkill V1.2 — M1 实现报告

日期：2026-10-14（Asia/Shanghai）。结论：**M1 核心配置与音色管理已实现，49 项离线测试 PASS，0 FAIL、0 ERROR、0 SKIP；完成后停止，未进入 M2。**

最新验收范围仅 **Codex 与 Claude Code** 共用的 Harness-Agnostic 核心/CLI。Kimi Work、DSH、WorkBuddy、豆包保留先前调查，不投入 Adapter 开发。Voice Studio 线框图经用户选择暂缓，本轮没有网页或原型。

## 1. 关键代码与文件

| 文件 | 实现内容 |
|---|---|
| `../pyproject.toml` | Python >=3.11 包元数据；可安装 entry point；运行时零第三方依赖 |
| `../makesound/__main__.py`、`../makesound/cli.py` | `python -m makesound`，稳定 JSON stdout、静态 stderr、非零失败退出码 |
| `../makesound/config_loader.py` | MiniMax 配置只读，环境覆盖，cn/international 与 HTTPS origin 白名单校验，秘密不进 repr/summary |
| `../makesound/validation.py` | 本地协议字段/类型/范围/引用校验；NFC 名称、敏感字段与 credential-like 值防护；禁止声音会话偏好 |
| `../makesound/storage.py` | 严格 UTF-8 JSON、重复 key/NaN 拒绝；明确项目根；OS 锁、revision、同目录临时写/fsync/原子替换 |
| `../makesound/voice_registry.py` | clone/design 来源分离、稳定 asset_id、唯一显示名、既有 Voice ID 本地登记、设计/授权元数据、可选样本托管副本及删除 |
| `../makesound/project_voice_library.py` | 项目别名添加/改名/移除/显式重绑定；default alias 引用完整性；添加+设默认同一文件原子提交 |
| `../makesound/preset_store.py` | 独立项目/全局默认与项目设置；1.1 只读兼容、带备份的非破坏迁移导出 |
| `../makesound/config_resolver.py` | Studio applied > 明确别名/直接引用 > 项目默认 > 全局默认；硬约束、缺别名提示、按目标解析声音，不生成音频 |
| `../makesound/jobs.py` | 配置快照创建/只读加载/哈希校验；冻结实际 Provider/region/ID/声音参数及导出设置，后续别名变更不影响它 |
| `../makesound/service.py` | 统一业务入口；跨文件操作协调锁、已知项目引用清单、全局资产引用检查；无 Harness SDK |
| `../tests/unit`、`../tests/integration` | 标准库 unittest；真实 CLI 子进程、并发进程和故障注入；临时假数据 |
| `../tests/support/sitecustomize.py` | CLI 测试子进程的 Python socket 网络阻断，另有验证阻断确实生效的测试 |
| `../tests/run_m1.py` | 执行实际测试并输出简明 JSON 证据 |
| `../examples`、`../schemas/README.md`、`../README.md` | 假声音/模型的可复制示例、可执行校验说明与 CLI 使用文档 |

M1 **没有真实 Provider 实现**，也没有 clone/design/TTS/upload 网络代码。assets register 仅登记调用方提供的既有/假 ID，不会创建音色。样本 fixture 是测试字节，不是真实录音。

## 2. CLI 与业务结果

已实现：doctor；config show/resolve/set-default/settings/migrate；voices assets list/register/rename/references/sample-delete/delete；voices aliases list/add/rebind/rename/remove；jobs snapshot/status；schema validate。`voices list --source official` 明确返回 not_implemented，不联网。

```powershell
python -m makesound doctor --json
python -m makesound config resolve --project '<明确的绝对项目路径>' --request examples/request-second-paragraph.json --json
python -m makesound voices aliases list --project '<明确的绝对项目路径>' --json
python -m makesound voices assets list --json
python -m makesound jobs status '<snapshot 返回的真实 job_id>' --json
```

完整、可执行的隔离演示见 [README](../README.md)。所有写命令应先读取 revision，使用单独的 demo data/global 路径；示例音色与模型均不可用于真实合成。

**实际 smoke 结果**：在工作区临时中文项目中，经 CLI 添加“女声音1”并设默认，再添加“男声音1”，解析 p002 显式别名后得到：

```json
{
  "status": "ready",
  "bindings": {
    "p001": "FAKE_VOICE_A",
    "p002": "FAKE_VOICE_B"
  },
  "network_calls": 0
}
```

此处仅验证声音分配配置，不含分句、Chunk Planner 或多声音合成。直接以 provider_voice 设置项目默认也已测试：named_voices 仍为空，重建服务对象后配置可复用。

重绑定必须同时提供 `--confirm`、`--expected-revision`、`--expected-old-ref`。旧引用或 revision 不匹配均拒绝。stdout 成功/错误均单一 JSON；退出 0 为业务操作完成，退出 2 为错误或 needs_setup/needs_studio；help/version 除外。

## 3. 实际执行与测试结果

环境：Windows 11、Python 3.13.10。未安装 pytest/jsonschema/setuptools；运行时使用标准库；测试用 unittest，未全局安装依赖。没有以缺少 pytest 为由跳过验收。

```powershell
python -m unittest discover -s tests -t . -q
python -m tests.run_m1 --output docs/M1_Test_Results.json
```

最终运行：**49/49 PASS（unit 40、integration 9），耗时 6.127 秒**。原始逐项结果见 [M1_Test_Results.json](M1_Test_Results.json)，smoke/doctor/语法结果见 [M1_Smoke_Results.json](M1_Smoke_Results.json)。这些文件记录实际执行结果，不是静态预期。

| M1 计划项 | 实际结果/覆盖 |
|---|---|
| CFG-01/02 | PASS：无默认不跳过设置；直接默认无需别名；读取无落盘；重启对象仍复用 |
| CFG-03/04 | PASS：不同项目同名隔离；同项目重名/过期 revision/旧引用不一致拒绝重绑定 |
| CFG-05 | PASS：重绑定后新解析用 B，旧快照仍为 A；快照禁止覆盖；完整生成 resume 留 M2 |
| CFG-06/07 | PASS：全局唯一 ID/NFC 显示名、clone/design 分离；删除托管样本不删源文件/ID/默认引用；引用保护和本地删除边界 |
| CFG-08/09/10 | PASS：male/unknown 不满足 female 硬约束；缺男声别名带筛选与修复状态；离线 applied 选择及项目/Job 关联检查；真实网页提交 NOT RUN |
| CFG-11 | PASS：换声音/语速不改变独立导出/字幕设置；本次覆盖不回写默认；全局/项目嵌套字段合并 |
| CFG-17 | PASS：明确非 Git/中文项目可用；无可信根、相对路径、HOME/不存在目录拒绝项目写入；只读文件失败 |
| CFG-18 | PASS：1.1 只读解析、明确区域、未知字段保留、迁移备份和独立输出，原 active 文件不变；重复迁移不覆盖 |
| REGION-01 | PASS：显式区域、环境覆盖、URL userinfo/query/path 拒绝、地区冲突、configured 区域缺失、不改原凭据 |
| IO-01 | PASS：注入 Windows replace/PermissionError 后旧内容不变且临时文件清理；两个真实进程竞争 revision 仅一个成功；进程被终止后 OS 锁可重新获得；添加别名+设默认原子提交 |
| CLI-01 | PASS：真实子进程贯通新增/默认/解析/重绑定/快照；错误/未知参数不回显测试秘密；JSON 可解析；官方列表拒绝联网 |
| 额外边界 | PASS：损坏快照、重复 JSON key/NaN、错误 Schema/未知字段/非 object 请求、非法参数、过期资产、默认别名删除保护、凭据路径保护 |

初次运行因系统 tempfile ACL 被沙箱拒绝创建子目录/清理，未进入业务断言；测试目录改到授权工作区后正常运行。另修正了一处测试循环复用损坏 fixture 的错误。最终没有 SKIP/BLOCKED 的 M1 自动化测试。沙箱仍输出 Python “Failed to find real location”环境警告；未修改解释器或系统权限。

## 4. 真实 doctor 与兼容性验证

- **Observed / PASS**：新 CLI 对本机实际配置执行只读 doctor，退出 0，status=ok，region=cn；ffmpeg/ffprobe/git/codex/claude 均在 PATH，network_calls=0。doctor 前后实际 MiniMax 文件字节哈希一致；秘密只留在本地，不进入输出。
- **Observed / PASS**：21 个 Python 文件按 Python 3.11 语法版本解析通过。**Python 3.11 实际运行 NOT RUN**，不能以语法检查代替运行兼容。
- **NOT RUN**：pip/wheel 构建与安装（setuptools 未安装）；直接在仓库 `python -m makesound` 已运行。
- **NOT RUN**：Codex 与 Claude Code 内的安装/完整 Agent 对话链路。此次集成指真实本机 CLI 子进程，与宿主 SDK 无耦合；并未启动第二个模型会话，不把它标成完整跨 Harness E2E 已通过。

## 5. 数据与安全取舍

1. 项目修改由显式绝对根目录授权，托管路径拒绝 symlink/junction；运行时不从任意 cwd 推断业务项目。Windows ACL 的实际拒绝会安全报错，未承诺覆盖所有 ACL/同步盘/断电情况。
2. 所有支持的业务修改经服务协调锁和目标文件锁，预设更新必须 CAS revision。项目引用清单在提交前登记：失败可产生多余登记，避免成功引用漏记。读取只读，不为锁创建目录。
3. 全局资产删除检查**当前 data_dir 已登记项目、当前 global_config、历史快照/审计引用**。无法发现全盘手写或其他 data_dir 的项目；故需显式 `--known-projects-only` 承认清单边界。清单缺失/不可读等错误会阻止安全删除，不删除远端资源。历史审计中的引用保守阻止删除；历史清理未实现。
4. 原样本默认复制到独立用户数据位置，不复制进项目；sample-delete 只允许该资产托管路径。若 unlink 后 JSON 写入失败，已授权删除可能已发生，metadata 可暂时滞后；list 以文件是否存在反馈，再次删除可完成登记。没有远端删除/复刻行为。
5. 业务 Schema 用 Python 严格验证器执行；尚无独立 draft-2020-12 导出或前端校验器。V1.1 迁移只导出带备份的新文件，不擅自激活/覆盖原配置，保留原未知字段且不透传 Provider。
6. metadata 属性需要来源，不从别名/Voice ID 猜实际性别；缺别名的“男声”只是请求筛选。Voice ID、模型真实可用性是未知；expired/unavailable 已知状态阻止继续，pending/unknown 不伪装成已远端认证。
7. M1 读取调用方提供的 Studio applied 对象，只验证其结构和项目/Job 身份，不验证网页提交/TTL/令牌真实性；返回明确提醒。真正 Question/Answer 持久事务在 M3，当前没有任何可据此发起收费调用的代码。
8. 快照是配置冻结基础，不是完整 Job 引擎；不含源文正文、未实现状态变迁/生成/缓存复用。名称比较使用 NFC、区分大小写；前后空白输入拒绝，不静默改名。模型/情绪的远端兼容矩阵留 M4。

## 6. 未实现项、NOT RUN 与 M2 前置

没有实现 Voice Studio/试听网页、线框图、真实 API、音频合成/拼接、Script Processor、合成 Chunk、字幕转换、缓存与失败续跑、跨 Agent 自动恢复；没有开发 Kimi/DSH/WorkBuddy Adapter。M2–M4 保持 NOT RUN。

M2 可复用现有解析输出、稳定段落 target、concrete voice 和 snapshot_only 文件，下一阶段须增加：Script Manifest/source range 审计、Chunk Planner、真正的 Fake Provider 与 fixture 音频、时间轴/字幕、缓存和执行状态/恢复语义。M1 资产登记使用假数据，不应被当成已经有 Fake 音频引擎。

进入 M2 前应审查本报告中的继承规则、引用清单边界、迁移激活策略和 CLI 契约；后续如需完整 JSON Schema 导出、安装包构建或 Python 3.11 运行矩阵，应单列验证。用户要求的 M1 停止点已遵守，未开始 M2。
