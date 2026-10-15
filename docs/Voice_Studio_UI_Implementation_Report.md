# Voice Studio UI Implementation Report

日期：2026-10-15（Asia/Shanghai）。阶段：M1.5 / Task 08。结果：**自动化验收 PASS；待用户视觉审核，完成后停止。未进入 M2。**

## 范围与设计依据

依据项目 [PRD V1.3](../doc/MakeSoundSkill_Voice_Studio_PRD_V1.3_2026-10-15.md)、[Visual Direction V1](../doc/MakeSoundSkill_Voice_Studio_Visual_Direction_V1_2026-10-15.md)、[M1 报告](M1_Implementation_Report.md)、保留的 Wireframe/交互评审与 Task 01～07 报告。

工作区已有整体参考图 `doc/扁平风中文语音工作室仪表盘.png`。未找到可独立核实为用户最新确认版的高保真图、长卡草图文件或单独头像素材；没有将这个缺口描述为已经逐像素还原。遇到较早视觉文档与后续文字要求冲突时，采用用户后续确认的横向长卡、常显设置按钮及单屏工作台结构。没有从参考截图裁切头像，也未引入参考图中的额外导航功能。

技术栈保持 HTML5 / CSS3 / Vanilla JavaScript ES Modules；运行时零第三方依赖，无构建步骤。现有 Web 为原生模块，没有 React 工程迁移或删除。

## Task 08 关键变更

| 文件 | 作用 |
|---|---|
| `web/css/tokens.css`（新增） | 统一纸色、黑/蓝/红/黄及辅助色、可读状态色、4px 间距阶梯、系统中文字体、2/3px 描边、零模糊硬阴影和过渡时长 |
| `web/css/studio.css` | 统一色块、控件、Tab、选中描边、焦点、禁用和加载反馈；保持长卡与独立滚动几何结构；不使用渐变/玻璃/柔光 |
| `web/index.html` | 加载 Tokens、几何品牌色块、键盘跳转链接、保留 HTTP 启动指导；移除任务编号型临时页头 |
| `web/js/modules/project-library.js` | 长卡使用仓库原创人物 SVG 和 Token 底色；装饰图按 ID 选取，不推断声音性别 |
| `web/js/modules/settings-panel.js`、`assignment-actions.js` | 试听和保存过程提供 `aria-busy`、明确进度文案和禁用反馈；保留参数与保存门槛 |
| `web/js/modules/dialog-focus.js`（新增）、`requirements.js`、`assignment-actions.js` | 修复确认弹窗 Tab 循环焦点问题，三个弹窗共用处理；保留 Escape 和关闭后焦点返回 |
| `web/assets/README.md`（新增） | 说明原创 SVG、装饰用途、本地提示音与素材来源边界 |
| `web/tests/browser.cjs` | 保留 37 项检查，新增 6 项尺寸、基本可访问性、焦点、加载、配色/减少动态效果及错误恢复检查；证据写入 task08 |
| `web/README.md` | 更新启动、测试、视觉、素材、证据与已知限制 |
| `web/qa/task08/` | 新截图、机器测试记录、保护文件哈希、浏览器记录与旧 Wireframe 回归独立副本；保留旧验收证据 |

样式保留项目音色库与需求共享上方外框，下方独立声音池，右侧三个 Tab；左/右约 60:40。项目卡片仍为 340×56px、间距 12px；所有分类共用一个横滑容器，角色条独立横滑。选中角色同时有特殊描边、蓝色底边、分配符号和文字。布局变窄时上下堆叠，卡片不无限撑宽。

本次检查发现红底普通深色小字对比约 4.09:1，使用专用深色文字 Token 后提升至约 4.79:1。基础检查覆盖的 8 组文字/背景均达到 4.5:1；这不是完整可访问性认证。

## 架构与 Mock 边界

- `store.js` 集中状态；`editor.js` 管理对象草稿与有效参数签名；页面模块按区域拆分。
- `api.js` 是内存 Mock：工作区、目录、试听、项目库与 revision；不发业务网络请求。`events.js` 记录事件名、对象 ID、结果、错误，最多 100 条，可通过 Debug 查看。
- 不同角色、项目声音、候选和默认目标保留独立编辑上下文；基础/探索 Tab 共享同一对象草稿。能力冲突保留原情绪并要求用户主动选择兼容项。
- 试听仅返回同一个 2 秒本地提示音。签名包括声音、模型、文本及有效参数；过期结果不能解锁应用。加入项目库需名称，重名需旧引用和 revision 确认，失败保留草稿；模拟成功才同步到捕获的当前任务角色。
- 普通角色仅影响当前任务，项目默认经独立确认；管理模式不虚构角色目标。保存、缓存、默认均在内存，刷新重置，不写 localStorage 或真实项目配置。
- CSP `connect-src 'none'`；静态素材同源加载。没有 MiniMax SDK/真实调用、真实音色生成、真实 Question/Answer 提交或 Agent 恢复。通用接口保持供 Codex / Claude Code 后续衔接，没有其他 Agent 适配。

## Task 01～08 验收汇总

以下 PASS 指本次回归达到各项原型验收标准，不替代用户最终视觉确认。

