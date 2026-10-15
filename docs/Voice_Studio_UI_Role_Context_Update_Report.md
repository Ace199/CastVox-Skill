# Voice Studio 基础设置角色上下文更新

日期：2026-10-15。范围：角色选择前置提示、角色信息继承与固定图标。结果：**完成，等待审核；仍停留在 M1.5。**

## 当前行为

- 未选 02 角色时，基础设置只显示“请选择角色”和提示，隐藏参数、试听、名称与应用操作。点击项目设置或双击池中候选也不会绕过该提示。Tab 名称仍为“基础设置”，提示位于内容区。
- 选中角色后，显示角色名和图标，并沿用该角色的声音、参数、模型、试听文本及音色名称。未分配角色的音色名称初始采用角色名；已分配角色采用该角色保存的音色名称。
- 首次打开新的项目声音/候选时，继承当前角色正在编辑的有效草稿；再次打开则保留该对象的修改。相同声音在不同角色下分别存储编辑草稿，避免参数、名称或试听结果串角色。
- 02 卡片与基础设置使用同一个角色图标。图标在任务载入时从三个已有本地 SVG 中随机分配，同一任务会话内切换角色、Tab、候选或重新载入相同任务时保持。刷新后是新的 Mock 会话，可以重新分配。
- 图标不作为声音性别依据，原有男声蓝绿、女声红粉、其他黄橙及“已分配才亮色”规则保留。
- 加入角色池或项目库后，角色保存的名称、声音和参数会同步；切换回来仍沿用已应用的信息。Mock 加入项目库的卡片同时沿用该角色图标。
- 探索更多保留独立声音管理能力，无角色时仍可通过探索更多编辑、试听并模拟加入项目库。默认声音快速确认保持原样。

## 关键变更

| 文件 | 修改 |
|---|---|
| `web/js/store.js` | 任务图标映射、同任务图标复用；名称写入当前对象草稿 |
| `web/js/editor.js` | 从当前角色继承参数/文本/名称；项目与候选草稿按任务/角色隔离 |
| `web/js/modules/settings-panel.js` | “请选择角色”门槛、角色名与图标；无角色时隐藏基础编辑操作 |
| `web/js/modules/requirements.js` | 02 卡片显示固定角色图标 |
| `web/js/assignment-flow.js` | 应用/保存后同步角色草稿；捕获角色图标，避免异步保存串目标 |
| `web/js/api.js`、`modules/project-library.js` | Mock 项目声音保存并展示角色图标，仅接受原有本地头像白名单 |
| `web/css/studio.css` | 角色图标、上下文标题、窄屏未选角色提示布局 |
| `web/tests/` | 按新角色前置规则更新预期，补充继承、隔离与图标一致性验证 |
| `web/README.md` | 更新当前操作、测试与会话边界 |

图标和草稿均为 UI/Mock 状态，没有修改 M1 Schema、Python Core、真实项目配置或凭据。没有增加真实 MiniMax/Harness 调用。

## 验证

| 测试 | 结果 | 证据 |
|---|---|---|
| 前端状态/流程 | **32 PASS，0 FAIL/SKIP** | [unit-results.tap](../web/qa/role-context/unit-results.tap) |
| Chrome 浏览器 | **54 PASS，0 FAIL** | [browser-results.json](../web/qa/role-context/browser-results.json) |
| M1 离线 | **49 PASS，0 FAIL/ERROR/NOT RUN** | [m1-results.json](../web/qa/role-context/m1-results.json) |
| 原保护文件 | **27 个文件，0 修改** | [protected-results.json](../web/qa/role-context/protected-results.json) |

新增检查验证：初始无角色提示及隐藏操作；角色 B 的 speed=0.9、volume=0.8、已保存名称；编辑后切换角色/Tab仍保留；同一候选在角色 A/B 下独立继承；02/基础设置图标 src 一致；同任务重复载入图标不变；Mock 项目保存后的头像一致；返回角色时名称与参数仍正确。

现有声音池单击/双击/播放、绑定序号、分配亮色、共享名称左右按钮、默认快速确认、缓存/过期、保存冲突/重试、管理模式与 Mock Harness 回归保留。指定桌面/窄屏与大量数据布局检查通过；HTTP 应用控制台/脚本错误、失败资源、外部请求及业务请求均为 0。

## 截图

- [未选角色提示](../web/qa/role-context/choose-role.png)
- [角色信息与头像：桌面](../web/qa/role-context/role-context-desktop.png)
- [角色信息与头像：窄屏](../web/qa/role-context/role-context-narrow.png)

## 运行与限制

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

打开 [本地原型](http://127.0.0.1:8765/)，更新后刷新。测试命令见 [README](../web/README.md)；本次证据独立存于 `web/qa/role-context/`，此前记录保留。

仍只验证本机 Chrome 与窄屏模拟，未验证实体手机或完整屏幕阅读器行为。头像只在 Mock 会话内稳定，未做跨刷新持久化。试听/保存/Harness 通知继续为 Mock。完成后停止，等待审核。
