# Voice Studio

持久化服务使用 `studio_v16_server.py`，项目声音、默认值、任务角色与 Answer 通过 SoundMaker Core 保存。网页只负责声音管理和绑定，不直接发起付费合成。启动、配置和生成流程见 [使用说明](../docs/usage.md)。

## 开发启动

在仓库根目录运行，目标项目必须已存在：

```powershell
python studio_v16_server.py --project '<existing-absolute-project-path>' --fake --config-dir web/tests/fixtures/providers
```

使用服务实际返回的随机回环 URL。`--fake` 是开发测试选项，测试静音不代表真实声音质量。内存 Mock 服务仍可用 `python studio_server.py --port 8766 --config-dir web/tests/fixtures/providers`，刷新会重置其业务状态。

## 结构

`index.html`、`css/`、`js/` 和 `assets/` 构成静态界面。`js/transport.js` 与 `persistent-api.js` 连接持久化服务，`mock-api.js` 提供隔离测试实现；store、controller、view 和功能面板负责状态与交互。`tests/fixtures/providers` 只包含假凭据和测试模型。

## 测试

```powershell
node --test web/tests/v16.test.js web/tests/i18n.test.js web/tests/delete-hover.test.js
python web/tests/test_config_editor.py
python web/tests/test_provider_config.py
```

浏览器测试需预先准备 Playwright/Chromium，可运行 `node web/tests/browser-v16.cjs`、`node web/tests/bilingual.cjs` 和 `node web/tests/defaults-completion.cjs`，分别覆盖综合界面、中英文及默认确认完成流程。本机依赖位置用 `NODE_PATH`、`STUDIO_CHROMIUM` 设置，不在源码硬编码个人目录。浏览器截图和测试报告属于本地过程产物，不提交仓库。`live-ui-smoke.cjs` 需先启动服务并设置正确的 `STUDIO_URL`；运行前查看脚本的具体操作范围。
