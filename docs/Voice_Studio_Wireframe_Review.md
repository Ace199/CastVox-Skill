# Voice Studio 低保真线框图 · 01 / 02 评审说明

日期：2026-10-15（Asia/Shanghai）。

本轮范围：在 M1 后、M2 前确认信息结构、动作范围与接口缺口。仅交付本地自包含 HTML；没有实现网页服务、音频管线或任何真实 API。产品验收平台仍仅 Codex 与 Claude Code，核心不绑定 Harness。

## 交付与使用

- [01 首次使用 / 无默认配置](../wireframes/Voice_Studio_Wireframe_01.html)
- [02 缺失项目音色别名补全](../wireframes/Voice_Studio_Wireframe_02.html)
- [实际浏览器检查结果](../wireframes/qa/Wireframe_QA_Results.json)
- [检查脚本](../wireframes/qa/check-wireframes.cjs)

直接用浏览器打开 HTML 即可，不需要服务、安装插件或连接网络。每个文件内嵌完整样式与交互脚本；另一文件仅为可选的场景导航目标。所有声音、模型、项目和任务均为虚构数据。刷新重置，不读写真实配置，也不使用 localStorage。

采用 [Effective HTML / html-wireframe 指引](https://github.com/plannotator/effective-html/blob/main/skills/html-wireframe/SKILL.md) 作为设计参考：灰度、系统字体、方框、语义控件与少量点击交互；未安装插件。遵循用户要求，未做高保真视觉或多种视觉方向。

## 已有规则与本稿取舍

**Docs-Verified**：原始 PRD V1.2 §4–5、§10 和现有 Harness Adapter 设计是产品规则依据；这表示文件内容已核对，不表示功能均已实现。

| 规则 / 场景 | 本稿呈现 |
|---|---|
| 首次缺配置必须由用户确认 | 默认落 Voices；声音与模型未选，不允许提交预览。初始语速、导出和字幕仅是建议 |
| 三个独立意图 | “应用本次”按钮；“设为项目默认声音”复选框；“添加项目音色库”复选框与名称。另有仅保存按钮，明确不启动生成 |
| 默认声音无需项目别名 | 首次默认勾保存默认声音，添加别名不勾；预览显示直接引用 Voice ID |
| 主动编辑不得默认回写 | 场景 02 两个保存项均不勾选；原项目默认与其他段落绑定单独展示 |
| 保存范围独立 | 保存默认声音包括当前声音参数，不改写导出、字幕等项目默认。本稿未提供完整“保存全部设置”入口 |
| 缺别名不可静默回退 | 提示“男声音1”缺失，预筛选男声，显式选择后才能确认；未知性别不在男声筛选结果内 |
| 网页最终选择优先 | 允许取消筛选并明确选择其他声音；预览提示需要记录约束覆盖，不把取消筛选本身当作已提交 |
| 任务回答不等于默认修改 | 预览分别列出本次、项目默认和项目库意图；仅保存后任务仍等待回答 |
| 等待超时不等于问题过期 | 异常演示仅说明回答持久化与用户手动继续；不是网页主动向 Agent 发消息，也不是重复发起付费请求 |

**Proposed / 待用户审核的交互取舍**：

1. 两个场景均先选声音，Settings 只展开基础参数，Outputs 暂不展开。
2. 缺失别名允许用户明确“仅本次替代第二段”，不创建别名。下次使用“男声音1”仍提示补全；不能宣称项目库已修复。选择添加别名后按钮改为“补全别名并应用于第二段”。此行为符合显式直接声音引用的方向，但具体交互尚未通过用户评审。
3. 补全页不默认勾选添加别名，预填“男声音1”。勾选后该补全入口要求保留原名称；其他命名由未来项目库管理入口处理。
4. 仅保存不会回答当前任务；新增别名后仍需明确应用，再让 Agent 继续。其实际事务与 Question revision 如何更新需在 M3 实现前确认。

## 页面需要的接口能力

下表是**能力需求，尚未确定 HTTP 路由或新增 CLI 命令**。不把草图当成可运行 API。

| 能力 | M1 已有事实（源码核对） | 后续需要补齐 / 验收 |
|---|---|---|
| 加载项目、默认、别名和 revision | PresetStore / 项目音色库 / config show 可读；项目写入要求可信绝对根 | Studio 返回可信项目上下文与可写范围；无项目根禁用项目保存，不能从任意 CWD 推断 |
| 候选与筛选 | 本地全局资产、项目别名可列出；官方声音列表明确未实现 | Provider 候选与可信属性来源、可用性状态；没有元数据不能猜真实性别。本稿声音仅 fixture |
| 本次只读解析 | config resolve 支持 assignments、约束、直接引用和优先级 | 将表单草稿转换为可审查的绑定差异；未提交不能生成、保存或覆盖声音 |
| 直接默认 / 添加别名 | set-default 允许直接引用；aliases add 可与设默认在同一项目文件原子完成 | UI 明确传保存意图；默认声音与导出设置分别更新，未勾选字段不能顺带覆盖 |
| 重名 / 版本冲突 | revision CAS、显式旧引用和确认保护重绑定 | 显示冲突与旧→新差异；保留草稿，重新读取后再次确认。新增失败不能静默变重绑定 |
| 局部最终选择 | M1 assignments 可按 target 指定声音 | **当前单个 studio_submission.voice 在 choose() 中对每个 target 生效**；不能直接用于“仅 p002”。需增补带范围的选择或在经过验证的回答处理中更新指定 assignment，并保留其他绑定 |
| 提交 Answer 与保存意图 | M1 仅校验调用方提供的 applied 结构与项目/Job 身份，有明确警告 | 真正的 Question/Answer Store、TTL、幂等、授权与原子可恢复提交；配置 CAS 与回答状态不能半成功 |
| 仅保存 | M1 配置写入可独立执行 | 不生成 Answer.applied，不触发 ResumeIntent；更新 revision 后对待答 Question 有明确处理规则 |
| 等待与恢复 | M1 只有配置快照，不是完整运行器 | 短 wait、已保存回答的领取、同 Job 幂等恢复；过期问题与单次 wait 超时必须区别处理 |

### 范围明确的 Answer 草图（非 M1 有效输入）

延续统一 Question / Answer / ResumeIntent，而非增加平台专有协议。以下是用于评审的新增字段草图，**不可直接传给 M1 CLI**；M1 严格校验会拒绝未知字段。

```json
{
  "question_id": "DEMO_QUESTION",
  "answer_id": "DEMO_ANSWER",
  "job_id": "DEMO_JOB",
  "project_id": "DEMO_PROJECT",
  "expected_revision": 7,
  "selection": {
    "scope": "targets",
    "targets": ["p002"],
    "requested_alias": "男声音1",
    "repair_mode": "task_only_replacement",
    "voice": {
      "ref": {
        "kind": "provider_voice",
        "provider": "minimax",
        "region": "cn",
        "voice_id": "FAKE_MALE_B"
      }
    },
    "constraint_overrides": []
  },
  "save_intents": {
    "project_default_voice": false,
    "project_alias": null
  }
}
```

- `scope=targets` 只能覆盖明确目标；`scope=task_default` 仅作用于未显式分配的部分。这是新增范围语义的提案，不能沿用“一个 Studio voice 覆盖所有段落”。
- “补全别名”与“仅本次替代”分开记录；后者在任务中保留原请求审计，但有效绑定必须改为直接声音引用，不能继续解析不存在的别名。
- 服务器校验项目、Job、Question、目标集合、有效模型与地区、revision、问题 TTL 和授权，生成/核验幂等标识；禁止信任浏览器自行宣称 applied。
- 保存默认或添加别名与 Answer 需要可恢复事务。跨文件不能靠逐个写 JSON 冒充全有或全无；具体 journal/提交策略待设计。单文件 aliases add+default 的原子性不证明整个 Answer 事务已完成。
- 仅保存与提交本次回答为不同操作。等待已结束时可持久化回答，再由用户复制含真实 job_id 的继续指令；自动消息投递不在当前范围。

## 验证结果与边界

**Observed / PASS**：实际 Chromium 浏览器检查 24 项通过，0 失败；桌面 1440px、窄屏 390px 与 320px 均无水平溢出。检查涵盖必填阻断、三个意图的组合、仅保存、缺别名仅本次替代、男声过滤、清除过滤后明确覆盖、文本安全呈现、键盘切换页签、冲突与超时提示、刷新重置。页面脚本错误 0，页面外部 HTTP 请求 0。

已打开检查两页桌面与 390px 截图。桌面采用列表 / 确认两列，窄屏按同一顺序堆叠；窄屏需要纵向滚动，未制作移动端专用交互。

证据在 `wireframes/qa/`：`Wireframe_QA_Results.json`、四张截图和可重跑脚本。浏览器最初在沙箱内无法启动，后使用获准的本机 Chromium 完成检查；未安装依赖或更改权限设置。脚本依赖现有 Playwright，可通过 `NODE_PATH` 指向已安装模块，`WIREFRAME_CHROMIUM` 指定已有浏览器；不需要联网安装。

**NOT RUN / 未实现**：真实保存、Question/Answer 原子事务、TTL/CSRF/授权验证、实际 revision 竞争、原 Agent 等待与恢复、真实候选查询、试听、MiniMax、字幕与生成。原型的冲突和超时检查仅验证提示交互，不验证真实机制。M1 的既有 49 项测试结果沿用原报告，本轮没有重跑或扩展后端测试。

本轮未修改 M1 Python 代码、MiniMax 凭据、原 PRD 或既有 M1 报告；未实施 M2/M3。下一审查节点是确认上述交互取舍及 target 范围语义，再安排 M2；不以交付线框图自动视为产品评审通过。
