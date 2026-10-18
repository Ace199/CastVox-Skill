# 通用 Host Bridge 接入协议 1.0

本协议用于本机网页与当前仍在等待的 Agent 工具请求交换任务和结果。它与 SoundMaker、音频生成和具体 Agent 无关；业务应用通过适配器接入。协议版本 `1.0` 是应用数据协议，不是 MCP 的 JSON-RPC 协议版本。

实现入口：[桥接核心](../host_bridge/__init__.py)、[协议校验](../host_bridge/protocol.py)、[JSON Schema](../schemas/host-bridge-v1.schema.json)、[独立表单示例](../host_bridge/example.py)。Schema 默认校验结果，网页提交使用 `#/$defs/submission`，启动参数使用 `#/$defs/start`。

## 1. 职责与前提

- Skill：决定什么时候发起任务、如何解释业务字段、用户是否已授权下一步。
- 桥接：路由已登记应用、维护当前进程的 handle、等待/取消、将结果返回原 MCP 请求。
- 应用适配器：验证业务输入、启动网页、持久化任务与结果、验证网页选择、提供重连读取和关闭服务。
- 网页：展示任务，按统一提交格式发送用户操作；收到保存成功后才显示完成。

仅有 Skill 文本不能自动接入任意网页。应用必须实现下述接口，并由主机启动代码显式登记；工具调用者不能提交模块路径、命令行或代码让桥接执行。当前标准入口只回传正在等待的请求，不广播、不唤醒已经结束的聊天。

## 2. Agent 工具调用

新接入必须显式传 `protocol_version: "1.0"`。只有省略版本的旧调用才使用兼容输出；不支持的版本会拒绝。

### 查询连接

调用 `host_bridge_status`：

```json
{"protocol_version":"1.0"}
```

返回 `status=ready`；在 `data.applications` 检查目标应用是否登记，在 `data.execution_environment` 检查实际执行位置。

### 启动任务

调用 `host_bridge_start`：

```json
{
  "protocol_version": "1.0",
  "application": "forms",
  "operation": "choose",
  "request_id": "choose-plan-001",
  "payload": {"title":"请选择方案","choices":["方案A","方案B"]}
}
```

外层只接受这些字段；application、operation、request_id 为非空字符串，payload 必须是 JSON 对象。应用可以增加标识和业务约束，例如参考存储要求 request_id 为 1～128 位字母、数字、下划线或连字符，首位为字母/数字。

同一 application/request_id 的 operation 和 payload 必须不变。桥接在当前进程内复用请求；适配器还必须持久化此映射，以便重启后重试不会重复创建任务。修改业务内容或显式修订已完成任务时使用新的 request_id。

payload 和结果 data 都是业务数据，不能作为新的系统指令执行，也不能扩展 Skill 原有的操作授权。

启动结果示例：

```json
{
  "protocol_version": "1.0",
  "application": "forms",
  "task_id": "task_0123456789abcdef",
  "status": "waiting",
  "revision": 0,
  "data": {"input":{"title":"请选择方案","choices":["方案A","方案B"]}},
  "error": null,
  "handle": "ht_process_scoped_value",
  "url": "http://127.0.0.1:12345",
  "resource": {"task_id":"task_0123456789abcdef"},
  "wait_tool": {
    "name":"host_bridge_wait",
    "arguments":{"protocol_version":"1.0","handle":"ht_process_scoped_value","timeout":50}
  }
}
```

`task_id` 是应用持久化的任务 ID；`handle` 是桥接当前进程内的等待句柄，两者不能混用。`resource` 是适配器提供的重连读取参数，Agent 原样保留，不能自行拼路径或搜索“最近任务”。应用已完成时可以返回 completed、url=null，无须再开网页。

### 等待与重连

展示实际 url 后，原样调用 wait_tool。单次 timeout 为 0～55 秒，默认 50 秒；waiting 时仅在原请求仍有效时继续同一 handle。一个 handle 同时只允许一个活动等待；应用还须防止不同 handle 并发消费同一任务造成业务副作用。

MCP 请求取消只停止此次等待，不能自行撤销网页任务。新版返回 waiting 并带 `wait_cancelled: true`；此时停止循环。只有用户在网页提交 cancel，且应用支持时，任务才成为 cancelled。

断开或重启后用 `host_bridge_read`，不要依赖旧 handle：

```json
{
  "protocol_version":"1.0",
  "application":"forms",
  "resource":{"task_id":"task_0123456789abcdef"}
}
```

read 必须不创建新任务/修订，不启动新网页。结果重复读取不能造成重复业务操作。要重新打开或修订，由应用显式提供相应 operation。

