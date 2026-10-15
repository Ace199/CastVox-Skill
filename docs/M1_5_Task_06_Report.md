# M1.5 / Task 06：右侧设置面板

日期：2026-10-15（Asia/Shanghai）。结果：**PASS；完成后停止，未进入 Task 07。**

## 实现范围与决策

- 三个 Tab 保留，首次默认探索更多；音色生成只有占位。基础设置与探索更多复用同一组控件、草稿和试听逻辑。
- 基础设置：情绪、语速、音量、LaTeX 公式朗读、中英文文本规范化、可编辑试听文本、生成模拟试听、结果与音频控件。不显示音色选择/模型选择/Pitch。
- 探索更多额外显示 Mock 模型选择和音色选择，可浏览项目音色及官方/用户 Mock 候选。
- 项目卡设置进入对应项目音色的基础设置；角色点击进入该 Job/角色的基础设置；声音池卡片进入对应候选的探索更多。切换 Tab 保留草稿，切换对象恢复各自草稿。
- `editor.activeKey` 和 `editor.drafts` 区分 project、pool、role(Job+role)、default(project)。角色草稿继承已绑定参数，随后编辑不直接改当前任务已应用配置；项目音色编辑不改项目库；候选浏览不自动绑定。项目默认参数进入独立未保存草稿，仍须明确确认 Mock 保存。
- 试听文本来自 Mock Agent 的长完整句，可编辑；原始 Mock 稿件字段不变，无稿件使用本地完整样句。
- Mock Capability Table：完整模型支持 auto/happy/sad/angry，轻量模型支持 auto/happy。不支持的选项可见但 disabled，选项 title 和正文有原因；模型切换不静默替换已选情绪，不兼容时禁止试听，等待主动选择。
- 试听为用户主动点击后返回本地 2 秒提示音，**不模拟真实音色或参数效果**。结果按声音/模型/情绪/语速/音量/文本开关/文本签名标识；修改后显示旧参数试听。失败保留草稿及上次音频，旧音频仍标明旧参数；结果异步返回只更新原对象。
- 未引入真实 Provider、框架或新 Agent 适配。LaTeX/文本规范化、模型与试听文本均为 UI Mock 草稿字段，不修改 M1 Schema。

## 文件

| 文件 | 变化 |
|---|---|
| `web/js/editor.js` | 新增 Mock 能力表、对象草稿激活、编辑校验、试听签名与阻断规则 |
| `web/js/modules/settings-panel.js` | 新增共享控件、上下文恢复、兼容提示、本地模拟试听及结果展示 |
| `web/js/store.js` | 新增集中编辑草稿及试听状态动作，加载 Job 时隔离初始化 |
| `web/js/modules/workspace.js`、`web/js/app.js` | 接入共享面板和 Mock API，移除旧只读详情渲染 |
| `web/js/modules/requirements.js` | 保留默认确认保存，阻止不兼容草稿或尚未提交的池区候选误保存 |
| `web/js/mock/data.js` | Mock Agent 提取的长句及来源说明 |
| `web/js/api.js` | 模拟试听的异步结果与失败事件，仅返回本地已有 WAV |
| `web/css/studio.css`、`web/index.html` | 设置表单、内部滚动与阶段标识 |
| `web/tests/core.test.js`、`web/tests/browser.cjs` | 草稿隔离、共享参数、能力兼容、试听状态与历史回归 |
| `web/README.md`、`web/qa/task06/` | 使用说明、实际结果、截图与保护文件证据 |

## 实际验证

**模块测试 17 PASS，浏览器检查 32 PASS，0 FAIL。** 浏览器为现有 Chrome 154.0.8037.98，复用已有 Playwright；在获准的沙箱外只访问本机临时 HTTP 服务。

```powershell
node --test web/tests/core.test.js
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
```

- 基础设置不显示模型/音色选择或 Pitch，探索更多显示额外选项；往返三个 Tab 后语速/音量/布尔开关/编辑文本不重置：PASS。
- 完整模型选悲伤后切轻量模型，情绪仍为 sad，原生 option.disabled=true，有明确原因且试听禁用；主动改开心后恢复可试听：PASS。
- 角色 B 初始 speed=0.9，编辑后切角色 A 再返回保留；同声音的项目、角色、候选草稿分别独立。普通编辑前后原始项目输入、角色已应用配置、默认已保存状态不变：PASS。
- 生成模拟试听得到本地音频与时长；修改参数后标旧参数，换 Tab 保留结果；注入模拟 API 失败后保留试听文本和错误提示：PASS。
- 模块层覆盖参数范围/类型、未知字段拒绝、不可用候选阻断、异步结果归属、默认编辑的显式确认与放弃恢复：PASS。
- Task 01–05 的 28 项既有浏览器检查保持通过，包括卡片事件、角色分配、默认确认、池区筛选、异常、窄屏/大量数据滚动与 file:// 启动提示。
- HTTP 页面脚本/控制台错误、HTTP 失败、外部请求、业务请求均为 **0**。只有本地静态资源加载，不调用真实 MiniMax。
- 已查看探索更多设置、基础设置/旧参数结果及窄屏截图。设置区内部滚动，顶部 Tab 和底部工作区状态固定；窄屏页面纵向滚动是预期行为。
- `makesound/`、`schemas/`、`wireframes/`、`examples/` 共 **27 个受保护文件 SHA-256 一致，0 修改**；未访问或修改真实凭据、全局或项目配置。

证据：`web/qa/task06/browser-results.json`、`protected-before.json`、`protected-files.json`、`explore-settings.png`、`basic-settings.png`、`narrow.png` 等；之前各 Task 证据保留。

## 运行与限制

项目根执行 `python -m http.server 8765 --bind 127.0.0.1 --directory web`，打开 http://127.0.0.1:8765/ 。直接双击 HTML 不是完整运行入口。

所有编辑/试听均为 Mock、刷新重置。角色/项目/候选参数应用提交、候选加入项目库或角色池、真实保存及真实语音留后续任务。默认已有声音的明确确认 Mock 保存保留；候选尚未提交为默认时不能通过该入口误保存。模型能力只表示虚构本地表，不证明真实 MiniMax 支持；提示音不用于判断音色、语速或情绪效果。仅实测 Chrome，未验证其他浏览器、真实移动/音频设备或 M1 Python 回归。
