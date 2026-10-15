# Voice Studio UI 更新报告（当前基线 V1.5）

日期：2026-10-15，Asia/Shanghai。文件名沿用用户指定的 `Voice_Studio_V1.4_UI_Update_Report.md`；实施与验收以随后上传的 PRD V1.5 为准。

**本轮结果**：双栏、右侧双 Tab、分类项目声音、轻量角色分配及 Provider-aware Mock 配置已实现；只读 Provider/Model 查询已接通。未迁移真实项目预设，未接真实 Harness 或厂商合成，未进入 M2。

## 1. 需求与兼容审查

已核对 PRD V1.5、V1.4、M1 实现报告、validation/config_loader/project_voice_library、当前前端及历史 01/02 组件和视觉参考。V1.5 覆盖 V1.4 删除轻量角色需求的旧条款；不恢复复杂角色管理或 03 声音池。

当前工作区只有旧完整工作台参考图，最新消息没有额外可访问的两张新图文件；最终结构按用户最新文字要求和 V1.5 实施，不宣称逐像素复刻未取得的图片。保留原头像、配色、粗描边与硬阴影，没有生成插画或另开视觉探索。

详细兼容方案见 [V1.5 兼容计划](Voice_Studio_V1.5_Compatibility_Plan.md)。关键结论：

- 分类使用 M1 已有 `metadata.gender/source`，不添加新持久化字段。
- M1 不接受火山引用或声音对象内 model；本轮用明确标记 `1.5-mock` 的内存 Studio 记录，不能直接写为 M1 preset。
- `toM1Voice()` 仅投影单条 MiniMax 记录；model 单独映射 project_settings.model 并用实际 M1 Validator 检验。它不是完整混合厂商项目迁移器。
- `config_loader.py` 原样保留，可兼容忽略 models/default_model 扩展；Studio 独立读取两项字段，不改变凭据校验语义。
- 27 个基线受保护文件 SHA-256 无变化。实际本机凭据在只读模型查询前后哈希相同，没有输出内容。

## 2. 实施步骤和文件

| 步骤 | 关键文件 | 结果 |
|---|---|---|
| 结构调整 | `web/index.html`、`web/js/view.js`、`web/js/sections.js`、`web/css/` | 左侧一个完整管理区；三行共用滚动、固定标签、轻量需求独立滚动；右侧添加项目声音／More Tools |
| 交互修正 | `web/js/store.js`、`controller.js`、`api.js`、`validation.js` | 草稿集中管理、分类必选、添加／改名／重绑定、默认确认、任务回答和冲突重试 |
| Provider 配置 | `studio_server.py`、`web/js/providers.js`、`app.js` | localhost 脱敏查询、只读 models/default_model、厂商说明／链接／模型／字段切换 |
| 调试与归档 | `web/js/events.js`、`debug.js`、`dialog-focus.js`、`archive/voice-studio-full-m1.5/` | 开关 Debug、事件／错误、失败和 revision 注入；历史完整工作台可追溯 |
| 验证与说明 | `web/tests/`、`web/qa/simplified/`、`web/README.md` | 自动化、截图、运行与限制说明 |

页面不加载官方声音池、探索更多、复杂基础设置、内置试听生成／缓存／播放器、Voice Clone/Design 或手动情绪／语速／音量控件。原 Python 业务模块及 Manifest、字幕、缓存、恢复设计均保留。

## 3. 保存、默认和回答

1. 添加／修改项目声音：必填 Provider、已配置 Model、名称、音色标识、用户分类。名称 NFC 规范化且项目内唯一；改名不得覆盖另一别名。
2. 身份／模型／现有配置更新会展示差异并确认，保存检查旧 ref 和 revision。取消不写入；冲突保留草稿，重新读取后重试。
3. 默认声音固定入口可快速选择项目声音并确认；右侧也支持只填身份、不命名而设默认。默认为独立拷贝，不随别名重绑定改变。
4. 角色选择仅切换当前目标，选声音才绑定；未分配保持暗色，已分配始终亮色。蓝绿／红粉／黄橙来自明确分类；头像随角色保持稳定。
5. “完成设置”校验未保存草稿、Question 和必要声音，汇总角色；未分配角色只有在已明确设置项目默认时才可使用默认。回答冻结 Provider/Model/ID 和当前配置，不改项目默认，也不生成音频。
6. Mock 回答包含 project_id/job_id/question_id/answer_id，幂等接收并返回 `mock=true, can_generate=false`。该接口是未来统一协议的 Mock 边界，M1 尚无可投递的真实 Studio/Harness wire protocol。无 Question 时禁止虚假提交／续跑。

所有保存和回答只在内存，刷新重置。未读取或修改真实 Project Preset、Job Snapshot，也没有构造假持久化成功。

## 4. Provider / Model 查询