| Task | 范围与关键验收 | 本次结果 |
|---|---|---|
| 01 前端基础 | HTTP/ES Modules、Mock 返回/错误、可开关 Debug、事件及状态、无业务网络 | PASS |
| 02 页面布局 | 上方单框含 01/02、独立声音池、默认探索 Tab、桌面/窄屏及有界溢出 | PASS |
| 03 项目音色库 | 横向长卡、固定编号分类、同步横滑、常显设置、事件独立、长名截断与大量声音 | PASS |
| 04 角色需求 | 默认固定且分割、独立角色滚动、角色绑定/参数不串、默认明确确认、无真实写入 | PASS |
| 05 声音池 | Mock 官方/用户、即时组合筛选、详情联动、unknown、不可用、空结果及错误恢复 | PASS |
| 06 右侧设置 | 基础/探索共享草稿、上下文切换、完整句可编辑、能力禁用原因、不静默覆盖 | PASS |
| 07 试听与分配 | 缓存/过期/失败/重复点击、角色与项目库闭环、同名确认/revision 冲突/重试、管理模式/默认/摘要 | PASS |
| 08 视觉与回归 | Tokens、纯色/粗描边/硬阴影、状态、素材来源、指定尺寸、键盘/基础可访问性、已有测试回归 | PASS |

没有为实现后续 Task 删除已验收功能；原始 Wireframe 与 Python Core 均保留。

## 最终验证证据

| 测试 | 结果 | 证据 |
|---|---|---|
| Node 模块与流程 | 25 PASS，0 FAIL / SKIP | [unit-results.tap](../web/qa/task08/unit-results.tap) |
| Chrome UI 回归 | 43 PASS，0 FAIL | [browser-results.json](../web/qa/task08/browser-results.json) |
| Python M1 全部离线测试 | 49 PASS，0 FAIL / ERROR / NOT RUN | [m1-results.json](../web/qa/task08/m1-results.json) |
| 旧 Wireframe 回归 | 24 PASS，0 FAIL | [Wireframe_QA_Results.json](../web/qa/task08/legacy/Wireframe_QA_Results.json) |
| 保护范围哈希 | 27 个文件，0 修改 | [protected-results.json](../web/qa/task08/protected-results.json) |

浏览器为 Chrome 154.0.8037.98，Python 3.13.10，Node 24.12.0。复用本机已有 Playwright 和 Chrome，没有联网安装测试工具。

指定视口 1920×1080、1440×900、1280×720、390×844、320×640 均无页面横向溢出，面板边界位于视口内。1920×1080 内容恰好一屏；1440×900、1280×720 的页面内容高 1014px，允许纵向滚动。声音池与详情仍在内部滚动；不宣称矮窗口内所有操作同时可见。

大量数据检查使用 120 个项目声音、120 个声音池候选、80 个角色及长名称，覆盖独立滚动、固定编号、稳定尺寸、卡片截断、键盘滚动定位。键盘检查覆盖跳转、可见焦点、Tab 页方向键、角色方向键/Home/End、弹窗循环和 Escape；加载反馈使用真实 Mock 操作触发后验证。

自动化监听记录：HTTP 应用脚本/控制台错误 **0**、失败 HTTP 资源 **0**、外部请求 **0**、业务请求 **0**。直接打开 file:// 的模块限制在隔离上下文中单独检查启动指导，不计入 HTTP 控制台结果。

人工检查本地预览中的初始空详情、角色分配、候选切换、Mock 试听与加入角色链路，见 [浏览器检查记录](../web/qa/task08/Browser_Check_Record.md)。完整尺寸截图、空/错误状态截图也列于该记录。

保护检查覆盖 `makesound/`、`schemas/`、`wireframes/`、`examples/` 的原 27 个文件，SHA-256 均一致。M1 测试使用自有临时假配置与网络阻断；未读取或修改真实 API 凭据。

## 启动与复验

在项目根目录运行并保持服务开启：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

打开 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)。直接双击 HTML 不支持 ES Modules，页面提供启动指导。Ctrl+C 停止服务。默认本地开发入口可打开 Debug，`/?dev=0` 隐藏开发工具。

```powershell
node --test web/tests/core.test.js web/tests/flow.test.js
python tests/run_m1.py --output web/qa/task08/m1-results.json
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
$env:WIREFRAME_CHROMIUM = $env:STUDIO_CHROMIUM
node web/qa/task08/legacy/check-legacy.cjs
```

不同电脑请指向已有 Playwright/Chromium 安装。测试不自动下载依赖。旧 Wireframe 检查使用本次保留的源码副本，独立输出，原检查脚本未修改。

## 未验证与剩余限制

- 最新确认参考图的版本身份和独立头像授权文件未在工作区找到；目前使用项目原创示意 SVG，最终视觉仍需用户审核。
- 未验证 Safari/Firefox、实体触屏及屏幕阅读器；环境无 axe-core，完成的是基础标签/键盘/焦点/配色检查，未宣称完整 WCAG 合规。
- 音频为提示音，不能评价 MiniMax 音色或参数效果；保存、冲突、缓存与 Agent 数据都是 Mock。真实持久化、业务协议联调与 MiniMax 集成留待另行授权的阶段。
- 当前阶段完成后停止；未进入 M2。
