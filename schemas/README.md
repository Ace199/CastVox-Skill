# M1 协议校验

运行时 Schema 由 `makesound/validation.py`、`voice_registry.validate_registry`、`config_resolver.validate_request` 和 `jobs.validate_snapshot` 的严格验证器执行；没有运行时第三方 JSON Schema 引擎，也不把 MiniMax 文档 Schema 当作本地协议。

所有持久化对象使用 schema_version 1.2，Preset/Registry 有单调 revision。Preset 的 ref 区分 provider_voice/global_asset/project_alias；项目别名不能再引用别名，防止循环。项目设置与声音参数各有字段白名单和类型/范围检查；未知字段/非有限数/重复 JSON key 拒绝。1.1 通过只读兼容视图保留原字段，不静默写回。

可执行离线校验：

```powershell
python -m makesound schema validate --kind preset --file '<实际本地 preset 文件>' --json
python -m makesound schema validate --kind asset-registry --file '<实际本地 assets 文件>' --json
python -m makesound schema validate --kind request --file examples/request-second-paragraph.json --json
python -m makesound schema validate --kind snapshot --file '<实际生成的 snapshot 文件>' --json
```

这类命令不创建目录、不改文件、不联网。尚未提供可供独立第三方 JSON Schema 工具使用的 draft-2020-12 导出；若后续 Studio 需要前端校验，应从同一正式协议生成并做与 Python 规则的一致性测试，不能另造互相冲突的规则。

## Host Bridge 应用协议

[host-bridge-v1.schema.json](host-bridge-v1.schema.json)独立于配音业务：默认校验统一结果，`#/$defs/submission` 校验网页提交，`#/$defs/start` 校验新版启动参数。语义、兼容与示例见[接入文档](../docs/host-bridge-integration.md)。
