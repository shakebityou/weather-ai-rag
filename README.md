# 天气预报 AI 助手（Agentic RAG）

带 MCP 工具的 Agentic RAG 问答系统：**SQL Server 持久化知识库，Redis 加速，知识库优先、答不上调工具，一键启动自带公网穿透**。

## 📝 更新日志

### v1.0（当前版本）

- ✨ **AI 助手人设优化**：System Prompt 设定为"天气AI助手小A"，知识库无答案时不编造、如实告知并安抚用户情绪，回答简洁，异常输出自动引导联系官方客服
- ✨ **JSON 结构化输出**：LLM 返回统一 `{"answer": "..."}` 格式，后端自动解析，解析失败时返回兜底话术
- ✨ **数学计算修复**：强制所有算数问题走 `calculator` 工具，杜绝 LLM 心算出错；MCP 工具改为本地同步工具（修复 async-only 不支持同步调用的问题）
- ✨ **熔断器**：对 LLM 相关性校验、答案生成、Agent 工具调用三级熔断保护，连续失败 3 次自动降级
- ✨ **一键公网穿透**：`_run.py` 内置 `cloudflared.exe`，启动时自动建立公网隧道并打印地址，手机可直接访问
- ✨ **响应式前端**：适配手机/桌面分辨率，标题改为"天气ai助手"，头像改为 `1.jpg` 圆形裁切，输入框增大，含快捷提问标签
- ✨ **数据库**：迁移至 SQL Server 2022（Windows 身份验证）

## 架构

```
用户提问
   │
   ▼
Redis 缓存 ──命中──→ 直接返回
   │ 未命中
   ▼
SQL Server 读取文档 → FAISS 向量检索 → LLM 相关性校验（Corrective RAG）
   │ 相关                                    │ 不相关
   ▼                                        ▼
带资料生成答案                        ReAct Agent（MCP 工具）
   │                                        │
   └──────────→ 写入 Redis 缓存 ←────────────┘

   熔断器（Circuit Breaker）保护以下外部调用：
   ┌──────────────┬──────────────┬──────────────────┐
   │ llm-grade    │ llm-qa       │ agent            │
   │ 相关性校验   │ 答案生成     │ Agent 工具调用    │
   └──────┬───────┴──────┬───────┴────────┬─────────┘
          │              │                │
          ▼              ▼                ▼
   降级：不相关      降级：返回 None     降级：提示服务不可用
   （转 Agent）     （转 Agent）        （source=degraded）
```

## 一键启动（自带公网穿透）

项目内置 `cloudflared.exe`，运行 `_run.py` 会同时启动 Web 服务和内网穿透，并打印公网地址：

```bash
python _run.py
```

启动后控制台输出：

