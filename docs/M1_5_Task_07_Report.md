# M1.5 / Task 07：试听和分配闭环

日期：2026-10-15（Asia/Shanghai）。结果：**PASS，完成后停止，未进入 Task 08。**

## 实现与范围

- Mock API 生成本地 2 秒提示音结果，明确不是 MiniMax 合成、不体现音色/参数效果。缓存键包含实际 Mock 声音引用、模型、试听全文、情绪、语速、音量、LaTeX 与规范化开关。相同进行中请求合并，命中显示标识；改变有效配置后旧结果标为“过期配置结果”。
- 只有成功且匹配当前参数的试听才开放新增配置的应用操作；过期、加载中、失败、不可用音色不能应用。已有项目声音直接分配入口保留。
- 加入角色池只修改当前任务选中角色，保存实际声音引用和有效参数，不改其他角色、项目库或默认。
- 加入项目库输入项目内唯一名称，Mock API 保存成功后再同时应用到点击时选中的角色。失败不部分应用；无角色或管理模式允许只保存项目库。等待期间切换角色/Job，结果仍限定原目标，不会误绑新目标。
- 同名重绑定必须确认旧→新声音引用、声音参数与 expected revision；API 以 revision+旧引用校验。冲突后清除旧确认、保留名称和草稿；手动重新读取后再明确确认。没有静默覆盖或自动重试。
- 前端保存中防重复点击，已成功同配置重复操作不再创建别名；API 操作 ID 回执防重复提交和同 ID 不同内容。失败为明确的提交前 Mock 失败，可主动重试。
- 默认目标只走“保存为项目默认（确认）”，可不创建命名音色，绝不混作普通角色。沿用 Task 04 明确确认机制，当前任务绑定保持独立。
- 完成设置显示各角色名称、音色/实际引用和参数；有未分配项时标“设置尚未完成”，全部分配后显示 Mock 完成。它不是提交真实 Answer，也不会恢复 Agent 或开始合成。管理模式不显示完成入口。
- Debug 可模拟下一次试听失败、下一次保存失败、项目库 revision 变化；缓存、Mock 项目库、回执均只在内存，刷新重置。

## 文件变化

| 文件 | 内容 |
|---|---|
| `web/js/assignment-flow.js` | 新增通用角色应用、Mock 保存/冲突/重试、捕获目标、库同步与摘要状态 |
| `web/js/modules/assignment-actions.js` | 新增加入角色/项目库、默认路由、重名确认、错误恢复和摘要对话框 |
| `web/js/api.js` | 试听缓存/请求合并、Mock 库 revision、旧引用检查、命名保存、操作回执与调试故障 |
| `web/js/editor.js` | 实际引用参与试听签名、当前试听门槛、候选默认确认衔接 |
| `web/js/store.js` | 集中闭环状态、库 revision；项目卡直接绑定也冻结实际 Mock 引用 |
| `web/js/modules/settings-panel.js` | 接入闭环动作、试听重复点击保护、缓存/过期文案 |
| `web/js/modules/project-library.js` | Mock 保存后刷新项目库，保留横滑位置与卡片操作 |
| `web/js/modules/requirements.js` | 完成入口、池区引用的名称展示、保持默认和角色区分 |
| `web/js/modules/sound-pool.js` | 候选提示与显式应用语义一致 |
| `web/js/modules/debug-panel.js` | 三个故障/冲突演示按钮 |
| `web/css/studio.css`、`web/index.html` | 动作区、命名、确认/摘要布局及 Mock 范围说明 |
| `web/tests/flow.test.js`、`web/tests/browser.cjs`、`web/package.json` | 新增流程测试与浏览器闭环回归，标准测试命令包含新测试 |
| `web/README.md`、`web/qa/task07/` | 使用与验证说明，结果、截图、保护文件证据 |

## 自动化验证

**模块/流程测试 25 PASS；浏览器检查 37 PASS；0 FAIL。** Chrome 154.0.8037.98，已有 Playwright，无依赖下载；浏览器测试仅访问本机 HTTP 并拦截外部请求。

```powershell
node --test web/tests/core.test.js web/tests/flow.test.js
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
```

- 缓存逐字段变化、命中、相同进行中请求合并、失败后重试：PASS。
- 当前结果门槛、过期结果阻断、同任务单角色应用、无效/默认目标禁止误绑：PASS。
- 命名保存成功后才同步角色，失败保留名称/草稿，重复点击及并发同操作 ID 只产生一条库记录：PASS。
- 重名明确确认、旧引用检查、revision 冲突、重新读取和再次确认、重绑定不改其他角色已冻结引用：PASS。
- 请求过程中切换角色，仍只应用到点击时的角色；切换 Job 后即使角色 ID 相同也不会误绑：PASS。
- 管理模式单独保存、默认独立确认、未分配与全部完成的角色摘要：PASS。
- 保留 Task 01–06 的 32 项浏览器回归；桌面/窄屏及大量声音/角色内部滚动保持通过。
- HTTP 页控制台/脚本错误、HTTP 失败、外部请求、业务请求均为 **0**。Mock API 是内存函数，不发真实业务 HTTP 请求。
- `makesound/`、`schemas/`、`wireframes/`、`examples/` 共 **27 个文件 SHA-256 一致，0 修改**；未访问或修改真实配置和凭据。

## 独立浏览器交互验证

另在 Codex 内置浏览器打开实际 http://127.0.0.1:8765/ ，通过界面依次选择主角 A、选择晴朗叙述、生成模拟试听、加入角色池、命名“手动验证旁白”并加入项目库。摘要正确显示该角色的已保存配置和旁白未分配；随后通过现有项目卡补分配旁白，再次打开摘要，实际显示“全部角色已分配 · Mock 设置完成”。该过程只操作可见 UI，没有用页面脚本直接改业务状态。

界面检查也核对了保存后的长卡、角色参数与明确的 Mock 状态。摘要检查发现直接项目卡绑定也需要冻结实际引用，已补齐并通过最终自动化回归。内置浏览器预览页保留供审核；刷新会重置这些测试数据。

证据：`web/qa/task07/browser-results.json`、`protected-before.json`、`protected-files.json`、`applied-and-saved.png`、`rebind-confirmation.png`、`assignment-summary.png`，以及旧阶段回归截图。已查看三张闭环截图。

## 运行与限制

项目根执行 `python -m http.server 8765 --bind 127.0.0.1 --directory web`，打开 http://127.0.0.1:8765/ 。请使用 HTTP，直接打开 HTML 不是完整运行入口。

音频仅提示音，Mock 项目库/缓存/回执不持久化。revision 与原子保存只验证本次内存 Mock，不等价于真实并发文件事务、MiniMax 能力或 M3 Answer 授权/TTL/恢复机制。没有真实收费、真实音色生成、Schema 修改或新平台适配。Chrome 自动化与内置浏览器交互已验证；其他浏览器、真实音频设备和 M1 Python 回归未验证。