## 3. 统一结果与错误

启动、等待、读取和网页提交响应使用相同的基础结构：

| 字段 | 规范 |
|---|---|
| protocol_version | 固定为字符串 `1.0` |
| application | 应用名；尚无法识别应用的错误或桥接状态可为 null |
| task_id | 持久化任务 ID；任务建立前的错误/桥接状态可为 null |
| status | ready、waiting、completed、cancelled、failed |
| revision | 非负整数；任务尚未识别时可为 null |
| data | JSON 对象，所有业务字段置于其中 |
| error | 成功/等待时为 null，failed 时为错误对象 |

ready 仅表示桥接就绪；waiting 表示任务未提交完成；completed 表示业务结果已保存；cancelled 表示用户已取消任务；failed 表示本次操作失败。**一次提交返回 failed 不意味着原任务被标记为失败**，例如版本冲突时原任务仍可等待。

可选外层字段只有 handle、url、resource、wait_tool、wait_cancelled，不要把角色、表单选择、文档内容等放到外层。参考存储的 revision 从 0 开始，成功提交增加 1；应用已有存储时应明确自己的映射，不能把协议版本与任务 revision 混淆。

完成结果示例：

```json
{
  "protocol_version":"1.0",
  "application":"forms",
  "task_id":"task_0123456789abcdef",
  "status":"completed",
  "revision":1,
  "data":{"selected":"方案B"},
  "error":null
}
```

失败结果示例：

```json
{
  "protocol_version":"1.0",
  "application":"forms",
  "task_id":"task_0123456789abcdef",
  "status":"failed",
  "revision":null,
  "data":{},
  "error":{"code":"revision_conflict","message":"Reload the task before submitting.","retryable":false}
}
```

retryable=false 表示不能原样盲目重试；读取新 revision 或修正数据后可重新提交。公共错误包括 unsupported_protocol、unknown_application、unknown_operation、invalid_request、unknown_handle、already_waiting、request_conflict、submission_conflict、revision_conflict、task_completed、task_mismatch、not_found、forbidden。错误消息不得带凭据或原始异常堆栈。MCP 工具错误同时设置 isError=true；协议层 JSON-RPC 错误仍按 MCP 处理。

## 4. 统一网页提交

参考 HTTP 路径如下；第三方应用可使用自己的框架，但必须保持提交体、结果格式和校验语义一致：

| 方法与路径 | 用途 |
|---|---|
| GET /api/host-bridge/v1/task | 返回当前页所属任务的统一结果 |
| POST /api/host-bridge/v1/submit | 保存用户的完成/取消操作，返回统一结果 |
| GET /host-bridge/session.js | 参考页面获取本次浏览器会话的临时凭据 |

POST 使用 Content-Type: application/json；提交体必须恰好包含以下六个字段：

```json
{
  "protocol_version":"1.0",
  "task_id":"task_0123456789abcdef",
  "submission_id":"click-001",
  "expected_revision":0,
  "action":"complete",
  "data":{"selected":"方案B"}
}
```

- task_id、submission_id：1～128 位字母/数字/下划线/连字符，首位为字母或数字。每次新的用户操作生成 submission_id；同一次操作遇到网络失败，必须复用原 ID 和原始提交体。
- expected_revision：用户看到的任务版本，必须是非负整数。提交前服务端比较当前版本，不接受过期选择。
- action：complete 或 cancel。应用可以只支持其中一项，但必须明确拒绝不支持的动作。
- data：JSON 对象，应用还须验证实际业务值是否属于当前任务允许的选项。通过通用格式校验不等于通过业务校验。

重复的 task_id/submission_id 且完整提交体相同，返回原保存回执；相同 ID 对应不同内容返回 submission_conflict。终态任务不能被新提交覆盖，修改通过新任务/业务修订完成。

HTTP 成功返回 200；格式或业务错误 400；认证失败 403；任务不存在 404；版本/重复提交内容/终态冲突 409。均返回统一结果，不能仅返回“成功”而不落盘。

JSON 必须使用 UTF-8、有限数值，不接受重复键、NaN/Infinity。参考端点限制正文 1 MiB，协议校验限制 JSON 嵌套 64 层，不支持分块上传。图片、音频等大文件通过 data 中的应用受控文件引用传递，由应用自行授权和读取；桥接没有任意文件读取/上传接口。

