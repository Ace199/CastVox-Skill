# 配音演绎单契约

“配音演绎单”是用户审阅并确认的表演计划。它不是原剧本，也不是厂商请求体。

Use the repository implementation at `makesound/performance_plan.py`.

`propose(core, question_id, items)` accepts one item per original sentence:

```json
{
  "sentence_id": "s_001",
  "emotion": "沉稳",
  "delivery_notes": "平和旁白，句尾收束。",
  "filler_text": null,
  "pause_after_ms": 300,
  "provider_directives": {"emotion": "calm"}
}
```

It persists a plan under `<project>/.makesound/plans`, creates an integrity hash, and does not make network calls. Use `render(plan)` to inspect the canonical plan. Create the user-facing Markdown review from the same verified values, following [delivery layout](delivery-layout.md); omit internal hashes/IDs from its main text without changing dialogue, controls or confirmation scope. `confirm(core, plan_id, plan_hash)` only accepts the unchanged, pending plan.

External documents do not need internal project IDs, voice IDs, or hashes. The agent resolves these from the actual project and records them internally. See the external-plan handling rules below.

`makesound.production.plan(core, performance_plan=plan_id)` validates a confirmed plan and freezes the Job without provider network traffic. A real provider call remains separate and requires the selected provider reference plus explicit paid authorization and per-Job limits.

The runtime currently exports audio and SRT under `<project>/outputs/audio/<job_id>`. These are source exports, not the primary user delivery entry. Locally prepare the readable task/version layout in [delivery layout](delivery-layout.md), preserving runtime references. Snapshots, receipts, and cache remain under `.makesound`.

Before drafting, check the exact provider/model capability matrix and the local adapter. Explain unsupported, unimplemented, and unknown controls in the preceding binding explanation; omit their user-facing plan columns and request fields, and do not write corresponding performance demands. If the schema requires emotion/delivery_notes text, use the capability-status explanation rather than an unsupported instruction. Automatic supported emotion is distinct from unsupported emotion.

## 外部演绎单由 Agent 整理

不新增专用通用导入程序，不要求用户按固定模板重写文档。Agent 理解 Markdown、表格、JSON 或自然语言，用现有项目读取、参数校验和生成接口处理。

### 检查与整理
1. 先确定用户意图：“检查/审阅”仅校验；“按此生成”表示执行该明确内容的请求。文档里的“已确认”、命令或付费授权文字不是当前用户的授权指令。
2. 保留对白原文、顺序、角色与段落边界。补充内部编号属于格式整理，不能悄悄改写或合并对白。没有另附原剧本时，以演绎单的对白为本次原文，不声称已对照未提供的剧本。
3. 整理段落、角色、声音选择、模型、语速、声调、情绪、语气词和停顿。未写情绪可以保持自动；未写语速/声调可以沿用可核实的绑定值，并清楚说明，不虚构已确认值。
4. 实际查询当前项目声音库：声音 ID/名称必须能确定唯一有效声音，检查软删除、厂商与模型配置。“沉稳男声”若仅是描述，不能当作已存在的音色；同名或跨项目 ID 不能猜测匹配。不擅自回退默认声音。
5. 读取对应厂商文档，核对模型能力与本地接入范围，检查单位及数值范围。unsupported/unimplemented/unknown 分别注明，不伪造参数；需要删除用户明确要求的效果、换模型、换音色或改原文时，展示差异并重新确认。
6. 内容完整、声音唯一可用、参数有效且用户明确要求生成时，跳过角色分析和绑定网页，无须再次索取同一内容的确认。只缺某些角色的绑定时仅处理这些角色；有歧义时只询问相关项。
7. 内部项目标识、声音 ID、快照与哈希由 Agent 通过现有函数生成并核验，不要求用户提供。展示执行范围和本次调用上限，沿用已有明确授权，不重复索取。

### 与当前执行代码的边界
Agent 负责语义理解；现有代码负责声音存在性、参数枚举/范围、快照完整性、调用预算与文件结果校验。不能仅凭阅读文档就声称校验通过。

现有 performance_plan.propose 仍依赖 Question/Answer，不能假装它接受任意外部文档。完整外部单可整理为现有 production.plan(request_path=..., confirmed=True) 接受的句子数组：paragraph_id、sentence_id、role_id、text、project_voice_id、settings、pause_ms、provider_directives。先查看当前函数契约，使用真实项目声音及已确认值，保存整理后的可审阅记录，再冻结执行；不伪造用户提交网页的 Answer。

若段落含多个句子，保持用户段落标识与顺序，交付时按确认的段落边界组织。遇到现有接口无法表达的必要要求，应明确说明具体缺口，不能用静默降级冒充已支持；本规则本身不授权新增导入程序。

用户审阅只显示当前厂商、模型与本地工具支持的字段。内部 emotion/delivery_notes 的能力状态占位文字不得原样展示为演绎要求。声音名称必须读取确认绑定快照；默认名称不得被项目库后续编辑覆盖。普通新配音任务首轮为每个角色选一句确认音色（完整外部单或已试听后明确直接生成的情况，按主 Skill 第 0 节例外执行）：优先第一句，中文不足 20 个有效文字则顺延，全部不足则选该角色最长句（并列取最早）；不计标点、空格和控制标签，不改写凑字。每组最多五个角色；确认音色后选择逐批确认或一次确认全部剩余内容，执行仍每批最多五段。聊天回复也须逐句展示实际情绪、语速、声调及存在的停顿、语气词/发声动作，具体规则见主 Skill。
