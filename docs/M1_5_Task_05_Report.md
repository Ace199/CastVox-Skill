# M1.5 / Task 05：声音池

日期：2026-10-15（Asia/Shanghai）。结果：**PASS；完成后停止，未进入 Task 06。**

## 实现

- Mock API 提供独立的 6 个官方/用户音色候选，不混用项目音色 ID。覆盖明确属性、unknown、不可用等状态，所有名称/ID/属性均虚构，不宣称真实 MiniMax 支持。
- 候选卡片包含本地扁平人物 SVG、纯色底块、音色名称、来源、性别/声音特征及可用性标签；统一 144px 行高，长名称截断保留 title。
- 关键词（名称、ID、可靠标签）、来源与声音特征可组合筛选，输入即更新；过滤只读取有来源的元数据，不从名称或头像推断属性。示例“甜美女声（属性未确认）”仍为性别 unknown，不能进入女声筛选结果。
- 点击/键盘选择候选自动切到右侧探索更多并显示对应详情；没有选择时显示“请选择声音”。项目音色详情与声音池详情通过明确上下文区分。
- 选择只查看详情，不分配角色、不写默认草稿、不加入项目库。筛选隐藏已选项时保留详情并标注“不在筛选结果中”；加载成功/失败后清除失效候选详情。
- 空结果有说明；开发面板可模拟加载失败、空列表和恢复数据；失败后有用户手动重试入口。加载器忽略过时成功/失败，避免并发演示状态相互覆盖。
- 不可用音色可查看原因，显示“不可用”；unknown 可用性明确未确认。本项没有试听/保存/分配操作可误用于这些候选。
- “下方添加更多”保留普通说明文字，无点击监听和按钮化处理。此前项目音色库、角色分配、默认草稿及 Debug 交互均保留。

## 文件

| 文件 | 内容 |
|---|---|
| `web/js/modules/sound-pool.js` | 新增独立声音池、即时筛选、状态呈现及候选详情 |
| `web/js/catalog.js` | 属性归一、来源文案和组合筛选 |
| `web/js/catalog-loader.js` | 集中加载动作、错误捕获、过时响应保护 |
| `web/js/mock/catalog.js` | 6 个官方/用户虚构候选 |
| `web/js/api.js` | 异步内存 Mock 列表、失败/空列表选项与事件 |
| `web/js/store.js` | 声音池状态/筛选/选择，与项目详情上下文分离 |
| `web/js/modules/workspace.js`、`web/js/app.js` | 模块接入及探索更多详情联动 |
| `web/js/modules/debug-panel.js` | 失败/空列表/恢复演示入口 |
| `web/assets/portrait-narrator.svg`、`portrait-reader.svg`、`portrait-soft.svg` | 本地扁平人物向量素材，不使用外部图片请求 |
| `web/css/studio.css` | 筛选条、候选卡、标签与滚动；池区最小高度 310px，工作区高度 854–1000px |
| `web/index.html`、`web/README.md` | 阶段标识、使用说明与边界 |
| `web/tests/core.test.js`、`web/tests/browser.cjs` | 新增声音池测试并保留既有回归 |
| `web/qa/task05/` | 结果、截图及受保护文件哈希证据，既有 Task 证据未覆盖 |

## 实际验证

**模块测试 13 PASS，浏览器检查 28 PASS，0 FAIL。** Chrome 154.0.8037.98，复用已有 Playwright 和浏览器；在获准的沙箱外只访问本机 HTTP，不下载依赖。

```powershell
node --test web/tests/core.test.js
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
```

- 组合筛选、即时更新、空结果、Mock 来源过滤、unknown 不被名称误分类：PASS。
- 卡片点击/Enter 的详情 ID、探索更多 Tab、焦点保留、当前候选被筛选隐藏的提示：PASS。
- 有激活角色时选择池区候选，任务绑定、项目输入与默认保存状态全部不变：PASS。
- 不可用候选可查看原因；Debug 模拟失败、手动重试、空列表、恢复，失败时清除候选详情：PASS。
- 模块层 Mock 结果隔离、错误、筛选、选择作用域、加载竞态保护：PASS。
- 布局与历史功能回归：1920/1440/1280/1024/851/850/768/390/320px，无非预期页面横向溢出；压力数据含 120 个项目声音、120 个声音池候选和 80 个角色，内部滚动及既有角色/项目库独立滚动通过。
- 截图发现初版卡片被网格压矮，已固定卡片行高并扩大池区；新增“卡片内名称/标签未裁切、桌面首张卡完整可见”断言，最终通过。已查看桌面、选中详情和窄屏截图。
- HTTP 页面脚本/console 错误、HTTP 失败、外部请求、业务请求均为 **0**。请求只包括同源静态资源，未调用真实 API。
- `makesound/`、`schemas/`、`wireframes/`、`examples/` 共 **27 个受保护文件 SHA-256 一致，0 修改**；未访问或修改真实凭据及真实项目配置。

证据：`web/qa/task05/browser-results.json`、`protected-before.json`、`protected-files.json`、`desktop.png`、`pool-selected.png`、`dense-desktop.png`、`narrow.png` 等。

## 运行与限制

项目根执行 `python -m http.server 8765 --bind 127.0.0.1 --directory web`，打开 http://127.0.0.1:8765/ 。请使用 HTTP，直接双击 HTML 仅显示启动提示。

本项仅实现 Mock 浏览、筛选、详情及异常演示；未实现真实音色查询、声音池试听、模型选择、加入项目库/角色池或真实持久化。参数编辑仍留后续任务。只实测现有 Chrome，未实测其他浏览器或真实移动设备，未重跑 M1 Python 测试。所有 Mock 状态刷新重置；矮桌面窗口允许预期纵向滚动。
