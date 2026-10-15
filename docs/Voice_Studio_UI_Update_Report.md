# Voice Studio UI Update Report

日期：2026-10-15（Asia/Shanghai）。结果：**本轮交互与美术更新完成，自动化 PASS；等待用户审核，停止在 M1.5。**

本次以用户最新文字、长卡截图和分类配色要求为准；粘贴说明用于补充交互意图。它们覆盖了此前“声音池打开探索更多”、340px 长卡和窄屏 400px 设置卡等旧规则。没有扩大到真实 Harness、MiniMax 或 Python Core。

## 完成内容

| 要求 | 实现与验收 | 状态 |
|---|---|---|
| 01/02 共用上方大框 | 保留单一外框与内部结构 | PASS |
| 项目长卡缩短 | 340×56 → **240×56px**；头像→试听→名称→常显设置，间距仍 12px；男女/其他共用横滑，编号分类固定 | PASS |
| 分类统一配色 | 项目库和声音池头像底块：男声蓝绿 `#4ecdc4`、女声红粉 `#f381a4`、其他/unknown 黄橙 `#f2b544`；依据明确元数据，名称含“女声”但属性未知仍用黄橙 | PASS |
| 不可用音色 | 保留类别色，不再变灰；虚线边框和“不可用”文案表明状态，仍能查看、不能生成有效试听/分配 | PASS |
| 声音池入口进入基础设置 | 候选上下文及草稿保留，窄屏定位下方设置卡；不会直接分配声音 | PASS |
| 01 设置自动收起 03 | 打开对应基础设置，同时收起声音池；窄屏滚动并聚焦设置区，不清空筛选和状态 | PASS |
| 声音池手动展开/收起 | 有明确按钮与 `aria-expanded` / `aria-controls`，收起只保留标题；筛选、候选选择和列表节点保留 | PASS |
| 完成设置主 CTA | 02 底部全宽、22px 粗体、至少 56px 高、黄色强对比与硬阴影；说明“提交本次角色配置 · 通知 Harness（Mock）”完整可见 | PASS |
| 默认声音快速确认 | 点默认声音直接打开候选/确认弹窗；不进入底部编辑器，不更改角色目标；选项目库声音，确认才 Mock 保存，取消不改数据 | PASS |
| 窄屏设置长卡 | 850px 以下上下排列；设置卡最小高度 1050px、内容自然展开，参数/试听/结果/分配操作可通过页面滚动看到 | PASS |
| 探索更多保留 | 模型和音色选择、扩展属性仍可访问，与基础设置共享对象草稿；初次默认采用基础设置 | PASS |
| 少量生成装饰图 | 内置 imagegen 生成两张透明 PNG，分别用于页头和音色生成占位区；装饰图不承担按钮功能，未裁取截图 | PASS |
| Debug 可观察 | 保留事件名、对象 ID、结果与错误；新增折叠、快速默认、基础设置打开、完成 CTA 与 Mock Harness 通知事件 | PASS |

“下方添加更多”保持说明文字。音色生成只占位。先试听后应用、缓存签名、过期结果、失败保留草稿、同名旧引用/revision 确认、管理模式和角色隔离均保留。

## 默认声音与 Harness 的明确边界

默认声音弹窗使用项目库声音的已保存参数，避免把右侧未保存草稿静默带入项目默认。弹窗候选变化不修改项目或角色；确认时检查项目默认 revision 和项目库 revision，过期则拒绝保存。项目库为空/候选不可用时不能确认。想把池中候选设为默认，先完成试听并加入项目库，再在快速弹窗选择。

“完成设置”先显示实际已应用角色摘要：有未分配角色时提示并阻止通知；全部分配后调用 `api.notifyHarness({ projectId, jobId, assignments })`。这个通用接口复制包含角色 ID 和配置的快照，等待本地 Mock 延迟并返回 `mock:true/status:acknowledged`，同时记录 `harness.mock.notified`。进行中防重复点击。没有发送真实 HTTP/聊天消息，没有恢复 Agent、执行 CLI 或启动合成。

真实 Harness 的传输方式、Answer 协议和确认回执仍未联调；这次不将 UI Mock 回执冒称真实通知成功。

## 关键文件

