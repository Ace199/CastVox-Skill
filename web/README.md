# Voice Studio · V1.6 UI Mock

原生 HTML / CSS / JavaScript ES Modules。新版视觉使用暖白、钴蓝、明黄、细墨色描边和少量硬阴影；人物来自 `assets/man`、`assets/women`、`assets/unknow`。头像底框缩小并向右下错位，未分配浅色，已分配亮色。当前任务未分配时保留灰底问号，分配后沿用声音人物。默认区按最新确认使用同一行的三张卡片：默认声音、默认男声、默认女声；全部可空、独立保存。

## 启动

从项目根目录运行已有服务：

```powershell
python studio_server.py --port 8766 --config-dir web/tests/fixtures/providers
```

打开 http://127.0.0.1:8766/ 。前端更新后刷新即可，服务接口更新后需重启服务。不要双击 HTML：模块和脱敏模型查询需要 HTTP 服务。

厂商下的「打开配置文件」使用 Windows 记事本打开当前服务读取的 JSON。带 `--config-dir` 时操作该目录的测试配置；不带此参数启动时，MiniMax 使用 `Path.home() / '.config/minimax/config.json'`。已有文件不改写，缺失时新建 `api_key: "write your own keys"`、`region: "cn"`、`base_url: "https://api.minimax.cn"`、`models: []`、`default_model: null`。填写并保存后点击「重新读取模型」。占位 Key 不能用于鉴权，空模型列表显示尚未配置模型。文件内容不返回网页。火山引擎不创建 MiniMax 格式的凭据模板；已指定且存在的测试配置可以打开，否则入口禁用。

## 交互范围

- 三分类声音共享横向滚动，标签固定；角色需求独立滚动。
- 先点默认卡，再点有效声音只修改草稿，保存仍需确认。三个默认都可空，任务分配与默认独立。
- 添加／声音设置／More Tools 三 Tab；厂商草稿隔离；新增不覆盖同名声音；已有来源只读。
- 语速与声调按已验证能力描述器显示，未知能力禁用。隔离 fixture 的示例范围明确标为 Mock，不代表真实模型能力。
- 同卡 Hover 两秒显示删除；设置面板和键盘也可删除。软删除保留引用，支持撤销和名称冲突处理。
- 本地试听支持播放、暂停、调整前、不可用及更新状态；同时只播放一个。两个 WAV 是本地生成的 6／7 秒测试纯音，不是厂商音色。
- 更新试听仅模拟替换已有样本，不实现生成、上传或音频提取。
- 全部业务只保存内存，刷新重置。完成设置只模拟当前任务 Answer，不保存草稿、不通知真实 Harness。
- Debug 显示事件与状态，可模拟失败、冲突和试听状态；`?dev=0` 隐藏 Debug。

## 前端测试

在项目根目录运行：

```powershell
node --test web/tests/v16.test.js
$env:NODE_PATH='C:/Users/63201/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
$env:STUDIO_CHROMIUM='C:/Program Files/Google/Chrome/Application/chrome.exe'
node web/tests/browser-v16.cjs
node web/tests/live-ui-smoke.cjs
```

其他机器改为实际依赖和浏览器路径。浏览器测试自建随机端口 Node Mock 服务，不启动 Python 或导入 Core，阻止外部请求和业务写请求。

结果与截图：`qa/v16/`。报告：`../docs/Voice_Studio_V1.6_UI_Implementation_Report.md`。旧 V1.5 测试与结果仅作历史资料。

`live-ui-smoke.cjs` 需要先启动本地服务，默认访问 8766（可用 `STUDIO_URL` 指定回环地址）。真实服务截图与结果在 `qa/visual-refresh/`；仅在独立浏览器中执行内存 Mock 分配，不提交配置、不打开凭据文件、不调用收费 API。视觉实现详见 `../docs/Voice_Studio_V1.6_Visual_Refresh_Report.md`。

本地配置按钮专项测试：`python web/tests/test_config_editor.py`，使用隔离临时文件和模拟编辑器，验证新建、不覆盖、错误脱敏与同源请求限制，不执行 M1 Core 测试。真实编辑器窗口显示未纳入自动化检查。
