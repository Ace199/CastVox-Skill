# M1.5 / Task 04：当前任务角色需求

日期：2026-10-15（Asia/Shanghai）。结果：**PASS；完成后停止，未进入 Task 05。**

## 关键实现

- Mock Agent 提供主角 A、主角 B、旁白、独立参数和主角 B 的预绑定。需求区不要求用户从头录入角色。
- “默认声音”成为固定在最左的可选按钮，与角色横滑条以竖线分隔。角色条独立于项目音色库滚动，方向键切换角色、Home/End 定位首尾；选中项自动滚动露出。
- 角色选中采用特殊描边，绑定状态用 `✓ 已分配 · 音色名称` / `○ 未分配` 表示，选中与已完成分别呈现。
- 选角色后点项目音色卡主体立即绑定或重新绑定，只改变 `task.selections` 对应角色。多个角色可共用声音，各自参数不共享。试听和设置操作保留，不产生绑定。
- 默认声音是独立项目默认目标。点击候选仅更新 `projectDefault.draft`，需“预览保存项目默认”并在差异对话框“确认保存（Mock）”后才更新 `saved`。取消/Esc 保留草稿；放弃草稿恢复已保存值。确认记录 revision，并拒绝无确认/失效/重复确认。
- Mock 默认保存不覆盖角色、不改 Agent 输入、项目库或真实项目文件；刷新重置。它演示持久默认的意图，不宣称已实现磁盘持久化。
- 切换角色/默认目标保留独立配置，右侧显示绑定和参数摘要；参数编辑仍留后续任务。无 Job 时显示角色空态，默认管理仍可用。

## 修改文件

| 文件 | 变化 |
|---|---|
| `web/js/modules/requirements.js` | 新增需求组件、角色选择与定位、状态展示、默认草稿确认/取消/放弃 |
| `web/js/store.js` | 当前 Job 的独立绑定与参数、目标状态、默认 saved/draft/confirmation 与确认校验 |
| `web/js/modules/project-library.js` | 卡片主体按当前目标绑定角色或更新默认草稿；试听/设置保持独立 |
| `web/js/modules/workspace.js` | 挂载需求组件、右侧目标上下文和反馈；保留统一外框及独立声音池 |
| `web/js/mock/data.js` | 三角色、预绑定与独立参数，项目默认初始为空 |
| `web/css/studio.css` | 需求按钮、固定默认、特殊选中描边、已分配标识、默认确认对话框 |
| `web/index.html` | 更新阶段标识；保留直接打开文件时的启动提示 |
| `web/tests/core.test.js`、`web/tests/browser.cjs` | 独立绑定/参数、默认确认、跨 Job 隔离、无 Job 与大量角色定位验证 |
| `web/README.md` | 当前使用方法、作用域、Mock 保存限制 |
| `web/qa/task04/` | 本次结果、截图与受保护文件哈希证据；既有证据保留 |

## 验证结果

**模块测试 9 PASS，浏览器检查 23 PASS，0 FAIL。** 实测已有 Chrome 154.0.8037.98；浏览器测试在获准的沙箱外执行，只访问本机临时 HTTP，拦截外部请求，无依赖下载。

```powershell
node --test web/tests/core.test.js
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
```

- 主角 A 分配后、旁白复用后、主角 A 重绑后，主角 B 和旁白不串状态。
- 主角 A 的 speed=1.1 与主角 B 的 speed=0.9/volume=0.8 在切换和重新绑定后保留；同声不同参数可共存。
- 默认草稿切回后保留；按钮取消和 Esc 均保留草稿；确认保存只改变 Mock 默认；放弃后恢复已保存值；过期和重复确认拒绝；任务配置与 Agent 输入保持不变。
- 换 Job 重新初始化任务状态，无串用旧任务映射；无 Job 时角色操作不可用，但可独立 Mock 保存默认。
- 120 个声音、80 个角色与长名称压力数据下，首尾定位、选中项可见、默认位置固定、角色/项目库独立滚动通过。首轮发现 End 定位边缘显示不完整，补充显式首尾滚动并复验通过。
- Task 01–03 的 HTTP、ES Modules、Debug、Mock、试听、卡片独立事件、布局/窄屏、刷新与 file:// 提示回归通过。
- 已查看已分配桌面、默认保存对话框、窄屏截图；默认按钮固定高度，未保存状态不会撑高区域。
- HTTP 页 console/脚本错误、HTTP 失败、外部请求、业务请求均为 **0**。
- 开始/结束比对 `makesound/`、`schemas/`、`wireframes/`、`examples/` 共 **27 个文件 SHA-256，一致，0 修改**。没有访问真实凭据、真实全局/项目配置目录；没有新增文件写入 API、持久化或真实网络代码。

证据：`web/qa/task04/browser-results.json`、`protected-before.json`、`protected-files.json`、`assigned-desktop.png`、`default-confirmation.png`、`desktop.png`、`dense-desktop.png`、`mobile.png`、`narrow.png`。

## 运行与限制

项目根执行 `python -m http.server 8765 --bind 127.0.0.1 --directory web`，打开 http://127.0.0.1:8765/ 。通过 HTTP 打开，直接双击 HTML 只能看到启动提示。

本阶段没有真实项目默认持久化、真实 Agent 接入、Question/Answer 事务、参数编辑或真实语音生成。仅实测现有 Chrome，未实测其他浏览器、真实移动设备或屏幕阅读器；未重跑 M1 Python 测试。所有 Mock 状态刷新重置。
