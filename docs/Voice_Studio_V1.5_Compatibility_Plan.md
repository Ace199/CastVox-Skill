# Voice Studio V1.5 数据兼容与前端删减方案

日期：2026-10-15。基线：`doc/MakeSoundSkill_PRD_V1.5_2026-10-15.md` 及用户本轮明确要求。本文记录实施前已在会话中提交的兼容判断；不是已执行的数据迁移。

## 核查结论

| 需求 | M1 现状 | 本轮处理 |
|---|---|---|
| 男声／女声／其他分类 | `validation.metadata()` 已允许 `gender`、`source` | 复用 `metadata.gender`；`source=user_selected`，仅表明用户分类，不代表厂商确认 |
| MiniMax Voice ID | `ref` 已支持 provider / region / voice_id | 沿用；region 使用 `configured`，不猜测真实地区 |
| 逐音色固定 Model | `voice()` 不允许直接带 model；只有项目级 project_settings.model | Studio Mock 记录独立 model；通过 `toM1Voice()` 去除扩展字段，再以独立 project_settings.model 投影并校验单条 MiniMax 配置 |
| 跨厂商项目库 | `reference()` 明确只接受 minimax | 火山仅存 `studio_schema_version=1.5-mock` 的内存配置；禁止投影进 M1 |
| models / default_model | M1 config_loader 只提取凭据及地域，兼容忽略额外字段 | 新增只读 Studio 查询适配器，提取并验证模型元数据；原 loader 不变 |
| 默认与任务 | M1 已支持独立直接默认及冻结 Job | Mock 默认复制 Provider/Model/ID；当前任务绑定复制完整记录，重绑定不追改快照 |
| Question/Answer | M1 尚无已实现的 Studio Wait/Resume 服务 | 使用明确标记的 Mock 适配协议，含 project_id/job_id/question_id/answer_id；不宣称真实 Harness 接收 |

`metadata.gender` 是当前 M1 可兼容的分类载体，无需添加 `gender_category`。旧数据没有分类或来源时进入“其他”，不按名字推断。

## 后续最小显式迁移提案（未执行）

1. 单独批准新版本 Project Preset Schema，为每条声音／默认增加 model，并注册新的 Provider 引用类型；不可直接将 Mock JSON 写入 M1 1.2 文件。
2. 迁移前锁定 revision、创建备份；旧 MiniMax 声音按旧解析优先级取得有效模型，无法唯一确定时进入 needs_review，不能用当前 default_model 猜测旧任务模型。
3. 已有 `metadata.gender/source` 原样保留；缺省分类只在 UI 显示“其他”。不强制重建旧项目。
4. 旧 Job Snapshot 字节及哈希不变。新 Job 冻结逐声音有效 Provider/region/model/ID；旧读取器继续读旧 Schema，新读取器显式支持两版。
5. 增加迁移往返、失败回滚、并发 revision、跨厂商拒绝／不降级、默认独立及历史快照回归后，再接真实原子项目保存。

本轮不创建任何真实 `.makesound/preset.json`，不修改 schemas、makesound 或用户凭据。也不将项目当前默认 Provider 随表单选择切换。

## 前端删减／保留

| 对象 | 最终状态 |
|---|---|
| 01 项目音色短卡、头像、三分类共用滚动、绑定序号 | 保留并适配 metadata 分类 |
| 02 当前对话需求、独立滚动、分配后亮色、角色头像 | 保留轻量当前任务交互，无增删角色或复杂角色管理 |
| 固定项目默认、明确确认、主 CTA 完成设置 | 保留，三个保存／提交动作独立 |
| 右侧复杂设置工作台 | 替换为添加项目声音和 More Tools 两个 Tab |
| 03 官方声音池、筛选、探索更多、试听生成／缓存／播放器 | 停用，当前入口无引用 |
| Voice Clone / Design、手动表演参数 | 停用，More Tools 只占位 |
| 原前端及旧测试 | 保存于 `archive/voice-studio-full-m1.5/web/`，旧 QA 留作历史证据 |
| M1 Core、Manifest／字幕／缓存／续跑设计 | 保留；本轮没有实现 M2 |

## 数据流

`只读 Provider config.json → Python 脱敏模型描述器 → GET /api/providers → 右侧表单草稿 → 显式 Mock 保存／默认确认 → 项目声音列表 → 当前角色绑定 → 校验当前 Question → Mock Answer 回执`

只有 Provider 元数据读取通过 HTTP；声音保存及回答只在内存。没有 Provider 网络客户端或收费操作。

火山字段说明依据[官方任务提交文档](https://docs.volcengine.com/docs/DoubaoVoice/Tasksubmission?lang=zh)：该接口存在 speaker 和资源标识，不能套用 MiniMax 请求体。网页只引导并保存 Mock 标识，未实现其请求契约、鉴权或合成 Adapter；真实音色控制台入口及部署配置路径仍待确认。