- `GET /api/providers` 只返回固定厂商说明、官方链接、models、default_model、模型配置状态及来源；不返回原始 config、api_key、base_url 或异常正文。
- 默认 MiniMax 路径为 `Path.home() / '.config/minimax/config.json'`。实际读取结果：配置存在，但 models 尚未配置；没有判断 API Key 无效，也没有补写模型。
- 字符串数组及 `{id,name}` 模型数组均可读取；default_model 不属于列表时警告并不选默认。模型列表不是账号鉴权／开通证明。
- 切厂商重新加载模型并清空 ID；名称和分类保留，同厂商旧草稿可明确恢复。已保存记录和默认声音不随配置默认模型变化。
- 火山目前只支持引导和 Mock 配置。真实配置路径、鉴权、resource_id 等请求映射尚未实现；默认显示未配置／待接入。测试模式从明确的隔离 fixture 目录读取模型，不冒充真实可合成。
- 火山字段说明依据[官方任务提交接口](https://docs.volcengine.com/docs/DoubaoVoice/Tasksubmission?lang=zh)，仅据该接口使用 speaker 标签，不声称所有火山产品共享同一字段契约。

## 5. 测试结果

| 验证 | PASS | FAIL / SKIP | 证据 |
|---|---:|---:|---|
| JavaScript 逻辑／实际 M1 投影校验 | 16 | 0 / 0 | `web/qa/simplified/unit-results.txt` |
| 只读配置、缺失／非法模型、默认、脱敏和 loader 兼容 | 8 | 0 / 0 | `provider-test-results.txt` |
| 原有 M1 离线回归 | 49 | 0 / 0 | `m1-results.json` |
| Chrome 浏览器交互和布局 | 27 | 0 / 0 | `browser-results.json` |

浏览器覆盖：三行分类／共同滚动和固定标签、长名截断、添加／编辑／改名、重绑定确认／取消、Tab 草稿与键盘操作、厂商切换和草稿恢复、混合厂商 Mock、模型配置缺失／默认变化、默认独立、角色头像与状态、Question/Answer、失败／冲突／重复点击、管理模式、无试听资源禁用、Debug 开关。

视口检查：1920×1080、1440×900、1280×720、390×844、320×640，全通过。页面允许必要的竖向滚动；声音区和需求区分别横向滚动，无整体横向溢出。

请求拦截仅允许本地静态资源及 `/api/providers` GET；外部厂商请求 0、业务 HTTP 写请求 0、控制台／JS 错误 0、缺失资源 0。配置只读结果见 `compatibility-results.json`。浏览器截图使用隔离 Mock 模型，不能作为真实厂商可用性证明。

## 6. 截图与启动

- [桌面 1440 视口](../web/qa/simplified/studio-1440x900.png)
- [桌面 1920 视口](../web/qa/simplified/studio-1920x1080.png)
- [窄屏 390 视口](../web/qa/simplified/studio-390x844.png)
- [火山配置 Mock](../web/qa/simplified/provider-volcengine-mock.png)
- [More Tools](../web/qa/simplified/more-tools.png)
- [缺少模型](../web/qa/simplified/models-not-configured.png)
- [重绑定确认](../web/qa/simplified/confirm-rebind.png)
- [Mock 回答回执](../web/qa/simplified/answer-receipt.png)

截图为对应视口下的整页截图，文件高度可能大于视口高度。

```powershell
# 项目根目录：可审核示例
python studio_server.py --port 8766 --config-dir web/tests/fixtures/providers
# 另一个端口：只读本机模型配置，业务仍为 Mock
python studio_server.py --port 8767
```

说明和测试命令见 [web README](../web/README.md)。旧 8765 通用静态服务不能提供新的模型查询，应使用上述服务。

## 7. 当前限制与停止点

- 未获准执行 Preset Schema 迁移，因此逐音色 Model／混合厂商的真实原子持久化未实现；现有 M1 格式保持兼容。迁移方案、备份与回滚测试须在批准后单独实施。
- 实际本机 MiniMax 尚无 models，页面如实显示未配置；此轮不补写凭据文件。火山真实配置路径和 Adapter 待接入。
- 本地服务仅提供静态页面和只读元数据；没有完整生产 Question 会话令牌、跨进程持久化回答或 Harness Resume。未冒充完成 M3。
- 没有对应音色且来源合法的本地音频，全部试听按钮禁用；没有用通用提示音伪装真实音色。
- 自动演绎、Chunk Planner、真实音频／字幕、缓存／续跑仍属后续 M2+。本轮测试未进行真实模型鉴权或付费请求。
- 仅做基本键盘、焦点和响应式检查，没有完整屏幕阅读器／WCAG 审计。

本轮完成后停止等待审核，不进入 M2，不开发其他 Agent Adapter。
