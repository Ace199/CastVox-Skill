# MakeSoundSkill V1.2 能力矩阵（M0）

日期：2026-10-14（Asia/Shanghai）。**Observed** = 本机观测；**Docs-Verified** = 官方文档陈述；**Assumption/Proposed** = 待验证建议。所有 MiniMax 业务调用均 **NOT RUN**。以下 API Schema 为文档摘记，不是实测响应，不是完整机器可读契约。

**最新开发范围**：V1.2 只验收 Codex/Claude Code；下文其他平台均为历史调研，不开发 Adapter。M1 本地配置/音色库/CLI 已通过离线测试，见 [实现报告](M1_Implementation_Report.md)；这不改变真实 Provider 能力仍 NOT RUN 的状态。

## 1. 地区与鉴权

- Observed：指定配置可解析；此前观察 api_key/base_url，用户补设后本轮复查 `region: str = cn`、Base URL 属当前国内域名类别，声明一致；真实密钥未输出。
- Docs-Verified：已读取国内官方页面（旧 `platform.minimaxi.com` 文档链接跳转 `platform.minimax.cn`），当前国内示例为 `https://api.minimax.cn`。国际 Voice Design 示例为 `https://api.minimax.io`。[国内接口](https://platform.minimax.cn/docs/api-reference/voice-design-design)、[国际接口](https://platform.minimax.io/docs/api-reference/voice-design-design)。
- Assumption：配置声明与 URL 一致，表示拟使用国内账号；密钥签发区、实际地址连通性、账户权限仍未认证。不得自动跨区或改写配置。
- 用户已确认：区域是配置项，不写死国内；本轮已复查 region 存在。后续需校验区域与 URL 一致、缺失/冲突可诊断；此次未改配置。

## 2. Provider 能力

表内方法来自各自官方页；Base URL 必须使用经过确认的区域配置。所有动作的真实执行状态为 NOT RUN。

| 能力 | 官方契约摘要（Docs-Verified） | PRD 对应/差异 | M0 结论 |
|---|---|---|---|
| 同步 TTS | `POST /v1/t2a_v2`；JSON+Bearer；`model/text/voice_setting`；返回 `data/extra_info/trace_id/base_resp` | 支持核心配音；内部 `volume` 映射 `vol`，内部情绪 auto 需省略，不能原样透传 | 文档支持；账号、声音/模型组合与解码 NOT RUN。[S1](https://platform.minimax.cn/docs/api-reference/speech-t2a-http) |
| 句/词字幕 | `subtitle_enable` 默认 false，`subtitle_type` 默认 sentence，也列出 word/word_streaming；非流式返回 subtitle_file，流式返回 data.subtitle | 默认句级 SRT 是应用策略，Provider 不直接保证源文句 ID、准确率或 SRT 成品 | 可按文档设计；实际文件字段/单位/URL TTL 尚未取得。[S1](https://platform.minimax.cn/docs/api-reference/speech-t2a-http) |
| 官方/用户音色查询 | `POST /v1/get_voice`；`voice_type=system/voice_cloning/voice_generation/all`；返回相应数组、base_resp | 示例有 ID、名称/描述/时间等，没有已证实可靠的 gender 枚举；描述可能为空 | 不支持仅凭名称证明女声硬条件；新建声音需保留本地登记。[S2](https://platform.minimax.cn/docs/api-reference/voice-management-get) |
| 克隆样本上传 | `POST /v1/files/upload`；multipart，`purpose=voice_clone`、`file`；返回 file.file_id、base_resp | mp3/m4a/wav，10 秒至 5 分钟，≤20mb；是远端写入，M0 不执行 | 文档证实 PRD 建议边界；20mb 十进制/二进制精确定义未证实。[S3](https://platform.minimax.cn/docs/api-reference/voice-cloning-uploadcloneaudio) |
| 快速复刻 | `POST /v1/voice_clone`；必需 file_id 与自定义 voice_id；可选 clone_prompt、试听 text/model 等；返回 demo_audio、审核信息、extra_info、base_resp | 音色 ID 由请求确定，不应强求响应再含 voice_id；需个人/企业认证；未正式使用的音色 7 天删除 | 支持 P0，但没有创建/认证实测；后续复用 ID 不代表生命周期永久。[S4](https://platform.minimax.cn/docs/api-reference/voice-cloning-clone) |
| Voice Design | `POST /v1/voice_design`；必填 prompt、preview_text（≤500 字符）；可选 voice_id、aigc_watermark；返回 voice_id、trial_audio(hex)、base_resp | 设计+试听一次调用；没有已验证独立免费预览/正式保存端点，也没有通用 model 请求字段依据 | P0 保留；真实权限、持久化、失活规则未知。[S5](https://platform.minimax.cn/docs/api-reference/voice-design-design) |
| 本地试听 | 播放已授权取得并缓存的音频是本机操作；生成新的试听属于 Provider 调用 | “试听按钮”不代表免费；缓存无音频时不能偷偷生成 | 本地播放为 Proposed；真实下载/播放 NOT RUN |
| Voice ID 可用性 | 列表不是无副作用合成验证接口；未激活声音可能不出现 | `available/unavailable` 二值不足；应保留 unknown/pending_activation | 不存在本次已验证的通用“免费试合成”能力；不能用 TTS 做 doctor |
| 多音色与三种导出 | 文档列出 timbre_weights；不等于按句切换角色 | PRD 要求声音边界拆 Chunk，属于本地规划与拼接 | Fake Provider 可先验证；真实跨声字幕 NOT RUN |
| 错误/限流/重试 | 示例使用 base_resp.status_code/status_msg | HTTP 200 不足以证明成功；超时后不一定未收费；远端幂等保证未取得 | 具体账户限流、幂等和错误响应实测 NOT RUN |

## 3. Schema 摘记与适配边界

以下仅为字段形状；值为类型占位，不应直接发送，不含任何凭据。

```json
{
  "voice_design_request": {
    "prompt": "string, required",
    "preview_text": "string, required, maxLength 500",
    "voice_id": "string, optional",
    "aigc_watermark": "boolean, optional"
  },
  "voice_design_response": {
    "voice_id": "string",
    "trial_audio": "hex string",
    "base_resp": {"status_code": "integer", "status_msg": "string"}
  },
  "clone_request": {"file_id": "int64", "voice_id": "string"},
  "clone_response": {
    "demo_audio": "string, may be empty",
    "input_sensitive": "boolean",
    "input_sensitive_type": "integer",
    "extra_info": "object",
    "base_resp": "object"
  },
  "upload_response": {"file": {"file_id": "documented ID"}, "base_resp": "object"},
  "voice_list_response": {
    "system_voice": "array",
    "voice_cloning": "array",
    "voice_generation": "array",
    "base_resp": "object"
  }
}
```

以上分别依据 [S2 查询](https://platform.minimax.cn/docs/api-reference/voice-management-get)、[S3 上传](https://platform.minimax.cn/docs/api-reference/voice-cloning-uploadcloneaudio)、[S4 克隆](https://platform.minimax.cn/docs/api-reference/voice-cloning-clone)、[S5 设计](https://platform.minimax.cn/docs/api-reference/voice-design-design)。上传示例 file_id 为字符串，clone 请求标 int64；内部建议用十进制字符串保存，在 Adapter 边界按具体接口严格转换，避免网页 JavaScript 数值精度损失。正式 Schema 尚需补齐；这不是 M1 实现。

克隆自定义 ID：8–256 字符、英文字母开头、允许字母数字及 `-/_`、不能以后两者结尾、不可重复。可选 clone_prompt 示例音频须小于 8 秒，不适用原始克隆素材的 10 秒下限；text 提供时必须提供 model，试听按所选模型计费。[克隆字段说明](https://platform.minimax.cn/docs/api-reference/voice-cloning-clone)

字幕仅取得文档中的传输路径与粒度说明，**未取得真实 subtitle_file 样本**，不确定其字段、时间单位、编码、句界与源文映射及 URL 有效期。TTS `output_format=url` 的 24 小时描述针对音频 URL，不能推导为字幕 URL TTL。首选非流式句级，流式累计字幕需去重覆盖；具体模型以文档能力白名单和后续实测共同限制。[TTS](https://platform.minimax.cn/docs/api-reference/speech-t2a-http)

## 4. 费用与生命周期

**Docs-Verified；2026-10-14 页面报价，不是当前账号账单或未来价格保证。**

| 地区/动作 | 已核对的公开说明 | 不可推出的结论 |
|---|---|---|
| 国内 Voice Design | 9.90 元/音色，首次正式合成使用计入；接口内试听按 2.00 元/万字符 | 不代表设计请求免费，也不代表点“采纳”才扣试听费 |
| 国内 clone | 9.90 元/音色，首次正式合成使用计入；试听按所选模型字符价 | 不代表无试听就允许在 M0 创建 |
| 国内 2.8 TTS | HD 3.50 元/万字符；Turbo 2.00 元/万字符；1 汉字计 2 字符 | 不代表余额足够、所有 Key 可用或失败重试一定免费 |
| 国际 Design 试听 | 接口页写 $30/百万字符，preview_text 必填 | 不能套用国内人民币价格或用国内 Key 试国际接口 |
| clone 未激活 | 文档写复刻后 7 天内未正式调用将删除；列表需要正式使用才可见 | 不是每隔 7 天都必须调用；没有证明使用后永久不失效 |
| design 生命周期 | 返回可用于合成的 ID；查询文档要求成功使用后可查 | 未证明与 clone 相同 7 天规则、无期限持久或任意模型兼容 |

费用来源：[国内定价](https://platform.minimax.cn/docs/pricing/overview)、[国际 Design](https://platform.minimax.io/docs/api-reference/voice-design-design)。生命周期来源：[clone](https://platform.minimax.cn/docs/api-reference/voice-cloning-clone)、[查询](https://platform.minimax.cn/docs/api-reference/voice-management-get)。首次正式使用、接口内试听与一次性音色费的精确账单触发关系，需后续受控测试或官方支持确认；预算保守按可能累加，不把任何创建/试听算免费。

## 5. Harness 与本地能力

| 能力 | 证据 | 结论 |
|---|---|---|
| Python/FFmpeg/ffprobe | Observed：3.13.10 / 8.1.2 / 8.1.2 | 环境版本可用；第三方包与媒体流程 NOT RUN |
| Codex CLI 续跑 | Observed：0.149.1 帮助；官方 exec resume 文档 | 指定 ID 恢复入口存在，实际恢复 NOT RUN |
| 网页回答让 CLI 返回 | Proposed：loopback 服务+持久问答+wait | 技术方案可行性待 M3；不能标 E2E PASS |
| 已结束 Agent 自动唤醒 | 没有本次已验证的通用入口 | 不承诺；使用持久 pending-answer 与用户续跑 |
| 超时后“继续任务”按钮 | 用户已接受持久回答，并提出再次发送请求 | 可定义为同一 Job 的幂等恢复请求；桥接自动发送尚未验证，无桥接时复制续跑指令至原聊天；不能当成重新合成 |
| app-server | 官方线程/轮次与输入请求协议；本地标 experimental | 可选适配路径，不能替代必需的客户端实现 |
| Claude 第二 Harness | Observed：2.1.295 帮助有 resume/continue/stream-json | 仅确认入口；AT-20 NOT RUN |

Harness 来源：[Codex 非交互](https://learn.chatgpt.com/docs/non-interactive-mode)、[App Server](https://learn.chatgpt.com/docs/app-server)。更完整本机记录、差异与用户决策见 [M0_Discovery_Report.md](M0_Discovery_Report.md)；未执行测试及验收门槛见 [Testing_Plan.md](Testing_Plan.md)。

## 6. 新增 Agent 平台矩阵

本节保留历史平台扩展调查。最新 V1.2 验收仅 Codex/Claude Code；Kimi Work/DSH/WorkBuddy/豆包均延期，不开发 Adapter。Docs-Verified 仅指所列官方材料，**全部新增平台实际接入、等待及恢复均 NOT RUN**。

| 平台/入口 | Skill 与本机执行依据 | 等待/任务恢复 | 继续按钮的投递 | 建议结论 |
|---|---|---|---|---|
| Kimi Desktop / Kimi Work（kimi_work） | 官方明确 Windows 本地 Agent、上传本地 Skills、本地文件/浏览器/可授权运行代码、自定义插件 | 桌面等待上限与原生恢复协议未证实；统一短轮询+持久回答，实际闭环 NOT RUN | 本阶段不自动发送；用户发送含 job_id 的继续指令；未来正式桥接另验 | 延期调研，不开发 Adapter；KW-01 至 KW-10 存档。[KW1](https://www.kimi.com/help/kimi-work/overview)、[KW2](https://www.kimi.com/academy/kimi-work-getting-started)、[KW3](https://www.kimi.com/en/help/plugins-and-skills/create) |
| Kimi Code CLI / Code Desktop / 网页 Chat | 非本次 Kimi 主适配目标，不合并标识 | Code 的超时/session/Shell 规则不作为 Work 验收依据 | 不用于替代 Work 原聊天 | 历史参考，不要求安装 CLI；kimi_code 与 kimi_work 分开 |
| WorkBuddy 桌面本地 | 授权本地操作、Skill 导入；开放平台 CLI+Skill 或 MCP+Skill | 历史任务可管理；长 CLI 等待上限和精确原任务恢复未知 | Open API 有发送本地助理消息，需 OAuth/在线助理/作用域；不保证任意原聊天定位 | 本地 CLI+Skill 候选，自动继续是需单独集成的增强。[W1](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)、[W2](https://open.workbuddy.cn/docs/connector)、[W3](https://open.workbuddy.cn/docs/openapi) |
| 豆包桌面端 | 官方确认办公任务入口；自有 Skill 导入/宿主 Python 未证实 | 未取得稳定 CLI/任务恢复协议 | 外部自动发送未证实 | 待实机核实，不认定为无能力。[D1](https://seed.bytedance.com/zh/blog/seed2-1-officially-released-advancing-ai-productivity) |
| 豆包网页版 | 官方站可访问但正文提取为空；没有本机执行桥接证据 | 未证实，云端任务不等于本机进程 | 未证实 | 若无本机桥接只能人工移交，不能用 TRAE/扣子代替。[D2](https://www.doubao.com/chat/) |
| DSH / DeepSeek Harness | 官方插件式 Harness、Skills filesystem、Bash/pwsh 工具 | headless --session-id ID；--json；SDK/ACP 文档入口 | SDK/CLI 桥接候选，需精确 session 与 Job 绑定 | 优先候选；developer preview，版本/profile/插件必须固定。[H1](https://github.com/deepseek-ai/deepseek-harness)、[H2](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cli-help.md)、[H3](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/tool-catalog.md) |

Observed：kimi/workbuddy/doubao/dsh/codebuddy 均未在 PATH 找到；开始菜单发现“Kimi”条目，未确定是不是 Kimi Code；Node v24.12.0、npm 11.6.2 可运行。未做安装、登录、会话读取或平台推理，不能把 PATH 未发现写成“未安装”。

WorkBuddy 同域 `/docs/cli` 是 CodeBuddy Code 文档，其 --resume 不证明 WorkBuddy 桌面支持同名命令。正式连接器市场规范与本地 Skill 调用不同：跨平台/runtime/认证包装需要另验，原有只读 MiniMax 配置不能因接入平台被复制到公共包或云端。[连接器规范](https://open.workbuddy.cn/docs/connector)

共同底线：同一 MakeSound Python CLI、独立 Job Snapshot/持久答案、可信项目根与无声音 Session Preference；无可核实的桥接时使用“复制继续指令”，不能谎称网页自动唤醒。Kimi Work 已有本地能力文档依据，但真实 MakeSound 接入与原聊天投递仍要分开验证。设计见 [Harness_Adapter_Design.md](Harness_Adapter_Design.md)，集成阶段见 [Platform_Integration_Plan.md](Platform_Integration_Plan.md)。