- `web/css/tokens.css`：新增三类声音配色 Tokens。
- `web/css/studio.css`：短卡、主 CTA、声音池折叠布局、窄屏长卡、装饰图尺寸与不可用状态。
- `web/index.html`：页头装饰图。
- `web/js/store.js`：默认基础设置、折叠状态、快速默认的候选/取消/确认及 revision 防护。
- `web/js/modules/project-library.js`、`sound-pool.js`：分类色映射、候选基础入口、展开/收起按钮。
- `web/js/modules/workspace.js`：设置入口自动折叠、窄屏滚动和焦点、相关事件。
- `web/js/modules/requirements.js`：全宽完成 CTA、快速默认选择确认；保留角色独立状态。
- `web/js/modules/settings-panel.js`：占位区装饰；参数与试听闭环保留。
- `web/js/modules/assignment-actions.js`、`web/js/api.js`：完成前检查、摘要与 Mock Harness 回执。
- `web/tests/core.test.js`、`web/tests/browser.cjs`：更新被新需求取代的入口/尺寸预期，补充新路径；未删除保存/缓存/冲突回归。
- `web/assets/studio-microphone-v1.png`、`studio-waves-v1.png`：新生成插画；[完整提示词与来源](../web/assets/Generated_Artwork_Notes.md)。
- `web/README.md`：重写为当前有效操作、启动与测试说明，避免旧交互说明冲突。
- `web/qa/ui-update/`：本次独立截图、测试结果、保护哈希；原 Task 01～08 证据保留。

## 验证结果

| 验证 | 结果 | 证据 |
|---|---|---|
| 前端模块/流程 | **28 PASS，0 FAIL/SKIP** | [unit-results.tap](../web/qa/ui-update/unit-results.tap) |
| Chrome UI 回归 | **47 PASS，0 FAIL** | [browser-results.json](../web/qa/ui-update/browser-results.json) |
| M1 全部离线测试 | **49 PASS，0 FAIL/ERROR/NOT RUN** | [m1-results.json](../web/qa/ui-update/m1-results.json) |
| 保护文件哈希 | **27 个文件，0 修改** | [protected-results.json](../web/qa/ui-update/protected-results.json) |

浏览器 Chrome 154.0.8037.98。检查脚本拦截外部请求并监听控制台：脚本/控制台错误 0、失败 HTTP 资源 0、外部请求 0、业务请求 0。图像生成调用独立的内置 imagegen；上述网络计数指前端原型本身，没有 MiniMax 调用。

覆盖 1920×1080、1440×900、1280×720、390×844、320×640，均无页面横向溢出；另保留 851/850px 等断点与 120 个项目声音、120 个声音池候选、80 个角色压力检查。桌面测试内容高约 1120px，窄屏展开状态约 2524–2585px：本次明确优先长卡可读与自然纵向滚动，不宣称所有内容一屏可见。收起声音池后大幅减少窄屏占用；01 设置入口定位已验证在视口顶部附近。

新增/更新检查包含：三类颜色与 unknown、不可用类别色；短卡顺序与 Hover 稳定；池折叠后筛选/选择保留；基础设置入口；窄屏长卡和焦点；快速默认取消/确认/过期 revision 及编辑器不变；主 CTA 尺寸与说明不裁切；完整与缺失角色的 Mock 通知；两张装饰素材同源加载。键盘、弹窗焦点、模型情绪、过期试听、命名保存、冲突与重试回归通过。

手动在内置浏览器刷新后确认：默认声音直接弹窗，取消后不保存；01 设置打开基础设置并使 03 按钮变为“展开声音池”；重新展开后点击池卡片，面板关联为 `tab-basic`；未分配齐全时完成摘要明确显示“未通知 Harness”。

## 截图

- [桌面整体](../web/qa/ui-update/final-desktop.png)
- [390px 窄屏整体长卡](../web/qa/ui-update/final-narrow.png)
- [窄屏：01 设置后自动收起并定位](../web/qa/ui-update/narrow-settings-collapsed.png)
- [窄屏默认快速弹窗](../web/qa/ui-update/narrow-default-quick.png)
- [完成设置及 Mock Harness 回执](../web/qa/ui-update/assignment-summary.png)
- [生成装饰图的占位区效果](../web/qa/ui-update/decoration-placeholder.png)

## 启动与复验

项目根目录：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

打开 [本地原型](http://127.0.0.1:8765/)，不要直接双击 HTML。

```powershell
node --test web/tests/core.test.js web/tests/flow.test.js
python tests/run_m1.py --output web/qa/ui-update/m1-results.json
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
```

使用已有工具，没有下载框架或测试依赖。`makesound/`、`schemas/`、`wireframes/`、`examples/` 的 27 个原文件 SHA-256 一致；没有修改或读取真实 API 凭据。

## 假设与未验证

- 依据“基础设置成为主面板”，初始 Tab 也调整为基础设置；探索更多保留为显式切换入口。
- 快速默认弹窗仅选项目库已保存声音；没有新增真实持久化或池中候选绕过试听直接设默认的流程。
- 当前使用本机 Chrome 与内置浏览器验证；未验证 Safari/Firefox、实体触屏、屏幕阅读器或完整 WCAG 合规。
- 装饰图为生成插画，有少量绘制明暗；页面 CSS 保持纯色背景和硬阴影。两图仅装饰，不替换原有 SVG 人物头像。
- Harness/试听/保存均为 Mock；真实接口与持久化没有验证。无待阻塞本轮交付的问题，最终视觉待用户审核。完成后停止，未进入 M2。
