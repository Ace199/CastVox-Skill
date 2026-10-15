# Voice Studio 最新参考图与交互更新

日期：2026-10-15。范围：本轮参考图、声音池双击/播放、角色绑定标记、分配明暗以及共用音色名称。结果：**完成，等待审核，停止于 M1.5**。本报告覆盖此前报告中被本轮反馈替换的交互。

## 最新有效规则

| 区域 | 实现 |
|---|---|
| 页头 | 参考新的 Bauhaus 几何图形，原创 SVG；不从截图裁图。重复的红色返回栏已按用户最新反馈完整移除，没有引入无业务的历史/设置导航。 |
| 声音池卡片 | 较大头像区、名称和标签，独立圆形播放按钮，保持男声蓝绿、女声红粉、其他黄橙。现为 192px 高，列表在区域内滚动。 |
| 声音池单击 | 只选中候选，不切 Tab、不修改编辑草稿、不跳转或分配。 |
| 声音池双击 | 打开此音色基础设置；窄屏定位下方设置长卡。键盘 Space 选中、Enter 打开设置。 |
| 声音池播放 | 仅明确 `available` 的音色提供独立播放/停止键；unknown/不可用无播放键。播放本地 Mock 提示音，不代表真实音色、不生成有效试听凭据、不解锁分配。 |
| 01 前方标记 | 未绑定任务角色显示灰色方框；绑定后显示对应 02 序号。不是新增的独立复选操作，点击卡片主体仍按当前目标绑定。两个角色显示两个序号，超过两个显示首个和其余数量，完整序号可从提示/可访问描述查看。 |
| 02 明暗 | **已分配才亮色；未分配保持暗色，即使被点击也不变亮。** 切换当前角色不改变已有绑定的亮色。额外描边单独表示当前编辑目标。 |
| 02 分类 | 按已绑定音色使用男声蓝绿、女声红粉、其他黄橙。未知/未分配为暗黄橙。不从名字或头像推断。分类随任务绑定冻结，避免别名重绑定影响其他角色的分类。 |
| 名称与按钮 | 公共“音色名称”在上；“加入角色池”在左、“加入项目库”在右，桌面、390px、320px 都同一行。两者均验证名称。 |
| 加入角色池 | 当前参数试听成功后，将名称和配置仅应用到当前任务角色；不增加或修改项目音色库。 |
| 加入项目库 | 共用名称用于项目内别名，仍执行唯一性、同名明确确认及 revision 约束；模拟保存成功后按原闭环更新捕获的角色。 |

原有 240×56px 项目横向短卡、常显设置、01/02 共用外框、默认声音快速确认、声音池折叠、主要完成 CTA、共享参数、缓存/过期及 Mock Harness 通知保留。未进入 M2。

## 关键文件

- `web/index.html`、`web/css/studio.css`、`tokens.css`：页头、移除重复栏、声音池视觉、角色明暗、灰框/序号、共用名称与并排按钮。
- `web/assets/bauhaus-header-v1.svg`：原创参考风格几何图形；原生成图片资产保留。
- `web/js/modules/sound-pool.js`：独立的单击、双击、Enter、播放/停止、结束/错误与折叠停止。播放按钮与卡片主体是兄弟控件，没有嵌套按钮或事件串线。
- `web/js/store.js`、`editor.js`、`workspace.js`：`SELECT_POOL_VOICE` 只选中；`OPEN_POOL_SETTINGS` 才激活编辑器；播放状态集中可查。
- `web/js/voice-presentation.js`：明确来源分类与实际声音引用对应的角色序号映射。
- `web/js/modules/project-library.js`、`requirements.js`：灰框/序号与亮色分配态；局部角色名称显示。
- `web/js/assignment-flow.js`、`modules/assignment-actions.js`：共享音色名称验证、任务局部名称、左右按钮；空名称提示不提供无关项目库恢复操作。
- `web/tests/core.test.js`、`flow.test.js`、`browser.cjs`：保留状态隔离/缓存/重绑定/Mock 提交回归，按新入口和命名语义更新预期。
- `web/README.md`、素材说明：更新当前操作和证据路径。

没有修改 M1 Python Core、Schema、真实项目文件或凭据。新增 `voiceGender` 仅为 UI 任务绑定的分类快照，不修改 M1 数据格式。

## 验证

| 检查 | 结果与证据 |
|---|---|
| 前端状态/流程 | **31 PASS，0 FAIL/SKIP**；[unit-results.tap](../web/qa/reference-update/unit-results.tap) |
| Chrome UI | **52 PASS，0 FAIL**；[browser-results.json](../web/qa/reference-update/browser-results.json) |
| M1 全部离线测试 | **49 PASS，0 FAIL/ERROR/NOT RUN**；[m1-results.json](../web/qa/reference-update/m1-results.json) |
| 保护文件 | 原 27 个文件 SHA-256 一致，0 修改；[protected-results.json](../web/qa/reference-update/protected-results.json) |

新增验证覆盖：单击不改变编辑器/角色/默认；双击及键盘打开；4 个明确可用候选有播放键，另 2 个没有；播放/停止不选中、不跳转、不解锁分配；没有嵌套按钮；未绑定灰框、单角色/多角色序号和更换绑定；点击未分配角色仍暗、已分配切换后仍亮；共享名称必填、角色名称不入项目库；1440/390/320px 左右按钮顺序。

保留指定 1920×1080、1440×900、1280×720、390×844、320×640，以及断点和 120 项目声音/120 候选/80 角色的滚动压力检查。无页面横向溢出，页面允许纵向滚动。HTTP 应用控制台/脚本错误 0、失败资源 0、外部请求 0、业务请求 0。播放器仅请求同源静态 WAV，不调用 MiniMax 或其他收费语音服务。

本轮曾复现新增标记挤占卡片主体中心点击区域的问题；已让主体中心位于名称区，试听/设置保持独立命中，原有三按钮事件回归通过。声音池增高后同步增加可视区域，桌面第一排头像、名称和标签完整可见。

## 截图

- [最新桌面整体与角色亮色](../web/qa/reference-update/final-desktop.png)
- [窄屏整体](../web/qa/reference-update/final-narrow.png)
- [未分配灰框及暗色](../web/qa/reference-update/unassigned-gray-markers.png)
- [多角色序号绑定](../web/qa/reference-update/role-binding-markers.png)
- [共享名称与左右按钮局部](../web/qa/reference-update/shared-name-actions-detail.png)
- [命名操作：桌面](../web/qa/reference-update/shared-name-actions-desktop.png)、[窄屏](../web/qa/reference-update/shared-name-actions-narrow.png)

## 运行与限制

项目根目录执行：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory web
```

打开 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)，更新后刷新页面。测试命令和现有 Playwright/浏览器路径见 [README](../web/README.md)，证据写入 `web/qa/reference-update/`；旧证据保留。

窄屏检查使用桌面 Chrome 的视口模拟，没有验证实体手机双击手势、Safari/Firefox 或屏幕阅读器。键盘 Enter 提供等价设置入口。试听、项目保存和 Harness 通知均为 Mock；没有验证真实音色、真实持久化或真实 Harness。完成后停止，等待审核。