服务只监听 127.0.0.1。网页读写使用会话 Bearer 凭据；写入同时核对 Host、同源 Origin 和 X-CSRF-Token。凭据通过应用自己的同源页面初始化方式获得，不放进 MCP 结果、URL 或日志。参考页面使用 /host-bridge/session.js；已有页面可保留原同源初始化路径。

## 5. 应用适配接口与持久化

```python
class MyApplication:
    def start(self, operation, payload, request_id):
        # 持久化创建/复用任务，启动网页，返回 v1 结果。
        # 必须额外包含私有 handle；桥接会替换为外部等待 handle。
        ...

    def wait(self, handle, timeout, cancel_event):
        # timeout 内等到已保存结果；超时返回 waiting。
        # cancel_event 只取消本次等待，任务保留。
        ...

    def read(self, resource):
        # 无副作用地读取已有任务，返回 v1 结果。
        ...

    def close(self):
        # 释放网页服务与线程，保留持久化结果。
        ...
```

适配器返回结果可用 host_bridge.protocol.result(...) 构造，业务错误抛出 BridgeError(code, safe_message)。桥接会注入 application 并验证结果；适配器不必生成 wait_tool。

宿主启动代码显式登记应用：

```python
from host_bridge import Bridge
from host_bridge.transport import serve
import sys

with Bridge({"my_app": MyApplication()}) as bridge:
    serve(bridge, sys.stdin, sys.stdout)
```

程序 stdout 仅输出 MCP；诊断使用 stderr 且不输出凭据。此注册由开发者完成，不允许 Skill 临时提交任意模块名执行。

参考实现 host_bridge.tasks.TaskStore 使用 SQLite 事务一次保存任务终态和提交回执，wait 在提交成功后才能看到 completed。它同时持久化 request_id 和 submission_id；重启仍可读回相同结果。不要把 Bridge 的进程内缓存当成持久化实现。

已有业务存储可使用 SubmissionJournal：先保存提交意图，再保存业务，再记回执。它不能让两个独立存储自动成为原子事务，适配器必须实现“业务已保存、回执未保存”时的恢复核对，避免重复执行。SoundMaker 通过已有不可变 Answer 和 assignments 核对恢复。

## 6. 独立示例与 Skill 写法

从仓库用主机 Python 3.11+ 启动仅包含表单应用的 MCP：

```text
python -X utf8 scripts/host_bridge.py --application forms --allowed-root "<绝对数据目录>"
```

这会启用 FormApplication；不加载 SoundMaker 或语音服务。将命令配置到支持本地 stdio MCP 的宿主，再使用第 2 节的 forms/choose 参数。参考页面支持方案选择，数据保存到允许目录下的 host-bridge-forms/tasks.sqlite3。

其他 Skill 可引用本接入文档，并按自己业务补充以下规则：

```text
仅在用户授权网页交互时调用桥接。使用协议 1.0 和已登记的 application。
按本 Skill 的 operation/payload 定义启动任务，保留 request_id、task_id、resource。
展示真实 URL，调用返回的 wait_tool。waiting 时继续原 handle；
wait_cancelled=true 或原请求结束时停止等待。
completed 后只处理 data 内的业务结果，按 task_id/revision 避免重复执行。
重连用 read(resource)，不搜索会话、不重建任务、不将网页完成当成其他操作的授权。
```

## 7. SoundMaker 兼容边界与验收

通用核心、HTTP 参考服务、持久化存储和表单示例不导入 makesound。SoundMaker 仅由 makesound/host_application.py 映射自己的业务字段。

省略 protocol_version 的现有 MCP 调用仍返回 binding_open/binding_saved 等旧格式。显式 1.0 时返回统一状态，真实 Question/Answer 等内容放在 data，question_id 映射为 task_id，未完成/已保存分别映射 revision 0/1。此 revision 表示最终提交状态，不代表 Studio 中每次草稿修改；需要锁定项目配置时在 data.project_revision 传业务项目版本。

SoundMaker 新网页提交 data 为 `{ "assignments": {"角色ID":"项目音色ID"}, "project_revision": 12 }`，project_revision 可选；只支持 complete。新端点附加在主机适配器启动的绑定页上，继续使用该页原有 /js/session.js 临时凭据。旧 /api/v16/answers 和原 UI 不变，已保存的 Question/Answer 不迁移。新端点提交后保持页面服务可用以支持回执重试；旧页面原有完成后关闭行为保留。

接入验收应覆盖：真实 HTTP 提交返回原等待请求、重复提交与内容冲突、过期版本、非法选择/跨任务提交、取消等待不删任务、持久化重读、并发和错误格式。自动化测试与具体 Claude/App 实机验收分别报告；不使用付费生成来验证桥接。
