# M1.5 / Task 01：前端工程基础

日期：2026-10-15（Asia/Shanghai）。状态：**PASS，完成后停止，未进入 Task 02。**

## 检查结论与边界

项目中已有 Web 代码只有 `wireframes/Voice_Studio_Wireframe_01.html`、`02.html` 及其 QA；未发现 React、Vite、Next.js 工程，无需迁移或删除。目录不是 Git 仓库。

已阅读 PRD V1.3、Visual Direction V1、M1 实现报告和 Wireframe 交互评审；查看工作区界面参考 PNG。未发现独立头像素材；本项只使用本地 SVG 图标与文字卡片，不裁取参考图头像。

采用 HTML5、CSS3、Vanilla JavaScript ES Modules；无应用框架、打包器、Provider SDK、真实 API 或凭据访问。Mock 数据、事件与状态仅保存在内存。音色生成保留占位。工作台是工程布局基线，不代表最终高保真设计验收。

## 新增文件

| 文件 | 内容 |
|---|---|
| `web/index.html` | 页面入口、同源资源策略；CSP `connect-src 'none'` |
| `web/css/studio.css` | 基础视觉、响应式网格、共享项目库滚动容器、独立角色滚动容器、焦点与 reduced-motion |
| `web/js/app.js` | ES Modules 启动与模块组合、加载状态、开发模式判定 |
| `web/js/store.js` | 集中状态、动作、订阅与隔离快照 |
| `web/js/api.js`、`web/js/mock/data.js` | 异步 Mock 服务、成功/失败事件、虚构项目/Job/角色/声音 |
| `web/js/events.js` | 最多 100 条日志；事件名、对象 ID、结果与错误 |
| `web/js/modules/workspace.js` | 工作台基础布局、键盘 Tab 切换、只读数据展示 |
| `web/js/modules/debug-panel.js` | 开关、测试事件、Mock 成功/失败测试、清空日志、状态查看 |
| `web/assets/studio.svg` | 本地占位图标 |
| `web/package.json`、`web/README.md` | 无依赖运行/测试命令、模块说明与限制 |
| `web/tests/core.test.js`、`web/tests/browser.cjs` | Node 标准库测试与已有 Playwright 浏览器验收 |
| `web/qa/browser-results.json`、`desktop.png`、`mobile.png` | 实际浏览器验收记录与截图 |

所有实现改动均为新增 `web/` 文件及本报告；未编辑 M1 Python Core、Schema、旧 Wireframe、原有文档或真实凭据。原计划的临时哈希基线在后续沙箱调用中不可读取，因此**不声称完成了逐文件哈希一致性验证**。

## 本地运行

项目根目录执行：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

打开 http://127.0.0.1:8765/ 。Ctrl+C 停止。默认显示开发工具开关；`/?dev=0` 隐藏开发工具。不支持直接通过 file:// 启动 ES Modules。

## 验证结果

**Node 标准库测试：4 PASS、0 FAIL。**

```powershell
node --test web/tests/core.test.js
```

覆盖 Mock 结果与数据隔离、失败/未知项目及日志、Store 快照与状态/订阅、日志容量/清空/取消订阅。

**实际 Chrome 浏览器验收：9 PASS、0 FAIL。** 浏览器版本 `154.0.8037.98`，本机已有 Playwright；没有联网安装。命令如下，脚本自动管理独立临时 HTTP 服务：

```powershell
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
```

| 检查 | 结果 |
|---|---|
| 本地 HTTP 与 ES Modules 启动、Mock 数据展示 | PASS |
| Debug 展开、测试事件名称/对象 ID/结果展示 | PASS |
| Mock 成功与失败、错误可见且已捕获 | PASS |
| 清空日志、关闭/重开、当前状态查看 | PASS |
| Tab 键盘操作、音色生成占位 | PASS |
| 1440 / 390 / 320px 无页面水平溢出 | PASS |
| `?dev=0` 隐藏 Debug | PASS |
| 刷新重置内存状态 | PASS |
| 控制台/脚本错误、HTTP 失败、外部请求、业务请求均为 0 | PASS |

首次沙箱内测试因本地回环连接被拒绝（EACCES）未进入页面验收；获准在沙箱外执行同一测试后通过。浏览器测试对外部请求执行拦截并记录；实际记录为零。已人工查看桌面和 320px 全页截图，页面可读；Debug 在窄屏采用表格容器滚动。

## 剩余范围与限制

- 本项仅实现基础工程、只读布局与调试交互；没有角色分配、参数编辑、搜索、试听、音频播放或项目保存。
- 没有真实 Question/Answer、TTL、持久事务、Agent 恢复或平台适配；接口为通用异步 JavaScript Mock 边界，不宣称可直接输入 M1 CLI。
- 不修改 M1 Schema；LaTeX/文本规范化等未来 UI 字段尚未接入。素材版权与头像交付未在本项扩展。
- 自动化只实测现有 Chrome；Firefox、Safari、真实移动设备及屏幕阅读器未验证。M1 的既有 49 项测试本轮未重跑。
- 浏览器测试依赖已有 Playwright 与浏览器；网页运行本身不需要它们。运行说明中提供路径配置，无自动下载行为。
- 男女共享横滑与角色独立横滑已建立结构；大量数据滚动交互与最终单屏密度留后续任务验收。

Task 01 到此停止，等待用户审核或明确继续指令。
