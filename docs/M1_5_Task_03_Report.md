# M1.5 / Task 03：项目音色库

日期：2026-10-15（Asia/Shanghai）。结果：**PASS，完成后停止，未进入 Task 04。**

## 基线与实现

工作区未找到最新长卡片草图或独立头像；只有此前高保真参考图。本次以用户明确的文字结构为依据，不宣称与未提供草图逐像素一致。未调用图像生成，采用本地中性头像 SVG 占位，不用头像、颜色或名称推断音色真实性别。

- 项目声音卡为统一 **340×56px 横向长卡**，间距 **12px**。从左到右为纯色底头像、试听按钮、名称、常显设置按钮；不采用此前方形卡片。
- 男声、女声各一行；存在无法可靠分类的声音时显示“其他”行。只有存在来源说明且明确 gender 为 male/female 时进入对应行。所有类别共用唯一 `.library-scroll`，不存在逐行同步偏移的误差。
- 大号 `01` 与分类标识在横向滚动容器外，保持固定；长名称 ellipsis，保留完整名称的 title 与按钮可访问名称。
- 卡片主体、试听与设置使用三个兄弟按钮，无嵌套按钮或父卡片点击处理器。Hover 只改变阴影/颜色，头像和试听按钮不位移。
- 主体选择记录 `library.card.select` 并显示选择反馈；未提前实现任务角色绑定。
- 设置记录 `library.settings.open`，将右侧切到基础设置，显示对应音色名称及 ID；参数编辑留后续任务。
- 试听播放本地 2 秒 WAV 提示音，明确标注“非真实音色”；可停止。loading / playing / stopped / ended / error 进入集中状态和事件日志。没有真实语音或 MiniMax 请求。
- 既有统一工作台、声音池、Tab、Mock API 与 Debug 功能保留。Debug 可查看对象 ID、操作结果、错误及完整状态。

## 文件

| 文件 | 变化 |
|---|---|
| `web/js/modules/project-library.js` | 新增独立长卡组件、元数据分类、选择/设置/试听事件 |
| `web/js/modules/workspace.js` | 挂载项目库、选择反馈、基础设置对应声音上下文 |
| `web/js/store.js` | 新增 UI 选择、详情及试听状态，不修改 M1 Schema |
| `web/css/studio.css` | 长卡布局、固定标识、头像底色、常显按钮、截断与反馈 |
| `web/assets/avatar-placeholder.svg` | 中性头像占位 |
| `web/assets/mock-preview.wav` | 标准库生成的 2 秒本地提示音，16kHz/单声道/16bit |
| `web/index.html` | Task 标识、允许同源 media；业务 connect 仍禁止 |
| `web/tests/core.test.js`、`web/tests/browser.cjs` | 分类/状态测试及长卡、事件、滚动验收 |
| `web/README.md` | 使用方式、事件及限制 |
| `web/qa/task03/` | 本次浏览器结果和截图；Task 01/02 证据保留 |

未修改 Python Core、M1 Schema、真实凭据或旧 Wireframe。

## 验证

**Node 模块测试 6 PASS；实际 Chrome 浏览器验收 18 PASS；0 FAIL。**

```powershell
node --test web/tests/core.test.js
$env:NODE_PATH = 'C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser.cjs
```

- 核验长卡尺寸、四项水平顺序、常显设置与 Hover 前后几何位置一致。
- 验证选择声音不会自动切换设置；设置另一个声音后显示正确名称/ID；事件名与对象 ID 精确对应，不额外产生卡片点击事件。Debug 表格有对应操作记录。
- 实际 HTMLAudio 播放成功并停止本地提示音；音频操作只产生 preview 事件，不改变已打开的声音详情。未验证真实设备扬声器的听感。
- 键盘可依次聚焦主体、试听、设置并操作。320px 下聚焦设置会滚动露出对应按钮。
- 120 个声音、80 个角色与极长名称压力数据：卡片尺寸与 12px 间距一致；共享容器滚动 180px 时男女行都移动 180px，编号和分类坐标不变；名称确实截断。
- 继承 Task 02 的桌面/窄屏边界、内部滚动、滚动位置保留及 Task 01 的 Debug/Mock/刷新重置检查，均通过。
- Console/脚本错误、HTTP 失败、外部请求、真实业务请求均为 **0**。音频和 SVG 只作为同源静态资源加载。
- 已查看桌面、压力桌面和窄屏截图。窄屏固定宽长卡可部分显示，横滑或键盘聚焦可访问右侧设置；页面本身无横向溢出。

证据：`web/qa/task03/browser-results.json`、`desktop.png`、`dense-desktop.png`、`mobile.png`、`narrow.png`。

## 运行与限制

项目根执行 `python -m http.server 8765 --bind 127.0.0.1 --directory web`，打开 http://127.0.0.1:8765/ 。打开 Debug 后点击卡片、试听或设置即可核对事件与状态。

头像是占位，最新草图像素细节尚无法核对；Mock 提示音不是语音，也不能用于判断音色。未实现角色绑定、参数编辑或保存。仅实测已有 Chrome 154.0.8037.98，未实测其他浏览器/真实移动设备、音频设备或 M1 Python 回归；浏览器测试复用已有环境并在获准的沙箱外访问本机服务。

## 桌面打开问题修正

用户截图显示从磁盘直接打开 `web/index.html`，ES Modules 未初始化，原页面只显示页头。已在实际浏览器复现该入口，并在 `web/index.html` 增加无需脚本即可显示的启动提示与本机 HTTP 地址；`web/css/studio.css` 添加提示区布局。正常 HTTP 启动后提示会被工作台替换。

`web/tests/browser.cjs` 新增 file:// 入口回归，预期模块加载限制在独立浏览器上下文中验证。最终 **19 项浏览器检查 PASS**，HTTP 页面控制台错误与外部/业务请求仍为零。直接双击 HTML 仍不作为支持的完整运行方式；需保持本地 HTTP 服务运行。