```
[tunnel] 启动 cloudflared 内网穿透...

============================================================
  🌐 公网访问地址：https://xxx-xxx-xxx.trycloudflare.com
  📱 手机直接打开即可访问（无验证页）
============================================================

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

- 手机用流量打开公网地址即可访问，无需同一局域网
- `Ctrl+C` 退出时自动关闭穿透进程
- cloudflared 未安装时会自动跳过穿透，仅启动本地服务

## 熔断器（Circuit Breaker）

对 LLM 调用和 Agent 调用做熔断保护，防止下游故障拖垮整个服务。

- **三态模型**：`CLOSED`（正常）→ `OPEN`（熔断，快速失败）→ `HALF_OPEN`（半开探测）
- **触发条件**：连续失败达到阈值（默认 3 次）
- **恢复机制**：熔断后等待 `recovery_timeout` 秒（默认 30s），放行一次探测请求，成功则关闭，失败则继续熔断
- **降级策略**：
  - `llm-grade` 熔断 → 文档判为不相关，问题转交给 Agent
  - `llm-qa` 熔断 → 返回 None，问题转交给 Agent
  - `agent` 熔断 → 返回"抱歉，工具服务暂时不可用"，`source=degraded`

配置项（`.env` 或环境变量）：

```env
CB_FAILURE_THRESHOLD=3      # 连续失败多少次后熔断
CB_RECOVERY_TIMEOUT=30.0    # 熔断后多少秒进入半开探测
```

## 前端特性

- 响应式布局，适配手机 / 平板 / 桌面
- 圆形头像、渐变背景、毛玻璃聊天气泡
- 快捷提问标签、回车发送（Shift+Enter 换行）
- 熔断降级时显示红色 `熔断降级` 标签

## 技术栈与分工

| 组件 | 作用 |
|---|---|
| FastAPI | 接口层，lifespan 管理 LLM/Agent 生命周期 |
| LangChain (LCEL) | PromptTemplate、链式调用 |
| LangGraph | ReAct Agent 编排与工具调用 |
| MCP 协议 | 工具以 stdio 标准协议暴露，Agent 自动发现，失败降级本地工具 |
| FAISS + sentence-transformers | 本地向量检索（embedding 免费离线） |
| SQL Server | 文档持久化存储，启动自动建库建表、空库灌示例数据 |
| Redis | 问答结果缓存，TTL 过期，连不上自动降级 |
| Circuit Breaker | 熔断器（三态模型），保护 LLM/Agent 调用，失败自动降级 |
| cloudflared | 一键内网穿透，免注册、无验证页，手机直接访问 |
| Docker Compose | app + redis + mysql 一键编排 |

## 目录结构

```
.
├── _run.py              # 一键启动入口（服务 + cloudflared 内网穿透）
├── cloudflared.exe      # 内网穿透工具（免安装，随项目分发）
├── app/
│   ├── main.py            # FastAPI 入口，三级路由：缓存→RAG→Agent（Agent 带熔断）
│   ├── rag.py             # Corrective RAG，LLM 调用带熔断（llm-grade / llm-qa）
│   ├── db.py              # SQL Server 访问层（pyodbc）
│   ├── agent.py           # ReAct Agent，MCP 工具加载 + 降级
│   ├── mcp_server.py      # MCP Server：天气/计算器/时间
│   ├── circuit_breaker.py # 熔断器：三态模型（CLOSED/OPEN/HALF_OPEN）+ 装饰器
│   ├── config.py          # pydantic-settings 统一配置（含熔断参数）
│   └── utils.py           # Redis 缓存
└── static/
    ├── index.html         # 响应式前端（Vue3 + Element Plus）
    └── 1.jpg              # 头像图片
```

## 运行

### 一键启动（推荐，自带公网穿透）

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python _run.py
```

启动后自动获得公网地址，手机可直接访问。

### 仅本地启动（不开启穿透）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker-compose up --build
```

## 测试

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "年假有几天？"}'
# {"answer": "...", "source": "kb"}   ← 知识库回答

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "北京今天天气怎么样，顺便算一下 12*8"}'
# {"answer": "...", "source": "agent"}  ← 走 Agent 工具调用
```

同一个问题问两次，第二次 `source` 变为 `cache`，说明 Redis 缓存命中。

## 工程细节

1. **Corrective RAG**：检索结果经 LLM 相关性校验，不相关拒答转 Agent，防幻觉
2. **优雅降级**：SQL Server / Redis / MCP 任一不可用，服务照常运行（内置文档、不缓存、本地工具）
3. **缓存三级路由**：缓存 → 知识库 → 工具，典型生产查询链路
4. **MCP 解耦**：工具通过标准协议暴露，Agent 自动发现 schema，换工具不改 Agent
5. **熔断器保护**：三态模型（CLOSED/OPEN/HALF_OPEN）保护 LLM 与 Agent 调用，连续失败自动熔断并降级，超时后半开探测恢复，避免下游故障雪崩
6. **一键公网部署**：内置 cloudflared，启动即获得公网地址，手机端无需配置即可访问



## 常见问题

- **faiss-cpu 在 Windows 装不上**：换 chromadb（pip install chromadb），或改用内存余弦相似度
- **sentence-transformers 首次运行下载模型**：属正常现象，模型约 90MB
- **公网地址打不开**：确认 cloudflared 进程是否存活，或重启 `_run.py` 获取新地址
- **cloudflared 未找到**：项目根目录应包含 `cloudflared.exe`，或执行 `winget install Cloudflare.cloudflared`
