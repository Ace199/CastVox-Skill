# M1.5 / Task 02：Voice Studio 页面布局

日期：2026-10-15（Asia/Shanghai）。结果：**PASS；完成后停止，未进入 Task 03。**

## 关键变化

- `web/js/modules/workspace.js`：项目音色库和当前需求合并到一个 `.assignment-workspace` 外框，内部用分隔线区分；声音池仍为独立容器。右侧保留基础设置 / 探索更多 / 音色生成，默认探索更多，生成仅占位。
- `web/css/studio.css`：桌面双栏约 60:40、最大宽 1600px；工作区高度 720–1000px，上方区域至少 480px，池区至少 160px。矮窗口允许页面纵向滚动；列表数量不会扩大页面宽度或工作区高度。
- 项目库共享横向滚动，角色独立横滑、默认声音固定；声音池与右侧详情正文内部纵向滚动。长名称有固定卡片尺寸、ellipsis 和完整 title。
- 850px 及以下改为上下堆叠，上方容器最高 560px、声音池 320px、详情 400px。
- Tab / Debug 开关不重建数据列表，避免清空滚动偏移；Task 01 Debug、Mock API 和日志功能保留。
- `web/index.html` 更新阶段标识；`web/README.md` 补充布局与测试说明。
- `web/tests/browser.cjs` 扩展布局验收，证据写入 `web/qa/task02/`，保留 Task 01 原有证据。

未修改 Python Core、Schema、真实凭据、旧 Wireframe 或原有 Mock 数据；未实现角色分配、参数编辑、试听、保存等业务逻辑。

## 实际验证

**模块测试 4 PASS、0 FAIL；Chrome 浏览器验收 14 PASS、0 FAIL。**

```powershell
node --test web/tests/core.test.js
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
```

浏览器版本：154.0.8037.98。浏览器测试在获准的沙箱外执行，仅访问临时本机 HTTP 服务，拦截外部请求，不下载依赖。

- 常规布局检查宽度：1920、1440、1280、1024、851、850、768、390、320px。桌面左右边界/上下对齐、需求卡片完整可见、窄屏堆叠、页面无横向溢出均 PASS。
- 压力数据：120 个声音、80 个角色，包含极长中英文名称；由测试临时注入内存 Store，不写入正式 Mock 文件。覆盖 1440×900、1024×600、851×900、850×900、390×844、320×640。页面无横向溢出，声音池有内部纵向滚动，项目库和角色条有独立横向滚动，工作区尺寸稳定。
- 滚动检查：默认声音横向位置固定；切换 Tab、打开 Debug 后，项目库/角色/声音池偏移保持；插入 80 段详情文本后正文滚动，右侧外框高度不变。
- Task 01 回归：HTTP/ES Modules、Mock 返回/错误、Debug 事件/清空/开关/状态、键盘 Tab、开发模式关闭、刷新重置均 PASS。
- 控制台/脚本错误、HTTP 失败、外部请求和业务请求均为 **0**。
- 已查看最终常规桌面、压力桌面及窄屏截图。初版截图发现需求区截断和长名称挤高行，已修正，并增加需求区完整可见断言后通过最终测试。

证据：`web/qa/task02/browser-results.json`、`desktop.png`、`dense-desktop.png`、`mobile.png`、`narrow.png`。

## 启动与限制

项目根目录：`python -m http.server 8765 --bind 127.0.0.1 --directory web`，打开 http://127.0.0.1:8765/ 。

本阶段为布局验收，不代表最终高保真视觉或业务交互完成。矮桌面窗口和窄屏的页面纵向滚动是预期行为，内部横滑不是页面横向溢出。仅实测现有 Chrome，未实测 Firefox、Safari、真实移动设备或屏幕阅读器；未重跑 M1 Python 测试。
